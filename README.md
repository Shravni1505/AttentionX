# 🎬 AttentionX — Automated Content Repurposing Engine

> Transform long-form videos into viral short-form clips with AI-powered emotional peak detection, smart face-tracking crop, and dynamic captions.

##  Demo Link(Google Drive)
https://drive.google.com/file/d/10AJtIBvBXDJN_XWu_tSXHO-G__9rne_m/view?usp=sharing

##  Features

###  Emotional Peak Detection
- **Audio Energy Analysis** using Librosa to detect passionate, high-energy moments
- **AI Sentiment Analysis** using Google Gemini to find the most compelling, viral-worthy segments
- **Smart Ranking** that combines audio spikes + content quality for optimal clip selection

###  Smart Face-Tracking Crop
- **MediaPipe Face Detection** tracks the speaker's face across frames
- **Automatic 9:16 Crop** converts horizontal (16:9) video to vertical format for TikTok/Reels/Shorts
- **Speaker-Centered Framing** ensures the speaker stays perfectly centered in every clip

###  Dynamic Captions
- **Auto-generated Transcription** with timestamp synchronization via Gemini AI
- **Karaoke-style Word Display** with timed word groups at the bottom of the screen
- **Hook Headlines** — AI generates catchy, scroll-stopping headlines overlaid on each clip

### 🎯 Full Processing Pipeline
1. Upload any long-form video (MP4, MOV, AVI, MKV, WebM)
2. AI extracts and analyzes audio for energy peaks
3. Full audio transcription with timestamps
4. Gemini AI identifies the top 3-5 "golden nuggets" for maximum virality
5. Each clip is smart-cropped, captioned, and exported as a ready-to-post vertical video

---

##  Architecture

```
┌─────────────────────────────────────────────┐
│         Premium Dark-Theme Frontend         │
│  Drag-drop upload • Real-time SSE progress  │
│  Clip gallery • Video preview • Download    │
└──────────────────────┬──────────────────────┘
                       │ REST API + SSE
┌──────────────────────▼──────────────────────┐
│            FastAPI Backend                   │
│  Upload → Process → Status → Download       │
└──────────────────────┬──────────────────────┘
                       │
┌──────────────────────▼──────────────────────┐
│         AI Processing Pipeline               │
│                                              │
│  1. Audio Extraction (MoviePy/FFmpeg)        │
│  2. Energy Analysis (Librosa)                │
│  3. Transcription (Gemini AI)                │
│  4. Golden Nugget Detection (Gemini AI)      │
│  5. Face Detection (MediaPipe)               │
│  6. Smart Crop to 9:16 (MoviePy)            │
│  7. Caption Overlay (MoviePy + PIL)          │
└─────────────────────────────────────────────┘
```

---

##  Quick Start

### Prerequisites

- **Python 3.9+**
- **FFmpeg** installed and available in PATH
  - Windows: Download from [ffmpeg.org](https://ffmpeg.org/download.html) or install via `choco install ffmpeg`
  - Mac: `brew install ffmpeg`
  - Linux: `sudo apt install ffmpeg`
- **Google Gemini API Key** — Get free at [Google AI Studio](https://aistudio.google.com/)

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/YOUR_USERNAME/attentionx.git
cd attentionx

# 2. Create virtual environment (recommended)
python -m venv venv
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up environment variables
# Copy .env.example to .env and add your API key
cp .env.example .env
# Edit .env and set: GOOGLE_API_KEY=your_key_here
```

### Run the Application

```bash
python main.py
```

Open your browser and navigate to: **http://localhost:8000**

---

##  Tech Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Backend** | FastAPI | High-performance async API server |
| **AI Engine** | Google Gemini 2.0 Flash | Transcription + golden nugget detection |
| **Audio Analysis** | Librosa | Energy peak detection, onset strength |
| **Face Detection** | MediaPipe | Speaker face tracking for smart crop |
| **Video Processing** | MoviePy + FFmpeg | Clip cutting, cropping, caption overlay |
| **Frontend** | Vanilla HTML/CSS/JS | Premium dark theme with glassmorphism |
| **Real-time Updates** | Server-Sent Events (SSE) | Live processing progress streaming |

---

##  Project Structure

```
attentionx/
├── main.py                 # FastAPI server & API endpoints
├── pipeline.py             # Processing pipeline orchestrator
├── ai_analyzer.py          # Gemini AI transcription & analysis
├── audio_analyzer.py       # Librosa audio energy detection
├── video_processor.py      # Face detection, smart crop, captions
├── models.py               # Pydantic data models
├── requirements.txt        # Python dependencies
├── .env                    # Environment variables (API keys)
├── .env.example            # Environment template
├── frontend/
│   ├── index.html          # Main UI page
│   ├── styles.css          # Premium dark theme CSS
│   └── app.js              # Client-side logic
├── uploads/                # Uploaded videos (auto-created)
└── output/                 # Generated clips (auto-created)
```

##  License

This project was built for the UnsaidTalks Hackathon 2025.

---

##  Acknowledgments

- **Google Gemini AI** — For powerful multimodal analysis
- **MediaPipe** — For blazing-fast face detection
- **MoviePy** — For flexible video processing
- **Librosa** — For audio signal analysis
- **UnsaidTalks** — For organizing this hackathon
