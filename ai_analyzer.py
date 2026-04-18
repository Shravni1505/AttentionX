"""
AttentionX - AI Analyzer
Uses Google Gemini API for:
1. Audio transcription with timestamps
2. Golden nugget detection (viral moments)
3. Hook headline generation
"""

import json
import time
import os


def get_gemini_client(api_key: str):
    """Initialize Gemini client."""
    from google import genai
    return genai.Client(api_key=api_key)


def transcribe_audio(audio_path: str, api_key: str) -> list:
    """
    Transcribe audio file using Gemini.
    
    Returns list of transcript segments:
    [{"start": float, "end": float, "text": str}, ...]
    """
    from google import genai
    
    print(f"[AIAnalyzer] Transcribing audio: {audio_path}")
    client = genai.Client(api_key=api_key)
    
    # Upload audio file to Gemini
    print("[AIAnalyzer] Uploading audio to Gemini...")
    audio_file = client.files.upload(file=audio_path)
    
    # Wait for file to be processed
    print("[AIAnalyzer] Waiting for Gemini to process audio...")
    max_wait = 120  # Max 2 minutes
    waited = 0
    while hasattr(audio_file, 'state') and audio_file.state and str(audio_file.state).upper() in ["PROCESSING", "STATE_UNSPECIFIED"]:
        time.sleep(3)
        waited += 3
        if waited > max_wait:
            print("[AIAnalyzer] Warning: Audio processing taking too long, proceeding anyway...")
            break
        try:
            audio_file = client.files.get(name=audio_file.name)
        except Exception:
            break
    
    prompt = """Transcribe this audio file with timestamps. Return ONLY valid JSON with this exact structure:
{
    "segments": [
        {
            "start": <start time in seconds as a float>,
            "end": <end time in seconds as a float>,
            "text": "<transcribed text for this segment>"
        }
    ]
}

Rules:
- Create segments of approximately 10-30 seconds each
- Ensure timestamps are accurate and sequential
- Include ALL spoken content
- Return ONLY the JSON object, no other text"""

    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[audio_file, prompt],
        )
        
        result_text = response.text.strip()
        # Clean up JSON if wrapped in code blocks
        if result_text.startswith("```"):
            result_text = result_text.split("```")[1]
            if result_text.startswith("json"):
                result_text = result_text[4:]
            result_text = result_text.strip()
        
        data = json.loads(result_text)
        segments = data.get("segments", [])
        print(f"[AIAnalyzer] Transcribed {len(segments)} segments")
        
        # Clean up the uploaded file
        try:
            client.files.delete(name=audio_file.name)
        except Exception:
            pass
        
        return segments
        
    except Exception as e:
        print(f"[AIAnalyzer] Transcription error: {e}")
        # Try to clean up
        try:
            client.files.delete(name=audio_file.name)
        except Exception:
            pass
        raise


def find_golden_nuggets(transcript_segments: list, energy_data: dict, api_key: str, video_duration: float = 0) -> list:
    """
    Use Gemini to find the most compelling viral moments from the transcript.
    
    Args:
        transcript_segments: List of {start, end, text} dicts
        energy_data: Audio energy analysis results
        api_key: Gemini API key
        video_duration: Total video duration
    
    Returns:
        List of golden nugget dicts with start_time, end_time, hook_headline, etc.
    """
    from google import genai
    
    print("[AIAnalyzer] Finding golden nuggets with Gemini...")
    client = genai.Client(api_key=api_key)
    
    # Format transcript for the prompt
    transcript_text = ""
    for seg in transcript_segments:
        transcript_text += f"[{seg['start']:.1f}s - {seg['end']:.1f}s]: {seg['text']}\n"
    
    # Format energy peaks
    energy_peaks_text = ""
    if energy_data.get("high_energy_regions"):
        energy_peaks_text = "High-energy regions (where speaker is most passionate):\n"
        for region in energy_data["high_energy_regions"][:10]:
            energy_peaks_text += f"  - {region['start']:.1f}s to {region['end']:.1f}s (energy: {region['avg_energy']:.4f})\n"
    
    if energy_data.get("peak_times"):
        energy_peaks_text += f"\nEnergy peak timestamps: {', '.join([f'{t:.1f}s' for t in energy_data['peak_times'][:20]])}\n"
    
    prompt = f"""You are an expert viral content strategist for TikTok, Instagram Reels, and YouTube Shorts.

Given the following transcript and audio energy analysis from a long-form video, identify the BEST "golden nuggets" — moments that would make the most compelling short-form viral content.

TRANSCRIPT:
{transcript_text}

AUDIO ENERGY ANALYSIS:
{energy_peaks_text}
Total Duration: {video_duration:.1f}s
Average Energy: {energy_data.get('avg_energy', 0):.4f}

INSTRUCTIONS:
1. Find 3-5 of the MOST compelling moments for short-form content
2. Each clip should be 30-90 seconds long
3. Prioritize moments with:
   - High audio energy (passionate/emotional delivery)
   - Complete, self-contained thoughts or stories
   - Universal appeal, controversial takes, or profound wisdom
   - Strong natural opening hooks
4. For each nugget, write a CATCHY, scroll-stopping hook headline
5. Clips should NOT overlap significantly

Return ONLY valid JSON with this exact structure:
{{
    "nuggets": [
        {{
            "start_time": <start in seconds as float>,
            "end_time": <end in seconds as float>,
            "hook_headline": "<catchy headline that makes people stop scrolling>",
            "transcript_text": "<exact transcript for this segment>",
            "virality_score": <1-10 float rating>,
            "emotion": "<primary emotion: passionate/inspiring/funny/shocking/profound/motivational>",
            "why_viral": "<1-2 sentence explanation of why this would go viral>"
        }}
    ]
}}

Return ONLY the JSON, no other text."""

    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
        )
        
        result_text = response.text.strip()
        # Clean up JSON
        if result_text.startswith("```"):
            result_text = result_text.split("```")[1]
            if result_text.startswith("json"):
                result_text = result_text[4:]
            result_text = result_text.strip()
        
        data = json.loads(result_text)
        nuggets = data.get("nuggets", [])
        
        # Validate and clean nuggets
        valid_nuggets = []
        for n in nuggets:
            if all(k in n for k in ["start_time", "end_time", "hook_headline"]):
                # Ensure times are valid
                n["start_time"] = max(0, float(n["start_time"]))
                n["end_time"] = min(video_duration if video_duration > 0 else float('inf'), float(n["end_time"]))
                
                if n["end_time"] - n["start_time"] >= 10:  # At least 10 seconds
                    valid_nuggets.append(n)
        
        # Sort by virality score
        valid_nuggets.sort(key=lambda x: x.get("virality_score", 0), reverse=True)
        
        print(f"[AIAnalyzer] Found {len(valid_nuggets)} golden nuggets")
        for i, n in enumerate(valid_nuggets):
            print(f"  [{i+1}] {n['hook_headline']} ({n['start_time']:.1f}s-{n['end_time']:.1f}s, score: {n.get('virality_score', 'N/A')})")
        
        return valid_nuggets
        
    except Exception as e:
        print(f"[AIAnalyzer] Golden nugget detection error: {e}")
        # Fallback: use energy peaks to create clips
        return _fallback_nuggets(transcript_segments, energy_data, video_duration)


def _fallback_nuggets(transcript_segments: list, energy_data: dict, video_duration: float) -> list:
    """
    Fallback nugget detection using only audio energy peaks.
    Used when Gemini API fails.
    """
    print("[AIAnalyzer] Using fallback nugget detection...")
    
    nuggets = []
    regions = energy_data.get("high_energy_regions", [])
    
    for i, region in enumerate(regions[:5]):
        # Expand region to 30-60 seconds if too short
        center = (region["start"] + region["end"]) / 2
        clip_duration = max(30, region["end"] - region["start"])
        clip_duration = min(60, clip_duration)
        
        start = max(0, center - clip_duration / 2)
        end = min(video_duration, center + clip_duration / 2)
        
        # Get transcript for this region
        transcript = ""
        for seg in transcript_segments:
            if seg["end"] > start and seg["start"] < end:
                transcript += seg["text"] + " "
        
        nuggets.append({
            "start_time": round(start, 2),
            "end_time": round(end, 2),
            "hook_headline": f"Viral Moment #{i+1} 🔥",
            "transcript_text": transcript.strip(),
            "virality_score": round(8 - i * 0.5, 1),
            "emotion": "passionate",
            "why_viral": "High energy peak detected in audio analysis",
        })
    
    if not nuggets and video_duration > 30:
        # Last resort: create clips from the beginning, middle, and end
        segments = [
            (0, min(45, video_duration)),
            (max(0, video_duration/2 - 22), min(video_duration, video_duration/2 + 22)),
        ]
        for i, (start, end) in enumerate(segments):
            transcript = ""
            for seg in transcript_segments:
                if seg["end"] > start and seg["start"] < end:
                    transcript += seg["text"] + " "
            nuggets.append({
                "start_time": round(start, 2),
                "end_time": round(end, 2),
                "hook_headline": f"Key Moment #{i+1}",
                "transcript_text": transcript.strip(),
                "virality_score": 6.0,
                "emotion": "informative",
                "why_viral": "Auto-selected segment",
            })
    
    return nuggets
