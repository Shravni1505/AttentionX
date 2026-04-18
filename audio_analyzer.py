"""
AttentionX - Audio Analyzer
Uses librosa to detect emotional peaks via audio energy analysis.
Finds high-energy regions where the speaker is most passionate.
"""

import numpy as np
import os


def analyze_audio_energy(audio_path: str) -> dict:
    """
    Analyze audio file for energy peaks and high-energy regions.
    
    Returns dict with:
    - high_energy_regions: list of {start, end, avg_energy} dicts
    - peak_times: list of timestamps (seconds) of energy peaks
    - duration: total audio duration in seconds
    - avg_energy: average RMS energy
    - energy_timeline: simplified energy over time for visualization
    """
    import librosa
    
    print(f"[AudioAnalyzer] Loading audio: {audio_path}")
    
    # Load audio at 16kHz for speech analysis
    y, sr = librosa.load(audio_path, sr=16000)
    duration = len(y) / sr
    print(f"[AudioAnalyzer] Duration: {duration:.1f}s, Sample rate: {sr}")
    
    # Compute RMS energy
    hop_length = 512
    S, phase = librosa.magphase(librosa.stft(y, hop_length=hop_length))
    rms = librosa.feature.rms(S=S, hop_length=hop_length)[0]
    
    # Time axis for each frame
    frame_times = librosa.frames_to_time(
        np.arange(len(rms)), sr=sr, hop_length=hop_length
    )
    
    # Smooth the energy envelope (window ~2 seconds)
    kernel_size = max(1, int(2.0 * sr / hop_length))
    kernel = np.ones(kernel_size) / kernel_size
    rms_smooth = np.convolve(rms, kernel, mode='same')
    
    avg_energy = float(np.mean(rms_smooth))
    
    # Find high-energy regions (above 70th percentile)
    threshold = np.percentile(rms_smooth, 70)
    high_energy_mask = rms_smooth > threshold
    
    # Group contiguous high-energy frames into regions
    regions = []
    in_region = False
    region_start = 0
    
    for i in range(len(high_energy_mask)):
        if high_energy_mask[i] and not in_region:
            region_start = frame_times[i]
            in_region = True
        elif not high_energy_mask[i] and in_region:
            region_end = frame_times[i]
            region_duration = region_end - region_start
            
            # Only keep regions longer than 5 seconds
            if region_duration >= 5.0:
                start_frame = int(region_start * sr / hop_length)
                end_frame = min(int(region_end * sr / hop_length), len(rms_smooth))
                region_energy = float(np.mean(rms_smooth[start_frame:end_frame]))
                
                regions.append({
                    "start": round(float(region_start), 2),
                    "end": round(float(region_end), 2),
                    "duration": round(region_duration, 2),
                    "avg_energy": round(region_energy, 6),
                })
            in_region = False
    
    # Handle if last region extends to the end
    if in_region:
        region_end = frame_times[-1]
        region_duration = region_end - region_start
        if region_duration >= 5.0:
            regions.append({
                "start": round(float(region_start), 2),
                "end": round(float(region_end), 2),
                "duration": round(region_duration, 2),
                "avg_energy": round(float(np.mean(rms_smooth[int(region_start * sr / hop_length):])), 6),
            })
    
    # Sort regions by energy (highest first)
    regions.sort(key=lambda r: r["avg_energy"], reverse=True)
    
    # Detect individual peaks
    try:
        peaks = librosa.util.peak_pick(
            rms_smooth,
            pre_max=30, post_max=30,
            pre_avg=30, post_avg=30,
            delta=threshold * 0.3,
            wait=50
        )
        peak_times_list = [round(float(t), 2) for t in librosa.frames_to_time(peaks, sr=sr, hop_length=hop_length)]
    except Exception as e:
        print(f"[AudioAnalyzer] Peak detection fallback: {e}")
        # Fallback: just find local maxima
        peak_indices = []
        window = 50
        for i in range(window, len(rms_smooth) - window):
            if rms_smooth[i] == max(rms_smooth[i-window:i+window]) and rms_smooth[i] > threshold:
                peak_indices.append(i)
        peak_times_list = [round(float(frame_times[i]), 2) for i in peak_indices]
    
    # Create simplified energy timeline (one value per second for visualization)
    energy_timeline = []
    for sec in range(int(duration)):
        frame_start = int(sec * sr / hop_length)
        frame_end = min(int((sec + 1) * sr / hop_length), len(rms_smooth))
        if frame_start < len(rms_smooth):
            energy_timeline.append({
                "time": sec,
                "energy": round(float(np.mean(rms_smooth[frame_start:frame_end])), 6)
            })
    
    result = {
        "high_energy_regions": regions[:20],  # Top 20 regions
        "peak_times": peak_times_list[:50],   # Top 50 peaks
        "duration": round(duration, 2),
        "avg_energy": round(avg_energy, 6),
        "energy_timeline": energy_timeline,
    }
    
    print(f"[AudioAnalyzer] Found {len(regions)} high-energy regions, {len(peak_times_list)} peaks")
    return result
