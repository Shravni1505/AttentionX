/**
 * AttentionX — Frontend Application Logic
 * Handles: Upload, SSE progress streaming, clip gallery, video preview
 */

// ─── State ───
let currentVideoId = null;
let eventSource = null;
let selectedFile = null;

// ─── DOM Elements ───
const uploadZone = document.getElementById('upload-zone');
const fileInput = document.getElementById('file-input');
const selectedFileEl = document.getElementById('selected-file');
const fileNameEl = document.getElementById('file-name');
const fileSizeEl = document.getElementById('file-size');
const uploadOverlay = document.getElementById('upload-progress-overlay');
const uploadRing = document.getElementById('upload-ring');
const uploadPercent = document.getElementById('upload-percent');
const uploadStatusText = document.getElementById('upload-status-text');
const progressFill = document.getElementById('progress-fill');
const progressPercent = document.getElementById('progress-percent');
const progressMessage = document.getElementById('progress-message');
const processingFilename = document.getElementById('processing-filename');
const pipelineSteps = document.getElementById('pipeline-steps');
const clipsGrid = document.getElementById('clips-grid');
const resultsSubtitle = document.getElementById('results-subtitle');
const errorMessage = document.getElementById('error-message');
const modalOverlay = document.getElementById('modal-overlay');
const modalVideo = document.getElementById('modal-video');
const modalHook = document.getElementById('modal-hook');
const modalTranscript = document.getElementById('modal-transcript');
const modalDownload = document.getElementById('modal-download');

// ─── Section Management ───
function showSection(name) {
    document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
    const section = document.getElementById(`section-${name}`);
    if (section) section.classList.add('active');
}

function resetToUpload() {
    currentVideoId = null;
    selectedFile = null;
    if (eventSource) {
        eventSource.close();
        eventSource = null;
    }
    fileInput.value = '';
    selectedFileEl.style.display = 'none';
    uploadOverlay.classList.remove('active');
    uploadZone.querySelector('.upload-content').style.display = 'block';
    clipsGrid.innerHTML = '';
    showSection('upload');
}

// ─── Upload Handling ───

// Drag and drop
uploadZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    uploadZone.classList.add('drag-over');
});

uploadZone.addEventListener('dragleave', () => {
    uploadZone.classList.remove('drag-over');
});

uploadZone.addEventListener('drop', (e) => {
    e.preventDefault();
    uploadZone.classList.remove('drag-over');
    const files = e.dataTransfer.files;
    if (files.length > 0) {
        handleFileSelect(files[0]);
    }
});

// Click to browse
uploadZone.addEventListener('click', (e) => {
    if (uploadOverlay.classList.contains('active')) return;
    fileInput.click();
});

fileInput.addEventListener('change', (e) => {
    if (e.target.files.length > 0) {
        handleFileSelect(e.target.files[0]);
    }
});

// Clear file
document.getElementById('btn-clear').addEventListener('click', (e) => {
    e.stopPropagation();
    selectedFile = null;
    fileInput.value = '';
    selectedFileEl.style.display = 'none';
});

function handleFileSelect(file) {
    // Validate file type
    const validTypes = ['video/mp4', 'video/mpeg', 'video/avi', 'video/webm', 'video/quicktime', 
                        'video/x-msvideo', 'video/x-matroska'];
    const validExts = ['.mp4', '.avi', '.mov', '.mkv', '.webm', '.mpeg', '.mpg', '.wmv'];
    const ext = '.' + file.name.split('.').pop().toLowerCase();
    
    if (!validTypes.includes(file.type) && !validExts.includes(ext)) {
        alert('Please select a valid video file (MP4, MOV, AVI, MKV, WebM)');
        return;
    }
    
    // Validate file size (500MB max)
    if (file.size > 500 * 1024 * 1024) {
        alert('File is too large. Maximum size is 500MB.');
        return;
    }
    
    selectedFile = file;
    
    // Show selected file info
    fileNameEl.textContent = file.name;
    fileSizeEl.textContent = formatFileSize(file.size);
    selectedFileEl.style.display = 'flex';
    
    // Auto-start upload
    uploadFile(file);
}

async function uploadFile(file) {
    // Show upload progress
    uploadOverlay.classList.add('active');
    uploadZone.querySelector('.upload-content').style.display = 'none';
    
    const formData = new FormData();
    formData.append('file', file);
    
    try {
        // Upload with XMLHttpRequest for progress tracking
        const result = await new Promise((resolve, reject) => {
            const xhr = new XMLHttpRequest();
            
            xhr.upload.addEventListener('progress', (e) => {
                if (e.lengthComputable) {
                    const percent = Math.round((e.loaded / e.total) * 100);
                    updateUploadProgress(percent);
                }
            });
            
            xhr.addEventListener('load', () => {
                if (xhr.status >= 200 && xhr.status < 300) {
                    resolve(JSON.parse(xhr.responseText));
                } else {
                    reject(new Error(`Upload failed: ${xhr.statusText}`));
                }
            });
            
            xhr.addEventListener('error', () => reject(new Error('Upload failed')));
            xhr.addEventListener('abort', () => reject(new Error('Upload aborted')));
            
            xhr.open('POST', '/api/upload');
            xhr.send(formData);
        });
        
        currentVideoId = result.video_id;
        updateUploadProgress(100);
        uploadStatusText.textContent = 'Upload complete! Starting processing...';
        
        // Start processing
        setTimeout(() => startProcessing(result.video_id, file.name), 500);
        
    } catch (error) {
        console.error('Upload error:', error);
        uploadOverlay.classList.remove('active');
        uploadZone.querySelector('.upload-content').style.display = 'block';
        alert(`Upload failed: ${error.message}`);
    }
}

function updateUploadProgress(percent) {
    const circumference = 2 * Math.PI * 54; // radius from SVG
    const offset = circumference - (percent / 100) * circumference;
    uploadRing.style.strokeDashoffset = offset;
    uploadPercent.textContent = `${percent}%`;
}

// ─── Processing ───

async function startProcessing(videoId, filename) {
    // Switch to processing view
    showSection('processing');
    processingFilename.textContent = filename;
    progressFill.style.width = '0%';
    progressPercent.textContent = '0%';
    progressMessage.textContent = 'Initializing pipeline...';
    
    // Reset pipeline steps
    document.querySelectorAll('.step').forEach(s => {
        s.classList.remove('active', 'complete');
    });
    
    try {
        // Trigger processing
        const response = await fetch(`/api/process/${videoId}`, { method: 'POST' });
        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || 'Processing failed to start');
        }
        
        // Connect to SSE for status updates
        connectSSE(videoId);
        
    } catch (error) {
        console.error('Processing start error:', error);
        showError(error.message);
    }
}

function connectSSE(videoId) {
    if (eventSource) {
        eventSource.close();
    }
    
    eventSource = new EventSource(`/api/status/${videoId}`);
    
    eventSource.addEventListener('update', (event) => {
        const data = JSON.parse(event.data);
        handleStatusUpdate(data);
    });
    
    eventSource.addEventListener('error', (event) => {
        console.error('SSE error:', event);
        // Try to reconnect after a delay
        if (eventSource) {
            eventSource.close();
            eventSource = null;
        }
        // Poll fallback
        setTimeout(() => pollStatus(videoId), 2000);
    });
}

async function pollStatus(videoId) {
    try {
        const response = await fetch(`/api/clips/${videoId}`);
        const data = await response.json();
        
        if (data.status === 'complete') {
            handleStatusUpdate({
                status: 'complete',
                progress: 100,
                message: 'Processing complete!',
                clips: data.clips,
            });
        } else if (data.status === 'error') {
            showError('Processing failed. Please try again.');
        } else {
            // Still processing, connect SSE again
            connectSSE(videoId);
        }
    } catch (e) {
        console.error('Poll error:', e);
    }
}

const STEP_ORDER = [
    'extracting_audio',
    'analyzing_audio', 
    'transcribing',
    'finding_nuggets',
    'processing_clips',
];

function handleStatusUpdate(data) {
    const { status, progress, message, clips, error } = data;
    
    // Update progress bar
    progressFill.style.width = `${progress}%`;
    progressPercent.textContent = `${Math.round(progress)}%`;
    progressMessage.textContent = message || '';
    
    // Update pipeline steps
    const currentStepIndex = STEP_ORDER.indexOf(status);
    
    document.querySelectorAll('.step').forEach((stepEl) => {
        const stepName = stepEl.dataset.step;
        const stepIndex = STEP_ORDER.indexOf(stepName);
        
        stepEl.classList.remove('active', 'complete');
        
        if (stepIndex < currentStepIndex) {
            stepEl.classList.add('complete');
        } else if (stepIndex === currentStepIndex) {
            stepEl.classList.add('active');
        }
    });
    
    // Handle completion
    if (status === 'complete' && clips && clips.length > 0) {
        if (eventSource) {
            eventSource.close();
            eventSource = null;
        }
        setTimeout(() => showResults(clips), 800);
    }
    
    // Handle error
    if (status === 'error') {
        if (eventSource) {
            eventSource.close();
            eventSource = null;
        }
        showError(error || message || 'An unknown error occurred');
    }
}

// ─── Results ───

function showResults(clips) {
    showSection('results');
    resultsSubtitle.textContent = `Generated ${clips.length} viral clip${clips.length !== 1 ? 's' : ''} from your video`;
    
    clipsGrid.innerHTML = '';
    
    clips.forEach((clip, index) => {
        const card = createClipCard(clip, index);
        clipsGrid.appendChild(card);
    });
}

function createClipCard(clip, index) {
    const card = document.createElement('div');
    card.className = 'clip-card';
    card.style.animationDelay = `${index * 0.1}s`;
    
    const duration = formatDuration(clip.duration);
    const thumbnailUrl = `/api/thumbnail/${currentVideoId}/${clip.thumbnail}`;
    const previewUrl = `/api/preview/${currentVideoId}/${clip.filename}`;
    const downloadUrl = `/api/download/${currentVideoId}/${clip.filename}`;
    const score = clip.virality_score || 0;
    const fireIcons = score >= 8 ? '🔥🔥🔥' : score >= 6 ? '🔥🔥' : '🔥';
    
    card.innerHTML = `
        <div class="clip-thumbnail" onclick="openPreview('${previewUrl}', ${JSON.stringify(clip.hook_headline).replace(/'/g, "&#39;")}, ${JSON.stringify(clip.transcript || '').replace(/'/g, "&#39;")}, '${downloadUrl}')">
            <img src="${thumbnailUrl}" alt="Clip ${index + 1} thumbnail" 
                 onerror="this.style.display='none'">
            <div class="clip-play-btn">
                <div class="play-icon">▶</div>
            </div>
            <span class="clip-duration">${duration}</span>
        </div>
        <div class="clip-info">
            <h3 class="clip-hook">${escapeHtml(clip.hook_headline)}</h3>
            <div class="clip-meta">
                <span class="clip-score">${fireIcons} ${score.toFixed(1)}</span>
                <span class="clip-emotion">${escapeHtml(clip.emotion || 'engaging')}</span>
            </div>
            <div class="clip-actions">
                <button class="btn btn-ghost" onclick="openPreview('${previewUrl}', ${JSON.stringify(clip.hook_headline).replace(/'/g, "&#39;")}, ${JSON.stringify(clip.transcript || '').replace(/'/g, "&#39;")}, '${downloadUrl}')">
                    ▶ Preview
                </button>
                <a class="btn btn-primary" href="${downloadUrl}" download>
                    ⬇ Download
                </a>
            </div>
        </div>
    `;
    
    return card;
}

// ─── Modal / Preview ───

function openPreview(videoUrl, hook, transcript, downloadUrl) {
    modalVideo.src = videoUrl;
    modalHook.textContent = hook;
    modalTranscript.textContent = transcript || '';
    modalDownload.onclick = () => {
        const a = document.createElement('a');
        a.href = downloadUrl;
        a.download = '';
        a.click();
    };
    modalOverlay.classList.add('active');
    document.body.style.overflow = 'hidden';
}

function closeModal(event) {
    if (event && event.target !== modalOverlay && !event.target.closest('.modal-close')) return;
    modalOverlay.classList.remove('active');
    modalVideo.pause();
    modalVideo.src = '';
    document.body.style.overflow = '';
}

// Close on Escape
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeModal();
});

// ─── Error ───

function showError(msg) {
    errorMessage.textContent = msg;
    showSection('error');
}

// ─── Utility ───

function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
    return (bytes / (1024 * 1024 * 1024)).toFixed(2) + ' GB';
}

function formatDuration(seconds) {
    const m = Math.floor(seconds / 60);
    const s = Math.round(seconds % 60);
    return `${m}:${s.toString().padStart(2, '0')}`;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ─── Initialize ───
showSection('upload');
