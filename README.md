# Object Matching Application

A powerful computer vision application that combines **YOLO 11** object detection with **DINOv2** feature extraction to create a robust object matching system. This application allows you to build a database of objects from images and then query similar objects using deep learning-based feature matching.

## Features

- **Object Detection**: Uses YOLO 11 for accurate object detection
- **Deep Feature Extraction**: Leverages DINOv2 (Vision Transformer) for high-quality feature vectors
- **Database Management**: SQLite-based storage for efficient object and feature management
- **Similarity Search**: Cosine similarity-based matching for finding similar objects
- **Parallel Processing**: Multi-threaded processing for faster database creation
- **Flexible Querying**: Support for class-based filtering and similarity thresholds
- **Command Line Interface**: Easy-to-use CLI for batch processing and queries

## Architecture

The application consists of several key components:

1. **DatabaseManager**: Handles SQLite database operations for storing object metadata and features
2. **DINOv2FeatureExtractor**: Extracts deep learning features using Facebook's DINOv2 model
3. **DeepFeatureMatcher**: Performs similarity matching using cosine similarity
4. **ObjectMatchingApp**: Main application orchestrating the entire workflow

## Installation

### Prerequisites

- Python 3.8 or higher
- CUDA-compatible GPU (recommended for better performance)

### Required Dependencies

```bash
pip install ultralytics torch torchvision opencv-python numpy scikit-learn
pip install pillow pathlib tqdm sqlite3 pickle logging argparse
```

### Additional Setup

The application will automatically download the DINOv2 model from PyTorch Hub on first run.

## Usage

The application operates in three main modes:

### 1. Database Loading Mode

Process a directory of images to extract objects and build the feature database:

```bash
python object_matching.py --mode load --images-dir /path/to/images --class person --confidence 0.5
```

**Parameters:**
- `--images-dir`: Directory containing images to process
- `--class`: Target object class (e.g., "person", "car", "bicycle")
- `--confidence`: Minimum detection confidence threshold (0.0-1.0)
- `--workers`: Number of parallel workers for processing

### 2. Query Mode

Search for similar objects using a query image:

```bash
python object_matching.py --mode query --query-image /path/to/query.jpg --top-k 10 --similarity 0.5
```

**Parameters:**
- `--query-image`: Path to the query image
- `--top-k`: Number of top matches to return
- `--similarity`: Minimum similarity threshold (0.0-1.0)

### 3. Statistics Mode

View database and application statistics:

```bash
python object_matching.py --mode stats
```

## Configuration Options

### YOLO Model Selection
```bash
--model yolo11n.pt    # Nano (fastest)
--model yolo11s.pt    # Small
--model yolo11m.pt    # Medium
--model yolo11l.pt    # Large
--model yolo11x.pt    # Extra Large (most accurate)
```

### DINOv2 Model Variants
```bash
--feature-model dinov2_vits14    # Small (384 dim) - Default
--feature-model dinov2_vitb14    # Base (768 dim)
--feature-model dinov2_vitl14    # Large (1024 dim)
--feature-model dinov2_vitg14    # Giant (1536 dim)
```

### Advanced Features
```bash
--patch-features    # Enable patch token features for more detailed representation
```

## Examples

### Complete Workflow Example

1. **Build a person database from a photo collection:**
```bash
python object_matching.py --mode load --images-dir ./photos --class person --confidence 0.6 --workers 4
```

2. **Query for similar people:**
```bash
python object_matching.py --mode query --query-image ./query_person.jpg --top-k 5 --similarity 0.7
```

3. **Check database statistics:**
```bash
python object_matching.py --mode stats
```

### Sample Output

**Database Loading:**
```
Database Loading Results:
  Total images: 1000
  Processed images: 987
  Total objects extracted: 2341
  Failed images: 13
  Processing time: 245.67 seconds
```

**Query Results:**
```
Top 5 matches:
  1. IMG_2023_001.jpg
      Similarity score: 0.892
      Object class: person
      Confidence: 0.87
      Original image: /photos/IMG_2023_001.jpg

  2. portrait_045.jpg
      Similarity score: 0.834
      Object class: person
      Confidence: 0.92
      Original image: /photos/portrait_045.jpg
```

## Database Schema

The application uses SQLite with the following schema:

### Images Table
- `id`: Primary key
- `filename`: Original filename
- `filepath`: Full file path
- `created_at`: Timestamp

### Objects Table
- `id`: Primary key
- `image_id`: Foreign key to images table
- `object_class`: Detected object class
- `confidence`: Detection confidence score
- `bbox_x1`, `bbox_y1`, `bbox_x2`, `bbox_y2`: Bounding box coordinates
- `object_image_path`: Path to extracted object image
- `feature_vector`: Serialized DINOv2 features (BLOB)
- `feature_dim`: Feature vector dimension
- `created_at`: Timestamp

## Performance Considerations

### GPU Usage
- DINOv2 feature extraction benefits significantly from GPU acceleration
- Automatic detection of CUDA availability
- Parallel processing is limited on GPU to prevent memory issues

### Memory Management
- Features are stored as compressed BLOB data in SQLite
- Large databases may require substantial disk space
- Consider using smaller DINOv2 models for memory-constrained environments

### Processing Speed
- YOLO 11 Nano: ~50-100 images/minute (CPU)
- DINOv2 feature extraction: ~10-30 objects/second (GPU)
- Database queries: Near real-time for thousands of objects

## Supported Image Formats

- JPEG (.jpg, .jpeg)
- PNG (.png)
- BMP (.bmp)
- TIFF (.tiff)
- WebP (.webp)

## Output Structure

```
project_directory/
├── object_features.db          # SQLite database
├── extracted_objects/          # Individual object images
│   ├── img001_obj_001_conf0.85.jpg
│   ├── img001_obj_002_conf0.92.jpg
│   └── ...
├── query_objects/             # Query object images
├── object_matching.log        # Application logs
└── object_matching.py         # Main application
```

## Troubleshooting

### Common Issues

1. **CUDA Out of Memory**
   - Reduce batch size or use smaller DINOv2 model
   - Limit number of parallel workers: `--workers 1`

2. **No Objects Detected**
   - Lower confidence threshold: `--confidence 0.3`
   - Verify target class name matches YOLO classes

3. **Poor Matching Results**
   - Increase similarity threshold: `--similarity 0.7`
   - Try different DINOv2 model variants
   - Enable patch features: `--patch-features`

### Model Downloads

DINOv2 models are downloaded automatically from PyTorch Hub. If you encounter download issues:
- Ensure internet connection
- Check firewall settings
- Consider manual model download

## Advanced Usage

### Custom Object Classes

YOLO 11 supports 80 object classes from COCO dataset:
- person, bicycle, car, motorcycle, airplane, bus, train, truck
- traffic light, fire hydrant, stop sign, parking meter, bench
- cat, dog, horse, sheep, cow, elephant, bear, zebra, giraffe
- And many more...

### Batch Processing Scripts

For large-scale processing, consider creating wrapper scripts:

```python
import subprocess
import os

def process_directory_batch(base_dir, class_name):
    for subdir in os.listdir(base_dir):
        if os.path.isdir(os.path.join(base_dir, subdir)):
            cmd = [
                "python", "object_matching.py",
                "--mode", "load",
                "--images-dir", os.path.join(base_dir, subdir),
                "--class", class_name,
                "--confidence", "0.6"
            ]
            subprocess.run(cmd)
```

## License

This project uses several open-source components:
- YOLO 11 by Ultralytics
- DINOv2 by Facebook Research
- Various Python libraries with their respective licenses


## Future Enhancements

- Support for video processing
- Web-based interface
- Real-time object tracking
- Integration with cloud storage
- Export capabilities for analysis tools