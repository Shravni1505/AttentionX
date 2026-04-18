"""
AttentionX - FastAPI Server
Main entry point for the AttentionX API and web frontend.

Endpoints:
  POST /api/upload          - Upload a video file
  POST /api/process/{id}    - Start processing pipeline
  GET  /api/status/{id}     - SSE stream for processing status
  GET  /api/clips/{id}      - List generated clips
  GET  /api/download/{id}/{f} - Download a clip file
  GET  /                    - Serve frontend
"""

import os
import uuid
import json
import asyncio
import threading
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Create required directories
os.makedirs("uploads", exist_ok=True)
os.makedirs("output", exist_ok=True)

app = FastAPI(
    title="AttentionX API",
    description="Automated Content Repurposing Engine",
    version="1.0.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory project store
projects = {}


@app.post("/api/upload")
async def upload_video(file: UploadFile = File(...)):
    """Upload a video file for processing."""
    
    # Validate file type
    allowed_types = {
        "video/mp4", "video/mpeg", "video/avi", "video/webm",
        "video/quicktime", "video/x-msvideo", "video/x-matroska",
    }
    
    if file.content_type and file.content_type not in allowed_types:
        # Allow any file that looks like a video by extension
        ext = os.path.splitext(file.filename or "")[1].lower()
        if ext not in {".mp4", ".avi", ".mov", ".mkv", ".webm", ".mpeg", ".mpg", ".wmv"}:
            raise HTTPException(
                400,
                f"Unsupported file type: {file.content_type}. Please upload a video file."
            )
    
    # Generate unique ID
    video_id = str(uuid.uuid4())[:8]
    upload_dir = os.path.join("uploads", video_id)
    os.makedirs(upload_dir, exist_ok=True)
    
    # Save file
    safe_filename = (file.filename or "video.mp4").replace(" ", "_")
    file_path = os.path.join(upload_dir, safe_filename)
    
    print(f"[Server] Uploading video: {safe_filename} -> {file_path}")
    
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)
    
    file_size_mb = len(content) / (1024 * 1024)
    print(f"[Server] Upload complete: {file_size_mb:.1f} MB")
    
    # Register project
    projects[video_id] = {
        "id": video_id,
        "filename": safe_filename,
        "filepath": file_path,
        "filesize": f"{file_size_mb:.1f} MB",
        "status": "uploaded",
        "progress": 0,
        "message": "Video uploaded successfully. Ready to process.",
        "clips": [],
        "error": None,
    }
    
    return {
        "video_id": video_id,
        "filename": safe_filename,
        "filesize": f"{file_size_mb:.1f} MB",
        "message": "Video uploaded successfully",
    }


@app.post("/api/process/{video_id}")
async def process_video(video_id: str):
    """Start the processing pipeline for an uploaded video."""
    
    if video_id not in projects:
        raise HTTPException(404, "Video not found")
    
    if projects[video_id]["status"] not in ["uploaded", "error", "complete"]:
        raise HTTPException(400, "Video is already being processed")
    
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise HTTPException(500, "GOOGLE_API_KEY not configured on server")
    
    # Reset status
    projects[video_id]["status"] = "extracting_audio"
    projects[video_id]["progress"] = 0
    projects[video_id]["message"] = "Starting processing pipeline..."
    projects[video_id]["clips"] = []
    projects[video_id]["error"] = None
    
    # Run pipeline in background thread
    thread = threading.Thread(
        target=_run_pipeline_thread,
        args=(video_id, api_key),
        daemon=True,
    )
    thread.start()
    
    return {"status": "processing", "message": "Processing started"}


def _run_pipeline_thread(video_id: str, api_key: str):
    """Run the processing pipeline in a background thread."""
    from pipeline import Pipeline
    
    def progress_callback(status, progress, message, clips=None):
        projects[video_id]["status"] = status
        projects[video_id]["progress"] = progress
        projects[video_id]["message"] = message
        if clips is not None:
            projects[video_id]["clips"] = clips
    
    try:
        pipeline = Pipeline(api_key=api_key)
        pipeline.run(
            video_id,
            projects[video_id]["filepath"],
            progress_callback,
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        projects[video_id]["status"] = "error"
        projects[video_id]["error"] = str(e)
        projects[video_id]["message"] = f"Error: {str(e)}"


@app.get("/api/status/{video_id}")
async def get_status(video_id: str):
    """SSE endpoint for real-time processing status updates."""
    
    if video_id not in projects:
        raise HTTPException(404, "Video not found")
    
    async def event_stream():
        last_data = ""
        tick = 0
        max_ticks = 1200  # Max ~20 minutes (at 1 tick/second)
        
        while tick < max_ticks:
            if video_id in projects:
                current = {
                    "status": projects[video_id]["status"],
                    "progress": projects[video_id]["progress"],
                    "message": projects[video_id]["message"],
                    "clips": projects[video_id].get("clips", []),
                    "error": projects[video_id].get("error"),
                }
                current_json = json.dumps(current)
                
                if current_json != last_data:
                    yield {"data": current_json, "event": "update"}
                    last_data = current_json
                    
                    if current["status"] in ["complete", "error"]:
                        return
            
            await asyncio.sleep(1)
            tick += 1
    
    return EventSourceResponse(event_stream())


@app.get("/api/clips/{video_id}")
async def get_clips(video_id: str):
    """Get list of generated clips for a video."""
    
    if video_id not in projects:
        raise HTTPException(404, "Video not found")
    
    return {
        "video_id": video_id,
        "clips": projects[video_id].get("clips", []),
        "status": projects[video_id]["status"],
    }


@app.get("/api/download/{video_id}/{filename}")
async def download_clip(video_id: str, filename: str):
    """Download a generated clip file."""
    
    # Sanitize filename to prevent path traversal
    filename = os.path.basename(filename)
    file_path = os.path.join("output", video_id, filename)
    
    if not os.path.exists(file_path):
        raise HTTPException(404, "File not found")
    
    return FileResponse(
        file_path,
        filename=filename,
        media_type="video/mp4",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/preview/{video_id}/{filename}")
async def preview_clip(video_id: str, filename: str):
    """Serve a clip for in-browser preview."""
    
    filename = os.path.basename(filename)
    file_path = os.path.join("output", video_id, filename)
    
    if not os.path.exists(file_path):
        raise HTTPException(404, "File not found")
    
    return FileResponse(file_path, media_type="video/mp4")


@app.get("/api/thumbnail/{video_id}/{filename}")
async def get_thumbnail(video_id: str, filename: str):
    """Serve a clip thumbnail."""
    
    filename = os.path.basename(filename)
    file_path = os.path.join("output", video_id, filename)
    
    if not os.path.exists(file_path):
        raise HTTPException(404, "Thumbnail not found")
    
    return FileResponse(file_path, media_type="image/jpeg")


# Serve static frontend files
frontend_dir = os.path.join(os.path.dirname(__file__), "frontend")
if os.path.isdir(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
else:
    @app.get("/")
    async def root():
        return HTMLResponse("<h1>AttentionX</h1><p>Frontend not found. Place files in ./frontend/</p>")


if __name__ == "__main__":
    import uvicorn
    
    print("=" * 60)
    print("  AttentionX - Automated Content Repurposing Engine")
    print("  http://localhost:8000")
    print("=" * 60)
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
    )
