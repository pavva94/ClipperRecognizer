#!/usr/bin/env python3
"""
Object Matching Application using YOLO 11 and SIFT
This application provides two main processes:
1. Database Loading: Extract objects from batch images and store SIFT features
2. Query Processing: Match query objects against the database using FLANN
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
        """Initialize the database schema"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Create tables
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                filepath TEXT NOT NULL,
                upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                processed BOOLEAN DEFAULT FALSE
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS objects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                image_id INTEGER,
                object_class TEXT NOT NULL,
                confidence REAL NOT NULL,
                bbox_x1 INTEGER,
                bbox_y1 INTEGER,
                bbox_x2 INTEGER,
                bbox_y2 INTEGER,
                object_image_path TEXT,
                keypoints_count INTEGER,
                descriptors BLOB,
                keypoints BLOB,
                created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (image_id) REFERENCES images (id)
            )
        ''')

        # Create indexes for faster querying
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_object_class ON objects(object_class)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_confidence ON objects(confidence)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_keypoints_count ON objects(keypoints_count)')

        conn.commit()
        conn.close()
        logger.info(f"Database initialized at {self.db_path}")

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

        # Serialize keypoints and descriptors
        keypoints_blob = pickle.dumps(object_data['keypoints']) if object_data['keypoints'] else None
        descriptors_blob = pickle.dumps(object_data['descriptors']) if object_data['descriptors'] is not None else None

        cursor.execute('''
            INSERT INTO objects (
                image_id, object_class, confidence, bbox_x1, bbox_y1, bbox_x2, bbox_y2,
                object_image_path, keypoints_count, descriptors, keypoints
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            image_id, object_data['class_name'], object_data['confidence'],
            object_data['bbox'][0], object_data['bbox'][1], object_data['bbox'][2], object_data['bbox'][3],
            object_data['object_image_path'], object_data['keypoints_count'],
            descriptors_blob, keypoints_blob
        ))

        object_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return object_id

    def get_all_objects(self, object_class: str = None, min_keypoints: int = 10) -> List[Dict]:
        """Retrieve all objects from the database with optional filtering"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        query = '''
            SELECT o.id, o.image_id, o.object_class, o.confidence, o.bbox_x1, o.bbox_y1, 
                   o.bbox_x2, o.bbox_y2, o.object_image_path, o.keypoints_count, 
                   o.descriptors, o.keypoints, i.filename, i.filepath
            FROM objects o
            JOIN images i ON o.image_id = i.id
            WHERE o.keypoints_count >= ?
        '''

        params = [min_keypoints]

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
                'keypoints_count': row[9],
                'descriptors': pickle.loads(row[10]) if row[10] else None,
                'keypoints': pickle.loads(row[11]) if row[11] else None,
                'original_filename': row[12],
                'original_filepath': row[13]
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

        cursor.execute('SELECT AVG(keypoints_count) FROM objects WHERE keypoints_count > 0')
        avg_keypoints = cursor.fetchone()[0] or 0

        conn.close()

        return {
            'total_images': total_images,
            'total_objects': total_objects,
            'class_counts': class_counts,
            'avg_keypoints': round(avg_keypoints, 2)
        }


class SIFTFeatureExtractor:
    """
    Handles SIFT feature extraction from images
    """

    def __init__(self, n_features: int = 5000):
        self.sift = cv2.SIFT_create(nfeatures=n_features)
        logger.info(f"SIFT extractor initialized with {n_features} features")

    def extract_features(self, image: np.ndarray) -> Tuple[List, np.ndarray]:
        """
        Extract SIFT features from an image

        Args:
            image (np.ndarray): Input image

        Returns:
            Tuple[List, np.ndarray]: Keypoints and descriptors
        """
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image

        keypoints, descriptors = self.sift.detectAndCompute(gray, None)

        return keypoints, descriptors


class FLANNMatcher:
    """
    Handles FLANN-based feature matching
    """

    def __init__(self):
        # FLANN parameters
        FLANN_INDEX_KDTREE = 1
        index_params = dict(algorithm=FLANN_INDEX_KDTREE, trees=5)
        search_params = dict(checks=50)

        self.matcher = cv2.FlannBasedMatcher(index_params, search_params)
        logger.info("FLANN matcher initialized")

    def match_features(self, query_descriptors: np.ndarray,
                       db_descriptors: np.ndarray) -> List[cv2.DMatch]:
        """
        Match features between query and database descriptors

        Args:
            query_descriptors (np.ndarray): Query image descriptors
            db_descriptors (np.ndarray): Database image descriptors

        Returns:
            List[cv2.DMatch]: List of matches
        """
        if query_descriptors is None or db_descriptors is None:
            return []

        if len(query_descriptors) < 2 or len(db_descriptors) < 2:
            return []

        try:
            matches = self.matcher.knnMatch(query_descriptors, db_descriptors, k=2)

            # Apply Lowe's ratio test
            good_matches = []
            for match_pair in matches:
                if len(match_pair) == 2:
                    m, n = match_pair
                    if m.distance < 0.7 * n.distance:
                        good_matches.append(m)

            return good_matches
        except cv2.error as e:
            logger.warning(f"FLANN matching error: {e}")
            return []


class ObjectMatchingApp:
    """
    Main application class for object matching
    """

    def __init__(self, model_path: str = "yolo11n.pt", target_class: str = "person"):
        self.model = YOLO(model_path)
        self.target_class = target_class
        self.db_manager = DatabaseManager()
        self.sift_extractor = SIFTFeatureExtractor()
        self.flann_matcher = FLANNMatcher()

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

                        # Extract SIFT features
                        keypoints, descriptors = self.sift_extractor.extract_features(object_img)

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
                            'keypoints': keypoints,
                            'descriptors': descriptors,
                            'keypoints_count': len(keypoints) if keypoints else 0
                        }

                        processed_objects.append(object_data)
                        logger.info(f"Processed object {i}: {object_data['class_name']} "
                                    f"(conf: {confidence:.2f}, keypoints: {object_data['keypoints_count']})")

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

        # Process images in parallel
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
                     top_k: int = 10, object_class: str = None) -> List[Dict]:
        """
        Query the database with a single object image

        Args:
            query_image_path (str): Path to query image
            confidence_threshold (float): Minimum confidence threshold
            top_k (int): Number of top matches to return
            object_class (str): Filter by object class (optional)

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
        query_descriptors = query_obj['descriptors']

        if query_descriptors is None or len(query_descriptors) == 0:
            logger.warning("No SIFT features found in query object")
            return []

        logger.info(f"Query object: {query_obj['class_name']} "
                    f"(conf: {query_obj['confidence']:.2f}, keypoints: {query_obj['keypoints_count']})")

        # Get database objects
        db_objects = self.db_manager.get_all_objects(object_class, min_keypoints=10)

        if not db_objects:
            logger.warning("No objects found in database")
            return []

        logger.info(f"Matching against {len(db_objects)} database objects")

        # Match against all database objects
        matches_results = []

        for db_obj in tqdm(db_objects, desc="Matching objects"):
            if db_obj['descriptors'] is None:
                continue

            # Match features
            matches = self.flann_matcher.match_features(query_descriptors, db_obj['descriptors'])

            if matches:
                # Calculate similarity score (number of good matches)
                similarity_score = len(matches)

                # Normalize by query keypoints count
                normalized_score = similarity_score / len(query_descriptors)

                match_result = {
                    'object_id': db_obj['id'],
                    'similarity_score': similarity_score,
                    'normalized_score': normalized_score,
                    'matches_count': len(matches),
                    'object_class': db_obj['object_class'],
                    'confidence': db_obj['confidence'],
                    'original_filename': db_obj['original_filename'],
                    'original_filepath': db_obj['original_filepath'],
                    'object_image_path': db_obj['object_image_path'],
                    'keypoints_count': db_obj['keypoints_count']
                }

                matches_results.append(match_result)

        # Sort by similarity score (descending)
        matches_results.sort(key=lambda x: x['similarity_score'], reverse=True)

        # Return top k matches
        top_matches = matches_results[:top_k]

        logger.info(f"Found {len(top_matches)} matches")
        for i, match in enumerate(top_matches[:5]):  # Log top 5
            logger.info(f"  {i + 1}. {match['original_filename']} "
                        f"(score: {match['similarity_score']}, "
                        f"norm: {match['normalized_score']:.3f})")

        return top_matches

    def get_stats(self) -> Dict:
        """Get application statistics"""
        db_stats = self.db_manager.get_database_stats()
        return {
            'database_stats': db_stats,
            'target_class': self.target_class,
            'extracted_objects_dir': self.extracted_objects_dir,
            'query_objects_dir': self.query_objects_dir
        }


def main():
    """Main function for command line interface"""
    parser = argparse.ArgumentParser(description="Object Matching Application")
    parser.add_argument("--mode", choices=["load", "query", "stats"], required=True,
                        help="Operation mode")
    parser.add_argument("--model", type=str, default="yolo11n.pt",
                        help="YOLO model path")
    parser.add_argument("--class", type=str, default="person", dest="target_class",
                        help="Target object class")
    parser.add_argument("--images-dir", type=str,
                        help="Directory containing images (for load mode)")
    parser.add_argument("--query-image", type=str,
                        help="Query image path (for query mode)")
    parser.add_argument("--confidence", type=float, default=0.5,
                        help="Confidence threshold")
    parser.add_argument("--top-k", type=int, default=10,
                        help="Number of top matches to return")
    parser.add_argument("--workers", type=int, default=4,
                        help="Number of parallel workers")

    args = parser.parse_args()

    # Initialize application
    app = ObjectMatchingApp(args.model, args.target_class)

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

        matches = app.query_object(args.query_image, args.confidence, args.top_k)

        if matches:
            print(f"\nTop {len(matches)} matches:")
            for i, match in enumerate(matches):
                print(f"  {i + 1}. {match['original_filename']}")
                print(f"      Similarity score: {match['similarity_score']}")
                print(f"      Normalized score: {match['normalized_score']:.3f}")
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
        print(f"  Total images in database: {stats['database_stats']['total_images']}")
        print(f"  Total objects in database: {stats['database_stats']['total_objects']}")
        print(f"  Average keypoints per object: {stats['database_stats']['avg_keypoints']}")
        print(f"  Class distribution:")
        for class_name, count in stats['database_stats']['class_counts'].items():
            print(f"    {class_name}: {count}")


if __name__ == "__main__":
    main()