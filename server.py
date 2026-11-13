import os, uuid, subprocess, requests
from fastapi import FastAPI, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="ClipFlow AI Backend")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs("outputs", exist_ok=True)
app.mount("/outputs", StaticFiles(directory="outputs"), name="outputs")

@app.get("/")
def health():
    return {"status": "online", "engine": "ClipFlow AI v4.0", "host": "Render Free"}

@app.post("/api/process-clip")
def process_clip(
    url: str = Form(...),
    caption_style: str = Form("Hormozi Bold"),
    gemini_key: str = Form(""),
    groq_key: str = Form("")
):
    job_id = str(uuid.uuid4())[:8]
    raw_file = f"outputs/raw_{job_id}.mp4"
    audio_file = f"outputs/audio_{job_id}.mp3"
    final_file = f"outputs/short_{job_id}.mp4"

    # 1. Download video via yt-dlp
    subprocess.run(["yt-dlp", "-f", "best[height<=720][ext=mp4]/best", "-o", raw_file, url], check=False)

    # 2. Crop to 9:16 Vertical Short (45s) & extract audio
    transcript_text = ""
    if os.path.exists(raw_file):
        subprocess.run([
            "ffmpeg", "-y", "-i", raw_file, "-t", "45",
            "-vf", "crop=ih*9/16:ih,scale=720:1280",
            "-c:v", "libx264", "-preset", "veryfast", "-c:a", "aac", final_file
        ], check=False)
        subprocess.run(["ffmpeg", "-y", "-i", final_file, "-vn", "-acodec", "libmp3lame", audio_file], check=False)

    # 3. Groq Whisper Auto-Transcription (if key provided)
    if groq_key and os.path.exists(audio_file):
        try:
            with open(audio_file, "rb") as f:
                gr = requests.post(
                    "https://api.groq.com/openai/v1/audio/transcriptions",
                    headers={"Authorization": f"Bearer {groq_key}"},
                    files={"file": f},
                    data={"model": "whisper-large-v3"},
                    timeout=30
                )
            if gr.ok:
                transcript_text = gr.json().get("text", "")
        except Exception:
            pass

    # 4. Gemini Viral Hook Title (if key provided)
    hook_title = "AI Extracted Viral 9:16 Short"
    if gemini_key:
        try:
            prompt_ctx = transcript_text[:400] if transcript_text else url
            r = requests.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={gemini_key}",
                json={"contents": [{"parts": [{"text": f"Write 1 short viral YouTube Shorts hook title (max 8 words) based on: {prompt_ctx}"}]}]},
                timeout=15
            )
            if r.ok:
                hook_title = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        except Exception:
            pass

    return {
        "status": "completed",
        "job_id": job_id,
        "hook_title": hook_title,
        "transcript": transcript_text,
        "caption_style": caption_style,
        "download_url": f"/outputs/short_{job_id}.mp4" if os.path.exists(final_file) else None
    }
  
