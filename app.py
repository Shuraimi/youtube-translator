from flask import Flask, request, jsonify, render_template
import os
import whisper
from gtts import gTTS
import subprocess
import uuid
import requests

# Constants
UPLOAD_FOLDER = "temp"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Flask app setup
app = Flask(__name__, template_folder='templates')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

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
def translate_uploaded_video():
    uploaded_file = request.files.get("file")
    target_lang = request.form.get("lang", "en")

    if not uploaded_file or uploaded_file.filename == '':
        return jsonify({"error": "No file uploaded"}), 400

    video_id = str(uuid.uuid4())
    video_path = os.path.join(UPLOAD_FOLDER, f"{video_id}.mp4")
    audio_path = os.path.join(UPLOAD_FOLDER, f"{video_id}.mp3")
    translated_audio_path = os.path.join(UPLOAD_FOLDER, f"translated_{video_id}.mp3")
    output_video = os.path.join(UPLOAD_FOLDER, f"translated_{video_id}.mp4")

    try:
        uploaded_file.save(video_path)

        # Extract audio
        subprocess.run([
            'ffmpeg', '-y',
            '-i', video_path,
            '-vn', '-acodec', 'mp3', audio_path
        ], check=True)

        # Transcribe
        model = whisper.load_model("base")
        result = model.transcribe(audio_path)
        original_text = result["text"]

        # Translate (optional)
        try:
            translated_text = translate_text(original_text, target_lang)
        except Exception as e:
            return jsonify({"error": f"Translation failed: {e}"}), 500

        # Convert translated text to speech
        tts = gTTS(translated_text, lang=target_lang)
        tts.save(translated_audio_path)

        # Combine video + new audio
        subprocess.run([
            'ffmpeg', '-y',
            '-i', video_path,
            '-i', translated_audio_path,
            '-c:v', 'copy',
            '-map', '0:v:0',
            '-map', '1:a:0',
            '-shortest', output_video
        ], check=True)

        return render_template('index.html', video_url=output_video)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        for f in [audio_path, translated_audio_path]:
            try:
                if os.path.exists(f):
                    os.remove(f)
            except Exception as err:
                print(f"Cleanup error: {err}")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
