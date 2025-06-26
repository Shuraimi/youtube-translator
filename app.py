from flask import Flask, request, jsonify, render_template
import os
from pytube import YouTube
import whisper
from gtts import gTTS
import subprocess
import uuid
import requests

# Constants
UPLOAD_FOLDER = "temp"

# Create upload folder if not exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# App setup
app = Flask(__name__, template_folder='templates')

# Translation function using LibreTranslate
def translate_text(text, target_lang):
    response = requests.post(
        "https://libretranslate.com/translate",
        params={"q": text, "source": "auto", "target": target_lang, "format": "text"}
    )
    if response.status_code == 200:
        return response.json()["translatedText"]
    else:
        raise Exception(f"Translation failed: {response.text}")

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
    temp_audio_mp4 = os.path.join(UPLOAD_FOLDER, f"{video_id}_audio.mp4")

    try:
        # Download audio using pytube
        yt = YouTube(youtube_url)
        audio_stream = yt.streams.filter(only_audio=True).first()
        audio_stream.download(output_path=UPLOAD_FOLDER, filename=f"{video_id}_audio.mp4")

        # Convert to mp3 using ffmpeg
        subprocess.run([
            'ffmpeg', '-y',
            '-i', temp_audio_mp4,
            '-vn', '-acodec', 'mp3', audio_path
        ], check=True)

        # Transcribe using Whisper
        model = whisper.load_model("base")
        result = model.transcribe(audio_path)
        original_text = result["text"]

        # Translate
        translated_text = translate_text(original_text, target_lang)

        # Convert translated text to speech
        tts = gTTS(translated_text, lang=target_lang)
        tts.save(translated_audio_path)

        # Download full video using pytube
        video_stream = yt.streams.filter(progressive=True, file_extension='mp4') \
            .order_by('resolution').desc().first()
        video_stream.download(output_path=UPLOAD_FOLDER, filename=f"{video_id}_video.mp4")

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
        # Cleanup intermediate files
        for f in [temp_audio_mp4, audio_path, video_path, translated_audio_path]:
            try:
                if os.path.exists(f):
                    os.remove(f)
            except Exception as cleanup_error:
                print(f"Cleanup failed for {f}: {cleanup_error}")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
