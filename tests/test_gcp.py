from google.cloud import texttospeech

client = texttospeech.TextToSpeechClient()

response = client.synthesize_speech(
    input=texttospeech.SynthesisInput(text="Hello from NIRA"),
    voice=texttospeech.VoiceSelectionParams(
        language_code="en-US"
    ),
    audio_config=texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3
    ),
)

with open("test.mp3", "wb") as f:
    f.write(response.audio_content)

print("Success")