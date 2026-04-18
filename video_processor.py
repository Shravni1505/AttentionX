"""
AttentionX - Video Processor
Handles:
1. Audio extraction from video
2. Face detection using MediaPipe
3. Smart cropping to 9:16 vertical
4. Dynamic caption overlay
5. Thumbnail generation
"""

import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import json


def extract_audio(video_path: str, output_dir: str) -> str:
    """
    Extract audio from video file as WAV.
    Returns path to the extracted audio file.
    """
    from moviepy import VideoFileClip
    
    audio_path = os.path.join(output_dir, "audio.wav")
    print(f"[VideoProcessor] Extracting audio from: {video_path}")
    
    clip = VideoFileClip(video_path)
    if clip.audio is None:
        raise ValueError("Video has no audio track")
    
    clip.audio.write_audiofile(
        audio_path,
        fps=16000,
        nbytes=2,
        codec='pcm_s16le',
        logger=None  # Suppress moviepy progress bars
    )
    clip.close()
    
    print(f"[VideoProcessor] Audio extracted to: {audio_path}")
    return audio_path


def get_video_info(video_path: str) -> dict:
    """Get basic video information."""
    from moviepy import VideoFileClip
    
    clip = VideoFileClip(video_path)
    info = {
        "width": clip.w,
        "height": clip.h,
        "duration": clip.duration,
        "fps": clip.fps,
        "aspect_ratio": f"{clip.w}:{clip.h}",
    }
    clip.close()
    return info


def detect_face_position(video_path: str, start_time: float, end_time: float) -> dict:
    """
    Detect face position in a video segment using MediaPipe.
    Samples frames and returns average face center position.
    
    Returns:
        dict with x_center, y_center (normalized 0-1), 
        face_width, face_height, detected (bool)
    """
    import cv2
    
    print(f"[VideoProcessor] Detecting face in segment {start_time:.1f}s-{end_time:.1f}s")
    
    try:
        import mediapipe as mp
        mp_face = mp.solutions.face_detection
    except ImportError:
        print("[VideoProcessor] MediaPipe not available, using center crop")
        return {"x_center": 0.5, "y_center": 0.5, "detected": False}
    
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    
    if fps <= 0:
        fps = 30
    
    # Sample 1 frame per second within the segment
    sample_interval = max(1.0, (end_time - start_time) / 10)  # At most 10 samples
    sample_times = np.arange(start_time, end_time, sample_interval)
    
    face_positions = []
    
    with mp_face.FaceDetection(
        model_selection=1,  # Full range model
        min_detection_confidence=0.5
    ) as face_detection:
        
        for t in sample_times:
            frame_num = int(t * fps)
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
            ret, frame = cap.read()
            
            if not ret:
                continue
            
            # Convert BGR to RGB
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = face_detection.process(rgb_frame)
            
            if results.detections:
                # Use the first (most confident) detection
                detection = results.detections[0]
                bbox = detection.location_data.relative_bounding_box
                
                x_center = bbox.xmin + bbox.width / 2
                y_center = bbox.ymin + bbox.height / 2
                
                face_positions.append({
                    "x": x_center,
                    "y": y_center,
                    "w": bbox.width,
                    "h": bbox.height,
                })
    
    cap.release()
    
    if face_positions:
        avg_x = np.mean([p["x"] for p in face_positions])
        avg_y = np.mean([p["y"] for p in face_positions])
        avg_w = np.mean([p["w"] for p in face_positions])
        avg_h = np.mean([p["h"] for p in face_positions])
        
        print(f"[VideoProcessor] Face detected at ({avg_x:.2f}, {avg_y:.2f})")
        return {
            "x_center": float(avg_x),
            "y_center": float(avg_y),
            "face_width": float(avg_w),
            "face_height": float(avg_h),
            "detected": True,
            "samples": len(face_positions),
        }
    else:
        print("[VideoProcessor] No face detected, using center crop")
        return {"x_center": 0.5, "y_center": 0.5, "detected": False}


def smart_crop_and_caption(
    video_path: str,
    nugget: dict,
    face_pos: dict,
    output_dir: str,
    clip_index: int,
) -> dict:
    """
    Smart-crop a video segment to 9:16 vertical format and add captions.
    
    Args:
        video_path: Path to source video
        nugget: Golden nugget dict with start_time, end_time, transcript_text, hook_headline
        face_pos: Face position dict from detect_face_position
        output_dir: Output directory
        clip_index: Index for filename
    
    Returns:
        dict with filename, thumbnail path, and clip info
    """
    from moviepy import (
        VideoFileClip, TextClip, CompositeVideoClip, 
        ColorClip, ImageClip
    )
    
    start = nugget["start_time"]
    end = nugget["end_time"]
    hook = nugget.get("hook_headline", f"Clip {clip_index + 1}")
    transcript = nugget.get("transcript_text", "")
    
    print(f"[VideoProcessor] Processing clip {clip_index + 1}: {start:.1f}s - {end:.1f}s")
    print(f"[VideoProcessor] Hook: {hook}")
    
    # Load and cut the clip
    source = VideoFileClip(video_path)
    
    # Clamp times to video duration  
    start = max(0, min(start, source.duration - 1))
    end = max(start + 5, min(end, source.duration))
    
    subclip = source.subclipped(start, end)
    clip_duration = end - start
    
    video_w = subclip.w
    video_h = subclip.h
    
    # Calculate 9:16 crop region
    target_ratio = 9 / 16
    current_ratio = video_w / video_h
    
    if current_ratio > target_ratio:
        # Video is wider than 9:16 → crop horizontally
        crop_w = int(video_h * target_ratio)
        crop_h = video_h
        
        # Center on face
        face_x_pixel = face_pos["x_center"] * video_w
        x1 = int(face_x_pixel - crop_w / 2)
        x1 = max(0, min(x1, video_w - crop_w))
        x2 = x1 + crop_w
        
        cropped = subclip.cropped(x1=x1, y1=0, x2=x2, y2=crop_h)
    else:
        # Video is already narrow or vertical → just use it as is
        cropped = subclip
        crop_w = video_w
        crop_h = video_h
    
    final_w = cropped.w
    final_h = cropped.h
    
    # Target output size: 1080x1920 or proportional
    if final_h < 1080:
        target_h = final_h
        target_w = final_w
    else:
        target_h = min(1920, final_h)
        target_w = int(target_h * 9 / 16)
    
    # Resize to target
    if final_w != target_w or final_h != target_h:
        cropped = cropped.resized((target_w, target_h))
        final_w = target_w
        final_h = target_h
    
    # ─── Create caption overlays ───
    caption_clips = []
    
    if transcript:
        caption_clips = _create_caption_clips(
            transcript, clip_duration, final_w, final_h
        )
    
    # ─── Create hook headline overlay (first 3 seconds) ───
    hook_clips = _create_hook_overlay(hook, final_w, final_h)
    
    # Composite everything
    all_layers = [cropped] + hook_clips + caption_clips
    final = CompositeVideoClip(all_layers, size=(final_w, final_h))
    
    # Output filename
    clip_filename = f"clip_{clip_index + 1}.mp4"
    clip_path = os.path.join(output_dir, clip_filename)
    
    print(f"[VideoProcessor] Writing clip to: {clip_path}")
    final.write_videofile(
        clip_path,
        codec="libx264",
        audio_codec="aac",
        fps=min(30, source.fps or 30),
        preset="fast",
        logger=None,
    )
    
    # Generate thumbnail
    thumb_filename = f"thumb_{clip_index + 1}.jpg"
    thumb_path = os.path.join(output_dir, thumb_filename)
    _generate_thumbnail(clip_path, thumb_path)
    
    # Cleanup
    final.close()
    cropped.close()
    subclip.close()
    source.close()
    
    return {
        "filename": clip_filename,
        "thumbnail": thumb_filename,
        "duration": round(clip_duration, 2),
    }


def _create_caption_clips(transcript: str, duration: float, width: int, height: int) -> list:
    """Create timed caption TextClips from transcript text."""
    from moviepy import TextClip
    
    words = transcript.split()
    if not words:
        return []
    
    words_per_group = 4
    groups = []
    for i in range(0, len(words), words_per_group):
        groups.append(" ".join(words[i:i + words_per_group]))
    
    if not groups:
        return []
    
    time_per_group = duration / len(groups)
    caption_clips = []
    
    # Find a suitable font
    font = _find_font()
    
    for i, text in enumerate(groups):
        try:
            # Main text (white with black outline)
            txt = TextClip(
                text=text.upper(),
                font_size=max(28, min(48, int(width / 15))),
                color="white",
                font=font,
                stroke_color="black",
                stroke_width=3,
                text_align="center",
                size=(width - 60, None),
            )
            
            txt = txt.with_position(("center", height - 200))
            txt = txt.with_start(i * time_per_group)
            txt = txt.with_duration(time_per_group)
            
            caption_clips.append(txt)
            
        except Exception as e:
            print(f"[VideoProcessor] Caption rendering error for group {i}: {e}")
            continue
    
    return caption_clips


def _create_hook_overlay(hook_text: str, width: int, height: int) -> list:
    """Create a hook headline overlay for the first 3 seconds."""
    from moviepy import TextClip, ColorClip
    
    clips = []
    font = _find_font()
    
    try:
        # Semi-transparent background bar
        bar_height = max(80, int(height * 0.06))
        bg = ColorClip(
            size=(width, bar_height),
            color=(0, 0, 0),
        )
        bg = bg.with_opacity(0.7)
        bg = bg.with_position(("center", int(height * 0.12)))
        bg = bg.with_start(0.5)
        bg = bg.with_duration(3.5)
        clips.append(bg)
        
        # Hook text
        hook_txt = TextClip(
            text=hook_text,
            font_size=max(24, min(40, int(width / 18))),
            color="#FFD700",
            font=font,
            stroke_color="black",
            stroke_width=2,
            text_align="center",
            size=(width - 40, None),
        )
        hook_txt = hook_txt.with_position(("center", int(height * 0.12) + 15))
        hook_txt = hook_txt.with_start(0.5)
        hook_txt = hook_txt.with_duration(3.5)
        clips.append(hook_txt)
        
    except Exception as e:
        print(f"[VideoProcessor] Hook overlay error: {e}")
    
    return clips


def _find_font() -> str:
    """Find a suitable font available on the system."""
    # Common font paths on Windows
    font_candidates = [
        "Arial",
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/calibri.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    
    for font in font_candidates:
        if os.path.exists(font):
            return font
    
    # Return a default name and hope the system resolves it
    return "Arial"


def _generate_thumbnail(video_path: str, thumb_path: str):
    """Generate a thumbnail from the middle of a video clip."""
    try:
        from moviepy import VideoFileClip
        
        clip = VideoFileClip(video_path)
        # Get frame from 1/3 into the clip
        t = clip.duration / 3
        frame = clip.get_frame(t)
        clip.close()
        
        img = Image.fromarray(frame)
        img.thumbnail((480, 854), Image.Resampling.LANCZOS)
        img.save(thumb_path, "JPEG", quality=85)
        
        print(f"[VideoProcessor] Thumbnail saved: {thumb_path}")
    except Exception as e:
        print(f"[VideoProcessor] Thumbnail generation error: {e}")
        # Create a placeholder thumbnail
        img = Image.new("RGB", (480, 854), (30, 30, 40))
        draw = ImageDraw.Draw(img)
        draw.text((200, 400), "▶", fill="white")
        img.save(thumb_path, "JPEG")
