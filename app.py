from flask import Flask, request, jsonify, send_file, render_template
import os
import yt_dlp
import whisper
from googletrans import Translator
from gtts import gTTS
import subprocess
import uuid

app = Flask(__name__, template_folder='templates')
UPLOAD_FOLDER = "temp"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/translate', methods=['POST'])
def translate_video():
    youtube_url = request.form.get("url")
    target_lang = request.form.get("lang", "en")  # Default to English

    if not youtube_url:
        return jsonify({"error": "Missing YouTube URL"}), 400

    video_id = str(uuid.uuid4())
    audio_path = os.path.join(UPLOAD_FOLDER, f"{video_id}.mp3")
    video_path = os.path.join(UPLOAD_FOLDER, f"{video_id}.mp4")
    output_video = os.path.join(UPLOAD_FOLDER, f"translated_{video_id}.mp4")
    translated_audio_path = os.path.join(UPLOAD_FOLDER, f"translated_{video_id}.mp3")

    try:
        # Download video and extract audio
        ydl_opts = {
    'format': 'bestaudio/best',
    'outtmpl': audio_path,
    'cookies': 'cookies.txt',  # ✅ This goes here — top-level
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
    }]
}

with yt_dlp.YoutubeDL(ydl_opts) as ydl:
    ydl.download([youtube_url])


        # Transcribe audio
        model = whisper.load_model("base")
        result = model.transcribe(audio_path)
        original_text = result["text"]

        # Translate text
        translator = Translator()
        translated_text = translator.translate(original_text, dest=target_lang).text

        # Text to Speech
        tts = gTTS(translated_text, lang=target_lang)
        tts.save(translated_audio_path)

        # Download original video
        ydl_opts_video = {
            'format': 'bestvideo+bestaudio/best',
            'outtmpl': video_path
        }
        with yt_dlp.YoutubeDL(ydl_opts_video) as ydl:
            ydl.download([youtube_url])

        # Replace original audio with translated one
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
            if os.path.exists(f):
                os.remove(f)

import os

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  # Use Render's assigned port
    app.run(host="0.0.0.0", port=port)
