# YOLO 11 Training Script
# This script provides training functionality for YOLO 11 custom object detection

import os
import yaml
import torch
from pathlib import Path
from ultralytics import YOLO
import argparse
from typing import List, Dict, Optional


class YOLO11Trainer:
    """
    YOLO 11 Training class for custom object detection
    """

    def __init__(self, model_size: str = "n"):
        """
        Initialize the YOLO 11 trainer

        Args:
            model_size (str): Model size ('n', 's', 'm', 'l', 'x')
        """
        self.model_size = model_size.lower()
        if self.model_size not in ['n', 's', 'm', 'l', 'x']:
            raise ValueError("Model size must be one of: 'n', 's', 'm', 'l', 'x'")

        self.model = YOLO(f"yolo11{self.model_size}.pt")
        print(f"Initialized YOLO11{self.model_size.upper()} model")

    def create_dataset_yaml(self, dataset_path: str, class_names: List[str],
                            output_path: str = "dataset.yaml") -> str:
        """
        Create dataset configuration YAML file

        Args:
            dataset_path (str): Path to the dataset directory
            class_names (List[str]): List of class names
            output_path (str): Path to save the YAML file

        Returns:
            str: Path to the created YAML file
        """
        dataset_config = {
            'path': os.path.abspath(dataset_path),
            'train': 'train/images',
            'val': 'val/images',
            'test': 'test/images',
            'nc': len(class_names),
            'names': class_names
        }

        with open(output_path, 'w') as f:
            yaml.dump(dataset_config, f, default_flow_style=False)

        print(f"Dataset YAML created at: {output_path}")
        print(f"Number of classes: {len(class_names)}")
        print(f"Classes: {class_names}")
        return output_path

    def train(self, dataset_yaml: str, epochs: int = 100, imgsz: int = 640,
              batch_size: int = 16, device: str = "auto", project: str = "runs/train",
              name: str = "yolo11_custom", **kwargs) -> dict:
        """
        Train the YOLO 11 model

        Args:
            dataset_yaml (str): Path to dataset YAML file
            epochs (int): Number of training epochs
            imgsz (int): Input image size
            batch_size (int): Batch size
            device (str): Device to use ('cpu', 'cuda', 'auto')
            project (str): Project directory
            name (str): Run name
            **kwargs: Additional training parameters

        Returns:
            dict: Training results
        """
        print("\n" + "=" * 50)
        print("STARTING YOLO 11 TRAINING")
        print("=" * 50)
        print(f"Model size: YOLO11{self.model_size.upper()}")
        print(f"Dataset: {dataset_yaml}")
        print(f"Epochs: {epochs}")
        print(f"Image size: {imgsz}")
        print(f"Batch size: {batch_size}")
        print(f"Device: {device}")
        print(f"Project: {project}")
        print(f"Name: {name}")
        print("=" * 50)

        # Validate dataset YAML exists
        if not os.path.exists(dataset_yaml):
            raise FileNotFoundError(f"Dataset YAML file not found: {dataset_yaml}")

        # Default training parameters
        training_params = {
            'data': dataset_yaml,
            'epochs': epochs,
            'imgsz': imgsz,
            'batch': batch_size,
            'device': device,
            'project': project,
            'name': name,
            'patience': 50,
            'save': True,
            'save_period': 10,
            'cache': True,
            'plots': True,
            'verbose': True,
            'val': True,
            'lr0': 0.01,
            'lrf': 0.01,
            'momentum': 0.937,
            'weight_decay': 0.0005,
            'warmup_epochs': 3,
            'warmup_momentum': 0.8,
            'warmup_bias_lr': 0.1,
            'box': 7.5,
            'cls': 0.5,
            'dfl': 1.5,
            'pose': 12.0,
            'kobj': 1.0,
            'label_smoothing': 0.0,
            'nbs': 64,
            'overlap_mask': True,
            'mask_ratio': 4,
            'dropout': 0.0,
            'amp': True
        }

        # Update with any additional parameters
        training_params.update(kwargs)

        try:
            # Start training
            results = self.model.train(**training_params)
            print("\n" + "=" * 50)
            print("TRAINING COMPLETED SUCCESSFULLY!")
            print("=" * 50)
            return results
        except Exception as e:
            print(f"\nTraining failed with error: {e}")
            raise

    def validate(self, dataset_yaml: str, model_path: str = None, **kwargs) -> dict:
        """
        Validate the trained model

        Args:
            dataset_yaml (str): Path to dataset YAML file
            model_path (str): Path to trained model weights (optional)
            **kwargs: Additional validation parameters

        Returns:
            dict: Validation results
        """
        if model_path:
            model = YOLO(model_path)
            print(f"Validating model: {model_path}")
        else:
            model = self.model
            print("Validating current model")

        validation_params = {
            'data': dataset_yaml,
            'verbose': True,
            'plots': True
        }
        validation_params.update(kwargs)

        results = model.val(**validation_params)
        print("Validation completed!")
        return results

    def resume_training(self, checkpoint_path: str) -> dict:
        """
        Resume training from a checkpoint

        Args:
            checkpoint_path (str): Path to the checkpoint file

        Returns:
            dict: Training results
        """
        print(f"Resuming training from checkpoint: {checkpoint_path}")

        if not os.path.exists(checkpoint_path):
            raise FileNotFoundError(f"Checkpoint file not found: {checkpoint_path}")

        results = self.model.train(resume=True, model=checkpoint_path)
        print("Training resumed and completed!")
        return results

    def export_model(self, model_path: str, format: str = "onnx", **kwargs) -> str:
        """
        Export trained model to different formats

        Args:
            model_path (str): Path to trained model weights
            format (str): Export format ('onnx', 'torchscript', 'tflite', etc.)
            **kwargs: Additional export parameters

        Returns:
            str: Path to exported model
        """
        model = YOLO(model_path)
        print(f"Exporting model to {format.upper()} format...")

        export_params = {
            'format': format,
            'dynamic': True,
            'simplify': True
        }
        export_params.update(kwargs)

        exported_path = model.export(**export_params)
        print(f"Model exported to: {exported_path}")
        return exported_path


def prepare_dataset_structure(base_path: str) -> None:
    """
    Create the required directory structure for YOLO training

    Args:
        base_path (str): Base path for the dataset
    """
    directories = [
        "train/images",
        "train/labels",
        "val/images",
        "val/labels",
        "test/images",
        "test/labels"
    ]

    for directory in directories:
        Path(os.path.join(base_path, directory)).mkdir(parents=True, exist_ok=True)

    print(f"Dataset structure created at: {base_path}")
    print("Directory structure:")
    for directory in directories:
        print(f"  - {directory}")


def convert_annotations_to_yolo(annotations: List[Dict], image_width: int,
                                image_height: int) -> List[str]:
    """
    Convert bounding box annotations to YOLO format

    Args:
        annotations (List[Dict]): List of annotations with 'class_id' and 'bbox' keys
        image_width (int): Width of the image
        image_height (int): Height of the image

    Returns:
        List[str]: List of YOLO format annotation strings
    """
    yolo_annotations = []

    for annotation in annotations:
        class_id = annotation['class_id']
        x1, y1, x2, y2 = annotation['bbox']

        # Convert to YOLO format (normalized center coordinates and dimensions)
        center_x = (x1 + x2) / 2.0 / image_width
        center_y = (y1 + y2) / 2.0 / image_height
        width = (x2 - x1) / image_width
        height = (y2 - y1) / image_height

        yolo_annotation = f"{class_id} {center_x:.6f} {center_y:.6f} {width:.6f} {height:.6f}"
        yolo_annotations.append(yolo_annotation)

    return yolo_annotations


def validate_dataset_structure(dataset_path: str) -> bool:
    """
    Validate that the dataset has the correct structure

    Args:
        dataset_path (str): Path to the dataset directory

    Returns:
        bool: True if structure is valid, False otherwise
    """
    required_dirs = [
        "train/images",
        "train/labels",
        "val/images",
        "val/labels"
    ]

    for directory in required_dirs:
        dir_path = os.path.join(dataset_path, directory)
        if not os.path.exists(dir_path):
            print(f"Missing directory: {dir_path}")
            return False

    # Check if directories contain files
    train_images = len(os.listdir(os.path.join(dataset_path, "train/images")))
    train_labels = len(os.listdir(os.path.join(dataset_path, "train/labels")))
    val_images = len(os.listdir(os.path.join(dataset_path, "val/images")))
    val_labels = len(os.listdir(os.path.join(dataset_path, "val/labels")))

    print(f"Dataset validation:")
    print(f"  Train images: {train_images}")
    print(f"  Train labels: {train_labels}")
    print(f"  Val images: {val_images}")
    print(f"  Val labels: {val_labels}")

    if train_images == 0 or val_images == 0:
        print("Error: No images found in train or val directories")
        return False

    return True


def main():
    """
    Main function to run the training script
    """
    parser = argparse.ArgumentParser(description="YOLO 11 Training Script")
    parser.add_argument("--mode", choices=["train", "validate", "resume", "export"],
                        default="train", help="Training mode")
    parser.add_argument("--dataset", type=str, required=True,
                        help="Path to dataset YAML file")
    parser.add_argument("--model-size", type=str, default="n",
                        choices=["n", "s", "m", "l", "x"],
                        help="Model size (n=nano, s=small, m=medium, l=large, x=extra-large)")
    parser.add_argument("--epochs", type=int, default=100,
                        help="Number of training epochs")
    parser.add_argument("--imgsz", type=int, default=640,
                        help="Input image size")
    parser.add_argument("--batch", type=int, default=16,
                        help="Batch size")
    parser.add_argument("--device", type=str, default="auto",
                        help="Device to use (cpu, cuda, auto)")
    parser.add_argument("--project", type=str, default="runs/train",
                        help="Project directory")
    parser.add_argument("--name", type=str, default="yolo11_custom",
                        help="Run name")
    parser.add_argument("--model-path", type=str,
                        help="Path to model weights (for validation/export)")
    parser.add_argument("--checkpoint", type=str,
                        help="Path to checkpoint file (for resume)")
    parser.add_argument("--export-format", type=str, default="onnx",
                        help="Export format (onnx, torchscript, tflite, etc.)")

    args = parser.parse_args()

    # Initialize trainer
    trainer = YOLO11Trainer(model_size=args.model_size)

    if args.mode == "train":
        # Validate dataset structure
        dataset_dir = os.path.dirname(args.dataset)
        if dataset_dir and not validate_dataset_structure(dataset_dir):
            print("Dataset structure validation failed!")
            return

        # Start training
        results = trainer.train(
            dataset_yaml=args.dataset,
            epochs=args.epochs,
            imgsz=args.imgsz,
            batch_size=args.batch,
            device=args.device,
            project=args.project,
            name=args.name
        )

    elif args.mode == "validate":
        if not args.model_path:
            print("Error: --model-path is required for validate mode")
            return

        results = trainer.validate(args.dataset, args.model_path)

    elif args.mode == "resume":
        if not args.checkpoint:
            print("Error: --checkpoint is required for resume mode")
            return

        results = trainer.resume_training(args.checkpoint)

    elif args.mode == "export":
        if not args.model_path:
            print("Error: --model-path is required for export mode")
            return

        exported_path = trainer.export_model(args.model_path, args.export_format)
        print(f"Model exported to: {exported_path}")


if __name__ == "__main__":
    # Example usage without command line arguments
    if len(os.sys.argv) == 1:
        print("YOLO 11 Training Script")
        print("\nExample Usage:")
        print("1. Train a model:")
        print("   python yolo11_trainer.py --mode train --dataset dataset.yaml --epochs 100 --batch 16")
        print("\n2. Validate a trained model:")
        print("   python yolo11_trainer.py --mode validate --dataset dataset.yaml --model-path best.pt")
        print("\n3. Resume training from checkpoint:")
        print("   python yolo11_trainer.py --mode resume --checkpoint last.pt")
        print("\n4. Export trained model:")
        print("   python yolo11_trainer.py --mode export --model-path best.pt --export-format onnx")
        print("\nFor direct use in code:")
        print("   trainer = YOLO11Trainer('n')")
        print("   trainer.create_dataset_yaml('dataset/', ['class1', 'class2'])")
        print("   trainer.train('dataset.yaml', epochs=100)")
    else:
        main()