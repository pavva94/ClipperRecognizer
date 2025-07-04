# Object Matching Application using YOLO 11 and SIFT

A powerful computer vision application that combines YOLO 11 object detection with SIFT feature extraction for robust object matching and retrieval. The application can process batches of images to build a searchable database of objects and then match query objects against this database.

## Features

- **Object Detection**: Uses YOLO 11 for accurate object detection with configurable confidence thresholds
- **Feature Extraction**: Employs SIFT (Scale-Invariant Feature Transform) for robust feature extraction
- **Database Storage**: SQLite database for efficient storage and retrieval of object features
- **Feature Matching**: FLANN-based matching for fast similarity search
- **Parallel Processing**: Multi-threaded batch processing for efficient database building
- **Command Line Interface**: Easy-to-use CLI for all operations
- **Comprehensive Logging**: Detailed logging for monitoring and debugging

## Installation

### Prerequisites

- Python 3.8 or higher
- OpenCV 4.x
- CUDA-compatible GPU (optional, for faster YOLO inference)

### Dependencies

Install the required packages:

```bash
pip install ultralytics opencv-python numpy sqlite3 pathlib tqdm
```

Or install from requirements.txt:

```bash
pip install -r requirements.txt
```

### YOLO Model

The application will automatically download the YOLO 11 model (`yolo11n.pt`) on first run. You can also specify a custom model path.

## Usage

The application operates in three main modes:

### 1. Database Loading Mode

Process a batch of images to extract objects and build the feature database:

```bash
python object_matching.py --mode load --images-dir /path/to/images --class person --confidence 0.5 --workers 4
```

**Parameters:**
- `--images-dir`: Directory containing images to process
- `--class`: Target object class (default: "person")
- `--confidence`: Minimum confidence threshold (default: 0.5)
- `--workers`: Number of parallel workers (default: 4)

### 2. Query Mode

Search for similar objects using a query image:

```bash
python object_matching.py --mode query --query-image /path/to/query.jpg --confidence 0.5 --top-k 10
```

**Parameters:**
- `--query-image`: Path to the query image
- `--confidence`: Minimum confidence threshold (default: 0.5)
- `--top-k`: Number of top matches to return (default: 10)

### 3. Statistics Mode

View database statistics and information:

```bash
python object_matching.py --mode stats
```

### Complete Example

```bash
# 1. Build database from images
python object_matching.py --mode load --images-dir ./training_images --class person --confidence 0.6

# 2. Query the database
python object_matching.py --mode query --query-image ./query.jpg --top-k 5

# 3. View statistics
python object_matching.py --mode stats
```

## Application Architecture

### Components

1. **DatabaseManager**: Handles SQLite database operations
   - Stores image metadata and object features
   - Manages keypoint serialization/deserialization
   - Provides efficient querying capabilities

2. **SIFTFeatureExtractor**: Extracts SIFT features from image regions
   - Configurable number of features
   - Robust to scale and rotation changes

3. **FLANNMatcher**: Fast feature matching using FLANN
   - KD-tree based indexing for speed
   - Lowe's ratio test for match quality

4. **ObjectMatchingApp**: Main application orchestrator
   - Coordinates all components
   - Handles parallel processing
   - Manages file operations

### Database Schema

The application uses two main tables:

**Images Table:**
- `id`: Primary key
- `filename`: Original filename
- `filepath`: Full file path
- `upload_date`: Processing timestamp
- `processed`: Processing status

**Objects Table:**
- `id`: Primary key
- `image_id`: Foreign key to images table
- `object_class`: Detected object class
- `confidence`: Detection confidence
- `bbox_*`: Bounding box coordinates
- `object_image_path`: Path to extracted object image
- `keypoints_count`: Number of SIFT keypoints
- `descriptors`: SIFT descriptors (BLOB)
- `keypoints`: SIFT keypoints (BLOB)

## Output Structure

The application creates the following directory structure:

```
project_root/
├── object_matching.py
├── object_features.db          # SQLite database
├── object_matching.log         # Application logs
├── extracted_objects/          # Extracted object images
│   ├── image1_obj_001_conf0.85.jpg
│   ├── image1_obj_002_conf0.72.jpg
│   └── ...
└── query_objects/              # Query-related files
```

## Configuration Options

### YOLO Model Options

- `yolo11n.pt`: Nano model (fastest, least accurate)
- `yolo11s.pt`: Small model (balanced)
- `yolo11m.pt`: Medium model (more accurate)
- `yolo11l.pt`: Large model (most accurate, slowest)

### Supported Object Classes

The application supports all YOLO 11 object classes:
- person, bicycle, car, motorcycle, airplane, bus, train, truck
- boat, traffic light, fire hydrant, stop sign, parking meter
- And many more...

### Supported Image Formats

- JPEG (.jpg, .jpeg)
- PNG (.png)
- BMP (.bmp)
- TIFF (.tiff)
- WebP (.webp)

## Performance Tuning

### For Large Datasets

1. **Increase worker count** for parallel processing:
   ```bash
   --workers 8
   ```

2. **Adjust SIFT parameters** by modifying `SIFTFeatureExtractor`:
   ```python
   self.sift = cv2.SIFT_create(nfeatures=3000)  # Reduce features for speed
   ```

3. **Use GPU acceleration** with YOLO:
   ```bash
   # Ensure CUDA is available
   python -c "import torch; print(torch.cuda.is_available())"
   ```

### For Better Accuracy

1. **Lower confidence threshold**:
   ```bash
   --confidence 0.3
   ```

2. **Increase SIFT features**:
   ```python
   self.sift = cv2.SIFT_create(nfeatures=8000)
   ```

3. **Use larger YOLO model**:
   ```bash
   --model yolo11l.pt
   ```

## Troubleshooting

### Common Issues

1. **"cannot pickle 'cv2.KeyPoint' object"**
   - This is fixed in the current version through keypoint serialization

2. **"No objects detected"**
   - Lower the confidence threshold
   - Check if the target class is present in images
   - Verify image quality and format

3. **"FLANN matching error"**
   - Ensure sufficient keypoints are extracted
   - Check descriptor compatibility

4. **Memory issues with large datasets**
   - Reduce batch size by decreasing worker count
   - Process images in smaller chunks

### Logging

Check the `object_matching.log` file for detailed execution logs:

```bash
tail -f object_matching.log
```

## API Reference

### DatabaseManager

```python
db = DatabaseManager("custom_db.db")
image_id = db.add_image(filename, filepath)
object_id = db.add_object(image_id, object_data)
objects = db.get_all_objects(object_class="person", min_keypoints=10)
stats = db.get_database_stats()
```

### ObjectMatchingApp

```python
app = ObjectMatchingApp(model_path="yolo11n.pt", target_class="person")
stats = app.load_database(images_dir, confidence_threshold=0.5)
matches = app.query_object(query_image_path, top_k=10)
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- [Ultralytics](https://github.com/ultralytics/ultralytics) for YOLO 11
- [OpenCV](https://opencv.org/) for computer vision operations
- [SIFT](https://en.wikipedia.org/wiki/Scale-invariant_feature_transform) algorithm by David Lowe

