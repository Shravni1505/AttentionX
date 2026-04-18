"""
AttentionX - Processing Pipeline
Orchestrates the full video processing pipeline:
1. Extract audio
2. Analyze audio energy
3. Transcribe with AI
4. Find golden nuggets
5. Process each clip (face detect, smart crop, captions)
"""

import os
import traceback

from audio_analyzer import analyze_audio_energy
from ai_analyzer import transcribe_audio, find_golden_nuggets
from video_processor import (
    extract_audio,
    get_video_info,
    detect_face_position,
    smart_crop_and_caption,
)


class Pipeline:
    """Main processing pipeline orchestrator."""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        if not api_key:
            raise ValueError("GOOGLE_API_KEY is not set. Please set it in .env file.")
    
    def run(self, video_id: str, video_path: str, callback):
        """
        Run the complete processing pipeline.
        
        Args:
            video_id: Unique identifier for this video
            video_path: Path to the uploaded video file
            callback: Function(status, progress, message, clips=None) for progress updates
        """
        try:
            # Create output directories
            work_dir = os.path.join("uploads", video_id)
            output_dir = os.path.join("output", video_id)
            os.makedirs(work_dir, exist_ok=True)
            os.makedirs(output_dir, exist_ok=True)
            
            # ─── Step 1: Get video info ───
            callback("extracting_audio", 5, "[1/5] Analyzing video properties...")
            video_info = get_video_info(video_path)
            video_duration = video_info["duration"]
            print(f"[Pipeline] Video: {video_info['width']}x{video_info['height']}, "
                  f"{video_duration:.1f}s, {video_info['fps']}fps")
            
            # ─── Step 2: Extract audio ───
            callback("extracting_audio", 10, "[1/5] Extracting audio track...")
            audio_path = extract_audio(video_path, work_dir)
            
            # ─── Step 3: Analyze audio energy ───
            callback("analyzing_audio", 20, "[2/5] Analyzing audio energy patterns...")
            try:
                energy_data = analyze_audio_energy(audio_path)
                print(f"[Pipeline] Audio analysis: {len(energy_data['high_energy_regions'])} "
                      f"high-energy regions, {len(energy_data['peak_times'])} peaks")
            except Exception as e:
                print(f"[Pipeline] Audio analysis failed: {e}")
                energy_data = {
                    "high_energy_regions": [],
                    "peak_times": [],
                    "duration": video_duration,
                    "avg_energy": 0,
                }
            
            # ─── Step 4: Transcribe with Gemini ───
            callback("transcribing", 30, "[3/5] Transcribing audio with AI...")
            try:
                transcript_segments = transcribe_audio(audio_path, self.api_key)
                if not transcript_segments:
                    raise ValueError("Empty transcript returned")
            except Exception as e:
                print(f"[Pipeline] Transcription failed: {e}")
                traceback.print_exc()
                # Create a minimal fallback transcript
                transcript_segments = [{
                    "start": 0,
                    "end": video_duration,
                    "text": "[Transcription unavailable - using audio energy analysis only]"
                }]
            
            # ─── Step 5: Find golden nuggets ───
            callback("finding_nuggets", 45, "[4/5] AI is finding viral moments...")
            try:
                nuggets = find_golden_nuggets(
                    transcript_segments, energy_data, self.api_key, video_duration
                )
                if not nuggets:
                    raise ValueError("No nuggets found")
            except Exception as e:
                print(f"[Pipeline] Nugget detection failed: {e}")
                traceback.print_exc()
                # Fallback: create clips from high-energy regions
                nuggets = self._create_fallback_nuggets(
                    energy_data, transcript_segments, video_duration
                )
            
            print(f"[Pipeline] Processing {len(nuggets)} golden nuggets")
            
            # ─── Step 6-8: Process each clip ───
            clips = []
            for i, nugget in enumerate(nuggets):
                clip_progress_base = 50 + (i / max(1, len(nuggets))) * 45
                
                # Face detection
                callback(
                    "processing_clips",
                    clip_progress_base,
                    f"[5/5] Clip {i+1}/{len(nuggets)}: Detecting speaker face..."
                )
                face_pos = detect_face_position(
                    video_path, nugget["start_time"], nugget["end_time"]
                )
                
                # Smart crop + captions
                callback(
                    "processing_clips",
                    clip_progress_base + 15,
                    f"[5/5] Clip {i+1}/{len(nuggets)}: Smart cropping & adding captions..."
                )
                try:
                    clip_info = smart_crop_and_caption(
                        video_path, nugget, face_pos, output_dir, i
                    )
                    
                    clips.append({
                        "filename": clip_info["filename"],
                        "thumbnail": clip_info["thumbnail"],
                        "hook_headline": nugget.get("hook_headline", f"Clip {i+1}"),
                        "duration": clip_info["duration"],
                        "virality_score": nugget.get("virality_score", 5.0),
                        "emotion": nugget.get("emotion", "engaging"),
                        "transcript": nugget.get("transcript_text", ""),
                        "why_viral": nugget.get("why_viral", ""),
                    })
                    
                    print(f"[Pipeline] Clip {i+1} generated successfully")
                    
                except Exception as e:
                    print(f"[Pipeline] Error processing clip {i+1}: {e}")
                    traceback.print_exc()
                    continue
            
            if not clips:
                callback("error", 0, "Failed to generate any clips. Please try with a different video.", None)
                return
            
            # ─── Step 9: Complete ───
            callback("complete", 100, f"Generated {len(clips)} viral clips!", clips)
            print(f"[Pipeline] Pipeline complete! Generated {len(clips)} clips.")
            
        except Exception as e:
            traceback.print_exc()
            callback("error", 0, f"Pipeline error: {str(e)}", None)
    
    def _create_fallback_nuggets(self, energy_data: dict, transcript_segments: list, duration: float) -> list:
        """Create fallback nuggets from energy data when AI fails."""
        nuggets = []
        
        regions = energy_data.get("high_energy_regions", [])
        
        if regions:
            for i, region in enumerate(regions[:3]):
                center = (region["start"] + region["end"]) / 2
                clip_len = min(45, max(30, region["end"] - region["start"]))
                start = max(0, center - clip_len / 2)
                end = min(duration, center + clip_len / 2)
                
                text = ""
                for seg in transcript_segments:
                    if seg["end"] > start and seg["start"] < end:
                        text += seg["text"] + " "
                
                nuggets.append({
                    "start_time": start,
                    "end_time": end,
                    "hook_headline": f"Must-Watch Moment #{i+1}",
                    "transcript_text": text.strip(),
                    "virality_score": 7.0,
                    "emotion": "passionate",
                    "why_viral": "High audio energy detected",
                })
        else:
            # Absolute fallback: take clips from different parts
            clip_len = min(45, duration / 3)
            positions = [0.2, 0.5, 0.8]  # 20%, 50%, 80% through the video
            
            for i, pos in enumerate(positions):
                if pos * duration + clip_len > duration:
                    continue
                start = pos * duration
                end = start + clip_len
                
                text = ""
                for seg in transcript_segments:
                    if seg["end"] > start and seg["start"] < end:
                        text += seg["text"] + " "
                
                nuggets.append({
                    "start_time": start,
                    "end_time": end,
                    "hook_headline": f"Highlight #{i+1}",
                    "transcript_text": text.strip(),
                    "virality_score": 5.0,
                    "emotion": "informative",
                    "why_viral": "Auto-selected segment",
                })
        
        return nuggets
