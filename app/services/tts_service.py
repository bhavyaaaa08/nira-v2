from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from google.cloud import texttospeech


VOICE_MAP = {
    "hi-IN": "hi-IN-Wavenet-D",      # confirmed FEMALE
    "en-IN": "en-IN-Neural2-A",      # female
    "ta-IN": "ta-IN-Standard-D",     # likely female, but verify later
}


def synthesize_speech_to_file(
    text: str,
    output_dir: str = "tmp_audio",
    language_code: str = "hi-IN",
    voice_name: str | None = None,
) -> str:
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    output_path = Path(output_dir) / f"nira_tts_{uuid4().hex}.mp3"

    client = texttospeech.TextToSpeechClient()

    selected_voice = voice_name or VOICE_MAP.get(language_code)

    if not selected_voice:
        selected_voice = "hi-IN-Wavenet-D"

    print(f"[GCP TTS] language_code={language_code}, voice={selected_voice}")

    response = client.synthesize_speech(
        input=texttospeech.SynthesisInput(text=text),
        voice=texttospeech.VoiceSelectionParams(
            language_code=language_code,
            name=selected_voice,
        ),
        audio_config=texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            speaking_rate=1.0,
        ),
    )

    output_path.write_bytes(response.audio_content)
    return str(output_path)