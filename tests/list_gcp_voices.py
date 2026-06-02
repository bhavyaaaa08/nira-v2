from google.cloud import texttospeech

client = texttospeech.TextToSpeechClient()

response = client.list_voices(
    language_code="hi-IN",
)

for voice in response.voices:
    print(voice.name, voice.ssml_gender.name)