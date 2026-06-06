from __future__ import annotations

from google.cloud import speech_v1 as speech


def transcribe_audio_bytes(
    audio_bytes: bytes,
    language_code: str = "hi-IN",
    alternative_language_codes: list[str] | None = None,
    encoding: speech.RecognitionConfig.AudioEncoding = speech.RecognitionConfig.AudioEncoding.MP3,
    sample_rate_hertz: int | None = None,
) -> str:
    client = speech.SpeechClient()

    audio = speech.RecognitionAudio(content=audio_bytes)

    config_kwargs = {
        "encoding": encoding,
        "language_code": language_code,
        "alternative_language_codes": alternative_language_codes or ["en-IN"],
        "enable_automatic_punctuation": True,
    }

    if sample_rate_hertz:
        config_kwargs["sample_rate_hertz"] = sample_rate_hertz

    config = speech.RecognitionConfig(**config_kwargs)

    response = client.recognize(
        config=config,
        audio=audio,
    )

    transcripts = []

    for result in response.results:
        if result.alternatives:
            transcripts.append(result.alternatives[0].transcript)

    return " ".join(transcripts).strip()


def detect_audio_encoding(filename: str) -> speech.RecognitionConfig.AudioEncoding:
    lower_name = filename.lower()

    if lower_name.endswith(".wav"):
        return speech.RecognitionConfig.AudioEncoding.LINEAR16

    if lower_name.endswith(".webm"):
        return speech.RecognitionConfig.AudioEncoding.WEBM_OPUS

    if lower_name.endswith(".mp3"):
        return speech.RecognitionConfig.AudioEncoding.MP3

    return speech.RecognitionConfig.AudioEncoding.ENCODING_UNSPECIFIED