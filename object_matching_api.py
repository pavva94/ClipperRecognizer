#!/usr/bin/env python3
"""
FastAPI REST API for Object Matching Application
Provides endpoints for database loading, querying, and statistics
"""

from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks, Form, Query
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
import os
import shutil
import tempfile
import zipfile
from pathlib import Path
import uvicorn
import asyncio
from datetime import datetime
import json
import logging

# Import the original classes (assuming they're in the same directory)
from object_matching import ObjectMatchingApp, DatabaseManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Object Matching API",
    description="REST API for YOLO + SIFT object matching system",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global variables
object_matching_app = None
background_tasks_status = {}

model_best = "runs/train/yolo11_custom/weights/best.pt"


# Pydantic models
class DatabaseLoadRequest(BaseModel):
    confidence_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    max_workers: int = Field(default=4, ge=1, le=16)
    target_class: str = Field(default="clipper")
    model_path: str = Field(default=model_best)


class QueryRequest(BaseModel):
    confidence_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    top_k: int = Field(default=10, ge=1, le=100)
    object_class: Optional[str] = None


class MatchResult(BaseModel):
    object_id: int
    similarity_score: int
    normalized_score: float
    matches_count: int
    object_class: str
    confidence: float
    original_filename: str
    original_filepath: str
    object_image_path: str
    keypoints_count: int


class DatabaseStats(BaseModel):
    total_images: int
    total_objects: int
    class_counts: Dict[str, int]
    avg_keypoints: float


class AppStats(BaseModel):
    database_stats: DatabaseStats
    target_class: str
    extracted_objects_dir: str
    query_objects_dir: str


class TaskStatus(BaseModel):
    task_id: str
    status: str  # "running", "completed", "failed"
    progress: Optional[Dict[str, Any]] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None


# Helper functions
def get_app_instance(model_path: str = model_best, target_class: str = "clipper") -> ObjectMatchingApp:
    """Get or create ObjectMatchingApp instance"""
    global object_matching_app

    if object_matching_app is None or object_matching_app.target_class != target_class:
        object_matching_app = ObjectMatchingApp(model_path, target_class)

    return object_matching_app


def save_uploaded_file(upload_file: UploadFile, destination: str) -> str:
    """Save uploaded file to destination"""
    try:
        with open(destination, "wb") as buffer:
            shutil.copyfileobj(upload_file.file, buffer)
        return destination
    except Exception as e:
        logger.error(f"Error saving file: {e}")
        raise HTTPException(status_code=500, detail=f"Error saving file: {str(e)}")


def extract_zip_file(zip_path: str, extract_to: str) -> List[str]:
    """Extract zip file and return list of image files"""
    image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp'}
    image_files = []

    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_to)

        # Find all image files in extracted directory
        for root, dirs, files in os.walk(extract_to):
            for file in files:
                if Path(file).suffix.lower() in image_extensions:
                    image_files.append(os.path.join(root, file))

        return image_files
    except Exception as e:
        logger.error(f"Error extracting zip file: {e}")
        raise HTTPException(status_code=500, detail=f"Error extracting zip file: {str(e)}")


async def background_database_load(task_id: str, images_directory: str,
                                   confidence_threshold: float, max_workers: int,
                                   model_path: str, target_class: str):
    """Background task for database loading"""
    try:
        background_tasks_status[task_id]["status"] = "running"
        background_tasks_status[task_id]["progress"] = {"stage": "initializing"}

        # Initialize app
        app_instance = get_app_instance(model_path, target_class)

        background_tasks_status[task_id]["progress"] = {"stage": "processing_images"}

        # Load database
        stats = app_instance.load_database(images_directory, confidence_threshold, max_workers)

        background_tasks_status[task_id]["status"] = "completed"
        background_tasks_status[task_id]["result"] = stats
        background_tasks_status[task_id]["completed_at"] = datetime.now()

    except Exception as e:
        logger.error(f"Background task {task_id} failed: {e}")
        background_tasks_status[task_id]["status"] = "failed"
        background_tasks_status[task_id]["error"] = str(e)
        background_tasks_status[task_id]["completed_at"] = datetime.now()


# API Endpoints

@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": "Object Matching API",
        "version": "1.0.0",
        "endpoints": {
            "load_database_from_directory": "/database/load-from-directory",
            "load_database_from_zip": "/database/load-from-zip",
            "query_object": "/query",
            "get_stats": "/stats",
            "get_tasks": "/tasks",
            "list_objects": "/database/objects",
            "health": "/health"
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@app.post("/database/load-from-directory")
async def load_database_from_directory(
        background_tasks: BackgroundTasks,
        images_directory: str = Form(...),
        confidence_threshold: float = Form(0.5),
        max_workers: int = Form(4),
        target_class: str = Form("clipper"),
        model_path: str = Form(model_best)
):
    """Load database from local directory (async)"""
    if not os.path.exists(images_directory):
        raise HTTPException(status_code=404, detail="Images directory not found")

    # Generate task ID
    task_id = f"load_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{len(background_tasks_status)}"

    # Initialize task status
    background_tasks_status[task_id] = {
        "task_id": task_id,
        "status": "queued",
        "progress": None,
        "result": None,
        "error": None,
        "created_at": datetime.now(),
        "completed_at": None
    }

    # Add background task
    background_tasks.add_task(
        background_database_load,
        task_id, images_directory, confidence_threshold, max_workers, model_path, target_class
    )

    return {
        "task_id": task_id,
        "status": "queued",
        "message": "Database loading started in background",
        "status_url": f"/tasks/{task_id}"
    }


@app.post("/database/load-from-zip")
async def load_database_from_zip(
        background_tasks: BackgroundTasks,
        zip_file: UploadFile = File(...),
        confidence_threshold: float = Form(0.5),
        max_workers: int = Form(4),
        target_class: str = Form("clipper"),
        model_path: str = Form(model_best)
):
    """Load database from uploaded zip file (async)"""
    if not zip_file.filename.endswith('.zip'):
        raise HTTPException(status_code=400, detail="Only ZIP files are supported")

    # Create temporary directory
    temp_dir = tempfile.mkdtemp(prefix="object_matching_")
    zip_path = os.path.join(temp_dir, "images.zip")
    extract_dir = os.path.join(temp_dir, "extracted")

    try:
        # Save uploaded zip file
        save_uploaded_file(zip_file, zip_path)

        # Extract zip file
        os.makedirs(extract_dir, exist_ok=True)
        image_files = extract_zip_file(zip_path, extract_dir)

        if not image_files:
            shutil.rmtree(temp_dir)
            raise HTTPException(status_code=400, detail="No image files found in zip")

        # Generate task ID
        task_id = f"load_zip_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{len(background_tasks_status)}"

        # Initialize task status
        background_tasks_status[task_id] = {
            "task_id": task_id,
            "status": "queued",
            "progress": None,
            "result": None,
            "error": None,
            "created_at": datetime.now(),
            "completed_at": None
        }

        # Add background task
        background_tasks.add_task(
            background_database_load,
            task_id, extract_dir, confidence_threshold, max_workers, model_path, target_class
        )

        return {
            "task_id": task_id,
            "status": "queued",
            "message": f"Database loading started from zip file with {len(image_files)} images",
            "status_url": f"/tasks/{task_id}"
        }

    except Exception as e:
        shutil.rmtree(temp_dir)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/tasks/{task_id}", response_model=TaskStatus)
async def get_task_status(task_id: str):
    """Get status of background task"""
    if task_id not in background_tasks_status:
        raise HTTPException(status_code=404, detail="Task not found")

    task_status = background_tasks_status[task_id]
    return TaskStatus(**task_status)


@app.get("/tasks")
async def list_tasks():
    """List all background tasks"""
    return {
        "tasks": list(background_tasks_status.keys()),
        "total": len(background_tasks_status)
    }


@app.post("/query", response_model=List[MatchResult])
async def query_object(
        query_image: UploadFile = File(...),
        confidence_threshold: float = Form(0.5),
        top_k: int = Form(10),
        object_class: Optional[str] = Form(None),
        target_class: str = Form("clipper"),
        model_path: str = Form(model_best)
):
    """Query database with uploaded image"""
    if not query_image.filename.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp')):
        raise HTTPException(status_code=400, detail="Unsupported image format")

    # Create temporary file for query image
    temp_dir = tempfile.mkdtemp(prefix="query_")
    query_path = os.path.join(temp_dir, f"query_{query_image.filename}")

    try:
        # Save query image
        save_uploaded_file(query_image, query_path)

        # Get app instance
        app_instance = get_app_instance(model_path, target_class)

        # Perform query
        matches = app_instance.query_object(query_path, confidence_threshold, top_k, object_class)

        print(matches)
        logger.warning(matches)

        # Convert to response format
        results = []
        for match in matches:
            results.append(MatchResult(**match))
        logger.warning(results)
        return results

    except Exception as e:
        logger.error(f"Query error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        # Clean up temporary files
        shutil.rmtree(temp_dir)


@app.get("/stats", response_model=AppStats)
async def get_statistics(
        target_class: str = Query("clipper"),
        model_path: str = Query(model_best)
):
    """Get application statistics"""
    try:
        app_instance = get_app_instance(model_path, target_class)
        stats = app_instance.get_stats()

        return AppStats(
            database_stats=DatabaseStats(**stats['database_stats']),
            target_class=stats['target_class'],
            extracted_objects_dir=stats['extracted_objects_dir'],
            query_objects_dir=stats['query_objects_dir']
        )
    except Exception as e:
        logger.error(f"Stats error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/database/objects")
async def list_database_objects(
        object_class: Optional[str] = Query(None),
        min_keypoints: int = Query(10),
        limit: int = Query(100),
        offset: int = Query(0)
):
    """List objects in database with pagination"""
    try:
        db_manager = DatabaseManager()

        # Ensure database schema is up to date
        db_manager.init_database()

        all_objects = db_manager.get_all_objects(object_class, min_keypoints)

        # Apply pagination
        paginated_objects = all_objects[offset:offset + limit]

        # Remove binary data for API response
        for obj in paginated_objects:
            obj.pop('descriptors', None)
            obj.pop('keypoints', None)

        return {
            "objects": paginated_objects,
            "total": len(all_objects),
            "limit": limit,
            "offset": offset,
            "has_more": offset + limit < len(all_objects)
        }
    except Exception as e:
        logger.error(f"List objects error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/database/objects/{object_id}/image")
async def get_object_image(object_id: int):
    """Get extracted object image by ID"""
    try:
        db_manager = DatabaseManager()
        objects = db_manager.get_all_objects()

        # Find object by ID
        target_object = None
        for obj in objects:
            if obj['id'] == object_id:
                target_object = obj
                break

        if not target_object:
            raise HTTPException(status_code=404, detail="Object not found")

        image_path = target_object['object_image_path']
        if not os.path.exists(image_path):
            raise HTTPException(status_code=404, detail="Object image file not found")

        return FileResponse(
            image_path,
            media_type="image/jpeg",
            filename=f"object_{object_id}.jpg"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get object image error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/database/clear")
async def clear_database():
    """Clear all data from database"""
    try:
        db_manager = DatabaseManager()

        # Remove database file
        if os.path.exists(db_manager.db_path):
            os.remove(db_manager.db_path)

        # Recreate database
        db_manager.init_database()

        # Clear extracted objects directory
        extracted_dir = "extracted_objects"
        if os.path.exists(extracted_dir):
            shutil.rmtree(extracted_dir)
            os.makedirs(extracted_dir)

        return {"message": "Database cleared successfully"}

    except Exception as e:
        logger.error(f"Clear database error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/models")
async def list_available_models():
    """List available YOLO models"""
    # Common YOLO model names
    models = [
        model_best,
        "yolo11n.pt",
        "yolo11s.pt",
        "yolo11m.pt",
        "yolo11l.pt",
        "yolo11x.pt"
    ]

    return {"available_models": models}


@app.get("/classes")
async def list_available_classes():
    """List available object classes"""
    try:
        # Get classes from YOLO model
        from ultralytics import YOLO
        model = YOLO("yolo11n.pt")
        classes = {int(k): v for k, v in model.names.items()}

        return {"available_classes": classes}

    except Exception as e:
        logger.error(f"List classes error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Object Matching API Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    parser.add_argument("--workers", type=int, default=1, help="Number of worker processes")

    args = parser.parse_args()

    uvicorn.run(
        "object_matching_api:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        workers=args.workers
    )