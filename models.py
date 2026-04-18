"""
AttentionX - Data Models
Pydantic models for API requests, responses, and internal data structures.
"""

from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum


class ProcessingStep(str, Enum):
    """Processing pipeline steps."""
    UPLOADED = "uploaded"
    EXTRACTING_AUDIO = "extracting_audio"
    ANALYZING_AUDIO = "analyzing_audio"
    TRANSCRIBING = "transcribing"
    FINDING_NUGGETS = "finding_nuggets"
    PROCESSING_CLIPS = "processing_clips"
    COMPLETE = "complete"
    ERROR = "error"


class GoldenNugget(BaseModel):
    """A detected high-value moment from the video."""
    start_time: float = Field(description="Start time in seconds")
    end_time: float = Field(description="End time in seconds")
    hook_headline: str = Field(description="Catchy headline for the clip")
    transcript_text: str = Field(description="Transcript of this segment")
    virality_score: float = Field(ge=0, le=10, description="Viral potential score 1-10")
    emotion: str = Field(description="Primary emotion (passionate, inspiring, etc.)")
    why_viral: str = Field(default="", description="Why this moment would go viral")


class ClipInfo(BaseModel):
    """Information about a generated clip."""
    filename: str
    thumbnail: str = ""
    hook_headline: str
    duration: float
    virality_score: float
    emotion: str
    transcript: str = ""


class VideoProject(BaseModel):
    """A video processing project."""
    id: str
    filename: str
    filepath: str
    status: ProcessingStep = ProcessingStep.UPLOADED
    progress: float = 0
    message: str = ""
    clips: List[ClipInfo] = []
    error: Optional[str] = None


class UploadResponse(BaseModel):
    """Response after uploading a video."""
    video_id: str
    filename: str
    message: str = "Video uploaded successfully"


class ProcessResponse(BaseModel):
    """Response after starting processing."""
    status: str
    message: str


class AudioAnalysisResult(BaseModel):
    """Result of audio energy analysis."""
    high_energy_regions: List[dict] = []
    peak_times: List[float] = []
    duration: float = 0
    avg_energy: float = 0


class TranscriptSegment(BaseModel):
    """A segment of the transcript."""
    start: float
    end: float
    text: str
