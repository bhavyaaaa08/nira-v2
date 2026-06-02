import os
import json
import google.auth
from google.cloud import texttospeech

print("GOOGLE_APPLICATION_CREDENTIALS:", os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"))
print("GOOGLE_CLOUD_PROJECT:", os.environ.get("GOOGLE_CLOUD_PROJECT"))
print("GCLOUD_PROJECT:", os.environ.get("GCLOUD_PROJECT"))

path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
if path:
    data = json.load(open(path))
    print("JSON project_id:", data.get("project_id"))
    print("JSON client_email:", data.get("client_email"))

credentials, project = google.auth.default()
print("google.auth.default project:", project)
print("credentials quota_project_id:", getattr(credentials, "quota_project_id", None))

client = texttospeech.TextToSpeechClient(credentials=credentials)

response = client.synthesize_speech(
    input=texttospeech.SynthesisInput(text="Hello from NIRA"),
    voice=texttospeech.VoiceSelectionParams(language_code="en-US"),
    audio_config=texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3
    ),
)

with open("debug_tts.mp3", "wb") as f:
    f.write(response.audio_content)

print("TTS success: debug_tts.mp3 created")