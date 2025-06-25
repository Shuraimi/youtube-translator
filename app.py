from flask import Flask, request, jsonify, render_template
import os
import yt_dlp
import whisper
from googletrans import Translator
from gtts import gTTS
import subprocess
import uuid
import requests

# Constants
COOKIES_URL = "https://paste.rs/iSLxu.txt"  # Replace with your actual paste.rs URL
COOKIES_PATH = "cookies.txt"
UPLOAD_FOLDER = "temp"

# Create upload folder if not exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# App setup
app = Flask(__name__, template_folder='templates')

def fetch_cookies():
    if not os.path.exists(COOKIES_PATH):
        try:
            r = requests.get(COOKIES_URL, timeout=10)
            r.raise_for_status()
            with open(COOKIES_PATH, "wb") as f:
                f.write(r.content)
            print("✅ cookies.txt fetched successfully")
        except Exception as e:
            print(f"⚠️ Could not fetch cookies: {e}")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/translate', methods=['POST'])
def translate_video():
    youtube_url = request.form.get("url")
    target_lang = request.form.get("lang", "en")

    if not youtube_url:
        return jsonify({"error": "Missing YouTube URL"}), 400

    # Generate unique file IDs
    video_id = str(uuid.uuid4())
    audio_path = os.path.join(UPLOAD_FOLDER, f"{video_id}.mp3")
    video_path = os.path.join(UPLOAD_FOLDER, f"{video_id}.mp4")
    translated_audio_path = os.path.join(UPLOAD_FOLDER, f"translated_{video_id}.mp3")
    output_video = os.path.join(UPLOAD_FOLDER, f"translated_{video_id}.mp4")

    try:
        # Fetch cookies from external URL
        fetch_cookies()

        # Download audio using yt-dlp
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': audio_path,
            'cookies': COOKIES_PATH,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
            }]
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([youtube_url])

        # Transcribe using Whisper
        model = whisper.load_model("base")
        result = model.transcribe(audio_path)
        original_text = result["text"]

        # Translate
        translator = Translator()
        translated_text = translator.translate(original_text, dest=target_lang).text

        # Convert translated text to speech
        tts = gTTS(translated_text, lang=target_lang)
        tts.save(translated_audio_path)

        # Download full video
        ydl_video_opts = {
            'format': 'bestvideo+bestaudio/best',
            'outtmpl': video_path,
        }
        with yt_dlp.YoutubeDL(ydl_video_opts) as ydl:
            ydl.download([youtube_url])

        # Combine translated audio + video
        command = [
            'ffmpeg', '-y',
            '-i', video_path,
            '-i', translated_audio_path,
            '-c:v', 'copy',
            '-map', '0:v:0',
            '-map', '1:a:0',
            '-shortest', output_video
        ]
        subprocess.run(command, check=True)

        return render_template('index.html', video_url=output_video)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        for f in [audio_path, video_path, translated_audio_path]:
            try:
                if os.path.exists(f):
                    os.remove(f)
            except Exception as cleanup_error:
                print(f"Cleanup failed for {f}: {cleanup_error}")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
