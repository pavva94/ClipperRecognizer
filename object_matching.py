#!/usr/bin/env python3
"""
Object Matching Application using YOLO 11 and DINOv2 Feature Extraction
This application provides two main processes:
1. Database Loading: Extract objects from batch images and store DINOv2 features
2. Query Processing: Match query objects against the database using cosine similarity
"""

import os
import cv2
import numpy as np
import sqlite3
import pickle
import json
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from datetime import datetime
import argparse
import logging
from ultralytics import YOLO
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from tqdm import tqdm
import torch
import torch.nn as nn
import torchvision.transforms as transforms
from sklearn.metrics.pairwise import cosine_similarity
from PIL import Image
import warnings

warnings.filterwarnings('ignore')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('object_matching.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Manages SQLite database operations for storing object features
    """

    def __init__(self, db_path: str = "object_features.db"):
        self.db_path = db_path
        self.init_database()

    def init_database(self):
        """Initialize SQLite database with required tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Create images table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                filepath TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Create objects table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS objects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                image_id INTEGER NOT NULL,
                object_class TEXT NOT NULL,
                confidence REAL NOT NULL,
                bbox_x1 INTEGER NOT NULL,
                bbox_y1 INTEGER NOT NULL,
                bbox_x2 INTEGER NOT NULL,
                bbox_y2 INTEGER NOT NULL,
                object_image_path TEXT NOT NULL,
                feature_vector BLOB,
                feature_dim INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (image_id) REFERENCES images (id)
            )
        ''')

        # Create indexes for better performance
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_objects_class ON objects(object_class)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_objects_confidence ON objects(confidence)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_objects_feature_dim ON objects(feature_dim)')

        conn.commit()
        conn.close()
        logger.info("Database initialized successfully")

    def add_image(self, filename: str, filepath: str) -> int:
        """Add a new image to the database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO images (filename, filepath) 
            VALUES (?, ?)
        ''', (filename, filepath))

        image_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return image_id

    def add_object(self, image_id: int, object_data: Dict) -> int:
        """Add an object with its features to the database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Serialize feature vector
        feature_blob = pickle.dumps(object_data['feature_vector']) if object_data[
                                                                          'feature_vector'] is not None else None
        feature_dim = len(object_data['feature_vector']) if object_data['feature_vector'] is not None else 0

        cursor.execute('''
            INSERT INTO objects (
                image_id, object_class, confidence, bbox_x1, bbox_y1, bbox_x2, bbox_y2,
                object_image_path, feature_vector, feature_dim
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            image_id, object_data['class_name'], object_data['confidence'],
            object_data['bbox'][0], object_data['bbox'][1], object_data['bbox'][2], object_data['bbox'][3],
            object_data['object_image_path'], feature_blob, feature_dim
        ))

        object_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return object_id

    def get_all_objects(self, object_class: str = None, min_feature_dim: int = 100) -> List[Dict]:
        """Retrieve all objects from the database with optional filtering"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        query = '''
            SELECT o.id, o.image_id, o.object_class, o.confidence, o.bbox_x1, o.bbox_y1, 
                   o.bbox_x2, o.bbox_y2, o.object_image_path, o.feature_vector, o.feature_dim,
                   i.filename, i.filepath
            FROM objects o
            JOIN images i ON o.image_id = i.id
            WHERE o.feature_dim >= ?
        '''

        params = [min_feature_dim]

        if object_class:
            query += " AND o.object_class = ?"
            params.append(object_class)

        query += " ORDER BY o.confidence DESC"

        cursor.execute(query, params)
        results = cursor.fetchall()
        conn.close()

        objects = []
        for row in results:
            obj = {
                'id': row[0],
                'image_id': row[1],
                'object_class': row[2],
                'confidence': row[3],
                'bbox': [row[4], row[5], row[6], row[7]],
                'object_image_path': row[8],
                'feature_vector': pickle.loads(row[9]) if row[9] else None,
                'feature_dim': row[10],
                'original_filename': row[11],
                'original_filepath': row[12]
            }
            objects.append(obj)

        return objects

    def get_database_stats(self) -> Dict:
        """Get database statistics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('SELECT COUNT(*) FROM images')
        total_images = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM objects')
        total_objects = cursor.fetchone()[0]

        cursor.execute('SELECT object_class, COUNT(*) FROM objects GROUP BY object_class')
        class_counts = dict(cursor.fetchall())

        cursor.execute('SELECT AVG(feature_dim) FROM objects WHERE feature_dim > 0')
        avg_feature_dim = cursor.fetchone()[0] or 0

        conn.close()

        return {
            'total_images': total_images,
            'total_objects': total_objects,
            'class_counts': class_counts,
            'avg_feature_dim': round(avg_feature_dim, 2)
        }


class DINOv2FeatureExtractor:
    """
    Handles deep learning-based feature extraction using DINOv2
    """

    def __init__(self, model_name: str = "dinov2_vits14", feature_dim: int = 384):
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.model_name = model_name

        # Load DINOv2 model from torch hub
        try:
            self.model = torch.hub.load('facebookresearch/dinov2', model_name)
            self.model.to(self.device)
            self.model.eval()

            # Get the actual feature dimension from the model
            if 'vits14' in model_name:
                self.feature_dim = 384
            elif 'vitb14' in model_name:
                self.feature_dim = 768
            elif 'vitl14' in model_name:
                self.feature_dim = 1024
            elif 'vitg14' in model_name:
                self.feature_dim = 1536
            else:
                self.feature_dim = feature_dim

        except Exception as e:
            logger.error(f"Failed to load DINOv2 model: {e}")
            logger.info("Falling back to local model loading...")
            # Alternative: try loading from local checkpoint if available
            raise RuntimeError(f"Could not load DINOv2 model: {e}")

        # Image preprocessing pipeline for DINOv2
        self.transform = transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406],
                                 std=[0.229, 0.224, 0.225])
        ])

        logger.info(f"DINOv2 feature extractor initialized with {model_name} on {self.device}")
        logger.info(f"Feature dimension: {self.feature_dim}")

    def extract_features(self, image: np.ndarray) -> np.ndarray:
        """
        Extract DINOv2 features from an image

        Args:
            image (np.ndarray): Input image (BGR format from OpenCV)

        Returns:
            np.ndarray: Feature vector
        """
        try:
            # Convert BGR to RGB
            if len(image.shape) == 3:
                image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            else:
                image_rgb = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)

            # Convert to PIL Image
            pil_image = Image.fromarray(image_rgb)

            # Apply preprocessing
            input_tensor = self.transform(pil_image).unsqueeze(0).to(self.device)

            # Extract features using DINOv2
            with torch.no_grad():
                # DINOv2 returns CLS token features by default
                features = self.model(input_tensor)

                # Convert to numpy and normalize
                features = features.cpu().numpy().flatten()

                # L2 normalize the features
                features = features / (np.linalg.norm(features) + 1e-8)

            return features

        except Exception as e:
            logger.error(f"Feature extraction error: {e}")
            return None

    def extract_features_with_patches(self, image: np.ndarray) -> np.ndarray:
        """
        Extract DINOv2 features including patch tokens (more detailed representation)

        Args:
            image (np.ndarray): Input image (BGR format from OpenCV)

        Returns:
            np.ndarray: Aggregated feature vector from all patches
        """
        try:
            # Convert BGR to RGB
            if len(image.shape) == 3:
                image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            else:
                image_rgb = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)

            # Convert to PIL Image
            pil_image = Image.fromarray(image_rgb)

            # Apply preprocessing
            input_tensor = self.transform(pil_image).unsqueeze(0).to(self.device)

            # Extract features using DINOv2
            with torch.no_grad():
                # Get all features (CLS + patch tokens)
                features = self.model.forward_features(input_tensor)

                # Option 1: Use only CLS token (global representation)
                cls_token = features['x_norm_clstoken'].cpu().numpy().flatten()

                # Option 2: Use patch tokens (local representations)
                patch_tokens = features['x_norm_patchtokens']  # Shape: [batch, num_patches, feature_dim]

                # Aggregate patch tokens (mean pooling)
                patch_features = torch.mean(patch_tokens, dim=1).cpu().numpy().flatten()

                # Combine CLS and patch features (or use only CLS)
                # For now, we'll use only CLS token for consistency
                final_features = cls_token

                # L2 normalize the features
                final_features = final_features / (np.linalg.norm(final_features) + 1e-8)

            return final_features

        except Exception as e:
            logger.error(f"Feature extraction with patches error: {e}")
            # Fallback to regular feature extraction
            return self.extract_features(image)

    def compute_similarity(self, feature1: np.ndarray, feature2: np.ndarray) -> float:
        """
        Compute cosine similarity between two feature vectors

        Args:
            feature1 (np.ndarray): First feature vector
            feature2 (np.ndarray): Second feature vector

        Returns:
            float: Cosine similarity score
        """
        if feature1 is None or feature2 is None:
            return 0.0

        # Reshape for sklearn cosine_similarity
        feature1 = feature1.reshape(1, -1)
        feature2 = feature2.reshape(1, -1)

        similarity = cosine_similarity(feature1, feature2)[0, 0]
        return float(similarity)


class DeepFeatureMatcher:
    """
    Handles deep learning-based feature matching using cosine similarity
    """

    def __init__(self, feature_extractor: DINOv2FeatureExtractor):
        self.feature_extractor = feature_extractor
        logger.info("Deep feature matcher initialized with DINOv2")

    def match_features(self, query_features: np.ndarray,
                       db_features: np.ndarray) -> float:
        """
        Match features between query and database using cosine similarity

        Args:
            query_features (np.ndarray): Query feature vector
            db_features (np.ndarray): Database feature vector

        Returns:
            float: Similarity score
        """
        return self.feature_extractor.compute_similarity(query_features, db_features)


class ObjectMatchingApp:
    """
    Main application class for object matching using DINOv2 features
    """

    def __init__(self, model_path: str = "yolo11n.pt", target_class: str = "person",
                 feature_model: str = "dinov2_vits14", use_patch_features: bool = False):
        self.model = YOLO(model_path)
        self.target_class = target_class
        self.use_patch_features = use_patch_features
        self.db_manager = DatabaseManager()
        self.feature_extractor = DINOv2FeatureExtractor(feature_model)
        self.feature_matcher = DeepFeatureMatcher(self.feature_extractor)

        # Create directories
        self.extracted_objects_dir = "extracted_objects"
        self.query_objects_dir = "query_objects"
        Path(self.extracted_objects_dir).mkdir(exist_ok=True)
        Path(self.query_objects_dir).mkdir(exist_ok=True)

        # Find target class ID
        self.target_class_id = None
        for class_id, class_name in self.model.names.items():
            if class_name.lower() == target_class.lower():
                self.target_class_id = class_id
                break

        logger.info(f"ObjectMatchingApp initialized for class: {target_class}")
        logger.info(f"Using DINOv2 model: {feature_model}")
        logger.info(f"Patch features enabled: {use_patch_features}")

    def process_single_image(self, image_path: str, confidence_threshold: float = 0.5) -> List[Dict]:
        """
        Process a single image to extract objects and their features

        Args:
            image_path (str): Path to the image
            confidence_threshold (float): Minimum confidence threshold

        Returns:
            List[Dict]: List of processed objects with features
        """
        # Load image
        image = cv2.imread(image_path)
        if image is None:
            logger.error(f"Could not load image: {image_path}")
            return []

        # Run YOLO detection
        results = self.model(image)

        processed_objects = []
        base_name = Path(image_path).stem

        for result in results:
            boxes = result.boxes
            if boxes is not None:
                for i, box in enumerate(boxes):
                    class_id = int(box.cls)
                    confidence = float(box.conf)

                    # Filter by target class and confidence
                    if (
                            self.target_class_id is None or class_id == self.target_class_id) and confidence >= confidence_threshold:
                        x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)

                        # Extract object region
                        object_img = image[y1:y2, x1:x2]

                        # Skip if object is too small
                        if object_img.shape[0] < 32 or object_img.shape[1] < 32:
                            continue

                        # Extract DINOv2 features
                        if self.use_patch_features:
                            features = self.feature_extractor.extract_features_with_patches(object_img)
                        else:
                            features = self.feature_extractor.extract_features(object_img)

                        if features is None:
                            continue

                        # Save extracted object
                        object_filename = f"{base_name}_obj_{i:03d}_conf{confidence:.2f}.jpg"
                        object_path = os.path.join(self.extracted_objects_dir, object_filename)
                        cv2.imwrite(object_path, object_img)

                        # Prepare object data
                        object_data = {
                            'class_name': self.model.names[class_id],
                            'confidence': confidence,
                            'bbox': [x1, y1, x2, y2],
                            'object_image_path': object_path,
                            'feature_vector': features,
                            'feature_dim': len(features)
                        }

                        processed_objects.append(object_data)
                        logger.info(f"Processed object {i}: {object_data['class_name']} "
                                    f"(conf: {confidence:.2f}, feature_dim: {object_data['feature_dim']})")

        return processed_objects

    def load_database(self, images_directory: str, confidence_threshold: float = 0.5,
                      max_workers: int = 4) -> Dict:
        """
        Load database by processing batch of images

        Args:
            images_directory (str): Directory containing images
            confidence_threshold (float): Minimum confidence threshold
            max_workers (int): Number of parallel workers

        Returns:
            Dict: Processing statistics
        """
        logger.info(f"Starting database loading from: {images_directory}")

        # Get all image files
        image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp'}
        image_files = []

        for ext in image_extensions:
            image_files.extend(Path(images_directory).glob(f"*{ext}"))
            image_files.extend(Path(images_directory).glob(f"*{ext.upper()}"))

        logger.info(f"Found {len(image_files)} images to process")

        if not image_files:
            logger.warning("No images found in the specified directory")
            return {'total_images': 0, 'total_objects': 0, 'processed_images': 0}

        stats = {
            'total_images': len(image_files),
            'processed_images': 0,
            'total_objects': 0,
            'failed_images': 0,
            'processing_time': 0
        }

        start_time = datetime.now()

        # Process images in parallel (but limit to avoid GPU memory issues)
        max_workers = min(max_workers, 2) if torch.cuda.is_available() else max_workers

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_image = {
                executor.submit(self.process_single_image, str(img_path), confidence_threshold): img_path
                for img_path in image_files
            }

            # Process completed tasks
            with tqdm(total=len(image_files), desc="Processing images") as pbar:
                for future in as_completed(future_to_image):
                    img_path = future_to_image[future]
                    try:
                        processed_objects = future.result()

                        if processed_objects:
                            # Add image to database
                            image_id = self.db_manager.add_image(img_path.name, str(img_path))

                            # Add objects to database
                            for obj_data in processed_objects:
                                self.db_manager.add_object(image_id, obj_data)
                                stats['total_objects'] += 1

                            stats['processed_images'] += 1

                    except Exception as e:
                        logger.error(f"Error processing {img_path}: {e}")
                        stats['failed_images'] += 1

                    pbar.update(1)

        stats['processing_time'] = (datetime.now() - start_time).total_seconds()

        logger.info(f"Database loading completed:")
        logger.info(f"  - Processed images: {stats['processed_images']}/{stats['total_images']}")
        logger.info(f"  - Total objects: {stats['total_objects']}")
        logger.info(f"  - Failed images: {stats['failed_images']}")
        logger.info(f"  - Processing time: {stats['processing_time']:.2f} seconds")

        return stats

    def query_object(self, query_image_path: str, confidence_threshold: float = 0.5,
                     top_k: int = 10, object_class: str = None,
                     min_similarity: float = 0.5) -> List[Dict]:
        """
        Query the database with a single object image

        Args:
            query_image_path (str): Path to query image
            confidence_threshold (float): Minimum confidence threshold
            top_k (int): Number of top matches to return
            object_class (str): Filter by object class (optional)
            min_similarity (float): Minimum similarity threshold

        Returns:
            List[Dict]: Top matching objects with similarity scores
        """
        logger.info(f"Querying database with: {query_image_path}")

        # Process query image
        query_objects = self.process_single_image(query_image_path, confidence_threshold)

        if not query_objects:
            logger.warning("No objects detected in query image")
            return []

        # Use the first detected object as query
        query_obj = query_objects[0]
        query_features = query_obj['feature_vector']

        if query_features is None:
            logger.warning("No features extracted from query object")
            return []

        logger.info(f"Query object: {query_obj['class_name']} "
                    f"(conf: {query_obj['confidence']:.2f}, feature_dim: {query_obj['feature_dim']})")

        # Get database objects
        db_objects = self.db_manager.get_all_objects(object_class, min_feature_dim=100)

        if not db_objects:
            logger.warning("No objects found in database")
            return []

        logger.info(f"Matching against {len(db_objects)} database objects")

        # Match against all database objects
        matches_results = []

        for db_obj in tqdm(db_objects, desc="Matching objects"):
            if db_obj['feature_vector'] is None:
                continue

            # Calculate similarity using cosine similarity
            similarity_score = self.feature_matcher.match_features(
                query_features, db_obj['feature_vector']
            )

            if similarity_score >= min_similarity:
                match_result = {
                    'object_id': db_obj['id'],
                    'similarity_score': similarity_score,
                    'object_class': db_obj['object_class'],
                    'confidence': db_obj['confidence'],
                    'original_filename': db_obj['original_filename'],
                    'original_filepath': db_obj['original_filepath'],
                    'object_image_path': db_obj['object_image_path'],
                    'feature_dim': db_obj['feature_dim']
                }

                matches_results.append(match_result)

        # Sort by similarity score (descending)
        matches_results.sort(key=lambda x: x['similarity_score'], reverse=True)

        # Return top k matches
        top_matches = matches_results[:top_k]

        logger.info(f"Found {len(top_matches)} matches above threshold {min_similarity}")
        for i, match in enumerate(top_matches[:5]):  # Log top 5
            logger.info(f"  {i + 1}. {match['original_filename']} "
                        f"(similarity: {match['similarity_score']:.3f})")

        return top_matches

    def get_stats(self) -> Dict:
        """Get application statistics"""
        db_stats = self.db_manager.get_database_stats()
        return {
            'database_stats': db_stats,
            'target_class': self.target_class,
            'extracted_objects_dir': self.extracted_objects_dir,
            'query_objects_dir': self.query_objects_dir,
            'feature_extractor': f'DINOv2 ({self.feature_extractor.model_name})',
            'feature_dimension': self.feature_extractor.feature_dim,
            'patch_features': self.use_patch_features,
            'device': str(self.feature_extractor.device)
        }


def main():
    """Main function for command line interface"""
    parser = argparse.ArgumentParser(description="Object Matching Application with DINOv2 Features")
    parser.add_argument("--mode", choices=["load", "query", "stats"], required=True,
                        help="Operation mode")
    parser.add_argument("--model", type=str, default="yolo11n.pt",
                        help="YOLO model path")
    parser.add_argument("--class", type=str, default="person", dest="target_class",
                        help="Target object class")
    parser.add_argument("--feature-model", type=str, default="dinov2_vits14",
                        choices=["dinov2_vits14", "dinov2_vitb14", "dinov2_vitl14", "dinov2_vitg14"],
                        help="DINOv2 model variant")
    parser.add_argument("--patch-features", action="store_true",
                        help="Use patch features in addition to CLS token")
    parser.add_argument("--images-dir", type=str,
                        help="Directory containing images (for load mode)")
    parser.add_argument("--query-image", type=str,
                        help="Query image path (for query mode)")
    parser.add_argument("--confidence", type=float, default=0.5,
                        help="Confidence threshold")
    parser.add_argument("--similarity", type=float, default=0.5,
                        help="Minimum similarity threshold")
    parser.add_argument("--top-k", type=int, default=10,
                        help="Number of top matches to return")
    parser.add_argument("--workers", type=int, default=4,
                        help="Number of parallel workers")

    args = parser.parse_args()

    # Initialize application
    app = ObjectMatchingApp(args.model, args.target_class, args.feature_model, args.patch_features)

    if args.mode == "load":
        if not args.images_dir:
            print("Error: --images-dir is required for load mode")
            return

        if not os.path.exists(args.images_dir):
            print(f"Error: Directory {args.images_dir} does not exist")
            return

        stats = app.load_database(args.images_dir, args.confidence, args.workers)
        print(f"\nDatabase Loading Results:")
        print(f"  Total images: {stats['total_images']}")
        print(f"  Processed images: {stats['processed_images']}")
        print(f"  Total objects extracted: {stats['total_objects']}")
        print(f"  Failed images: {stats['failed_images']}")
        print(f"  Processing time: {stats['processing_time']:.2f} seconds")

    elif args.mode == "query":
        if not args.query_image:
            print("Error: --query-image is required for query mode")
            return

        if not os.path.exists(args.query_image):
            print(f"Error: Query image {args.query_image} does not exist")
            return

        matches = app.query_object(args.query_image, args.confidence, args.top_k,
                                   min_similarity=args.similarity)

        if matches:
            print(f"\nTop {len(matches)} matches:")
            for i, match in enumerate(matches):
                print(f"  {i + 1}. {match['original_filename']}")
                print(f"      Similarity score: {match['similarity_score']:.3f}")
                print(f"      Object class: {match['object_class']}")
                print(f"      Confidence: {match['confidence']:.2f}")
                print(f"      Original image: {match['original_filepath']}")
                print()
        else:
            print("No matches found")

    elif args.mode == "stats":
        stats = app.get_stats()
        print("\nApplication Statistics:")
        print(f"  Target class: {stats['target_class']}")
        print(f"  Feature extractor: {stats['feature_extractor']}")
        print(f"  Feature dimension: {stats['feature_dimension']}")
        print(f"  Patch features enabled: {stats['patch_features']}")
        print(f"  Device: {stats['device']}")
        print(f"  Total images in database: {stats['database_stats']['total_images']}")
        print(f"  Total objects in database: {stats['database_stats']['total_objects']}")
        print(f"  Average feature dimension: {stats['database_stats']['avg_feature_dim']}")
        print(f"  Class distribution:")
        for class_name, count in stats['database_stats']['class_counts'].items():
            print(f"    {class_name}: {count}")


if __name__ == "__main__":
    main()