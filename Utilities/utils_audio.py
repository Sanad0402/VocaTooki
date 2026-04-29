import io
import time
from typing import Optional
from google.cloud import texttospeech
from pygame import mixer

GOOGLE_CLOUD_JSON = r"C:\Users\sanad\Downloads\vocatooki-translation-0c42cb154191.json"

_TTS_CLIENT: Optional[texttospeech.TextToSpeechClient] = None
_LAST_AUDIO_BUFFER = None
_AUDIO_READY = False

def init_audio():
    """Call once at suite start."""
    global _TTS_CLIENT, _AUDIO_READY
    if _TTS_CLIENT is None:
        _TTS_CLIENT = texttospeech.TextToSpeechClient.from_service_account_json(GOOGLE_CLOUD_JSON)

    if not _AUDIO_READY:
        # Use a common format that tends to behave well with virtual cable
        mixer.pre_init(frequency=48000, size=-16, channels=1, buffer=1024)
        mixer.init()
        _AUDIO_READY = True

def say(text: str, lang: str = "en-US", wait: bool = True):
    """TTS -> play to default output (VB Cable Input) -> Unity hears it via default mic (VB Cable Output)."""
    if not _AUDIO_READY:
        init_audio()

    synthesis_input = texttospeech.SynthesisInput(text=text)
    voice = texttospeech.VoiceSelectionParams(
        language_code=lang,
        ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL,
    )
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.LINEAR16
    )

    resp = _TTS_CLIENT.synthesize_speech(input=synthesis_input, voice=voice, audio_config=audio_config)

    global _LAST_AUDIO_BUFFER
    _LAST_AUDIO_BUFFER = io.BytesIO(resp.audio_content)
    _LAST_AUDIO_BUFFER.seek(0)

    try: mixer.music.stop()
    except: pass
    try: mixer.music.unload()
    except: pass

    time.sleep(0.05)
    mixer.music.load(_LAST_AUDIO_BUFFER, "wav")
    mixer.music.play()

    if wait:
        while mixer.music.get_busy():
            time.sleep(0.05)
