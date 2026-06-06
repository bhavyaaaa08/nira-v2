from __future__ import annotations

import asyncio
import base64
from queue import Queue
from typing import Iterator

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from google.cloud import speech_v1 as speech

from app.agents.orchestrator_agent import OrchestratorAgent
from app.services.session_store import session_store
from app.services.tts_service import synthesize_speech_to_file
from app.services.audit_logger import audit_logger


router = APIRouter()
orchestrator = OrchestratorAgent()


class AudioStream:
    def __init__(self) -> None:
        self.queue: Queue[bytes | None] = Queue()
        self.closed = False

    def write(self, chunk: bytes) -> None:
        if not self.closed:
            self.queue.put(chunk)

    def close(self) -> None:
        if not self.closed:
            self.closed = True
            self.queue.put(None)

    def generator(self) -> Iterator[speech.StreamingRecognizeRequest]:
        while True:
            chunk = self.queue.get()

            if chunk is None:
                return

            yield speech.StreamingRecognizeRequest(audio_content=chunk)


def stt_language_config_for_state(state) -> tuple[str, list[str]]:
    language = getattr(getattr(state, "language", None), "value", "en")

    if language == "ta":
        return "ta-IN", ["en-IN", "hi-IN"]

    if language in {"hi", "hinglish"}:
        return "hi-IN", ["en-IN", "ta-IN"]

    return "en-IN", ["hi-IN", "ta-IN"]


def tts_language_for_state(state) -> str:
    language = getattr(getattr(state, "language", None), "value", "en")

    if language == "ta":
        return "ta-IN"

    if language in {"hi", "hinglish"}:
        return "hi-IN"

    return "en-IN"


@router.websocket("/ws/voice/{session_id}")
async def realtime_voice_ws(websocket: WebSocket, session_id: str):
    await websocket.accept()

    state = session_store.get_session(session_id)
    if not state:
        await websocket.send_json(
            {
                "type": "error",
                "message": "Invalid session_id. Create a call session first.",
            }
        )
        await websocket.close()
        return
    
    audit_logger.log_event(
        session_id=session_id,
        event_type="realtime_voice_connected",
        source="voice_ws_routes",
        payload={
            "message": "Realtime voice WebSocket connected.",
        },
    )

    loop = asyncio.get_running_loop()

    active_stream: AudioStream | None = None
    active_stt_task: asyncio.Task | None = None
    background_tasks: set[asyncio.Task] = set()

    async def safe_send_json(payload: dict) -> None:
        try:
            await websocket.send_json(payload)
        except Exception:
            pass

    def send_json_from_thread(payload: dict) -> None:
        asyncio.run_coroutine_threadsafe(
            safe_send_json(payload),
            loop,
        )

    def run_google_stt_blocking(audio_stream: AudioStream) -> None:
        speech_client = speech.SpeechClient()

        language_code, alternative_language_codes = stt_language_config_for_state(state)

        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.WEBM_OPUS,
            sample_rate_hertz=48000,
            language_code=language_code,
            alternative_language_codes=alternative_language_codes,
            enable_automatic_punctuation=True,
        )

        streaming_config = speech.StreamingRecognitionConfig(
            config=config,
            interim_results=True,
            single_utterance=False,
        )

        try:
            responses = speech_client.streaming_recognize(
                config=streaming_config,
                requests=audio_stream.generator(),
            )

            for response in responses:
                for result in response.results:
                    if not result.alternatives:
                        continue

                    transcript = result.alternatives[0].transcript.strip()

                    if not transcript:
                        continue

                    send_json_from_thread(
                        {
                            "type": "partial" if not result.is_final else "final",
                            "transcript": transcript,
                        }
                    )

                    if not result.is_final:
                        continue

                    turn_result = orchestrator.process_turn(
                        state=state,
                        user_text=transcript,
                        channel="realtime_voice",
                    )

                    session_store.save_session(state)

                    send_json_from_thread(
                        {
                            "type": "nira_response",
                            "transcript": transcript,
                            "response": turn_result.final_response,
                            "intent": turn_result.intent_result.intent.value,
                            "agent": turn_result.agent_decision.selected_agent.value,
                        }
                    )

                    audio_path = synthesize_speech_to_file(
                        text=turn_result.final_response,
                        language_code=tts_language_for_state(state),
                    )

                    with open(audio_path, "rb") as audio_file:
                        audio_base64 = base64.b64encode(
                            audio_file.read()
                        ).decode("utf-8")

                    send_json_from_thread(
                        {
                            "type": "tts_audio",
                            "audio_base64": audio_base64,
                            "mime_type": "audio/mp3",
                        }
                    )

                    send_json_from_thread(
                        {
                            "type": "tts_audio",
                            "audio_base64": audio_base64,
                            "mime_type": "audio/mp3",
                        }
                    )

        except Exception as exc:
            message = str(exc)

            # This can still happen if a stream is opened and no real audio follows.
            # It should no longer happen just because the WebSocket connected.
            send_json_from_thread(
                {
                    "type": "error",
                    "message": message,
                }
            )

    def track_task(task: asyncio.Task) -> None:
        background_tasks.add(task)
        task.add_done_callback(background_tasks.discard)

    async def start_audio_stream_if_needed() -> AudioStream:
        nonlocal active_stream, active_stt_task

        if active_stream is not None:
            return active_stream

        active_stream = AudioStream()
        active_stt_task = asyncio.create_task(
            asyncio.to_thread(run_google_stt_blocking, active_stream)
        )
        track_task(active_stt_task)

        await safe_send_json(
            {
                "type": "stream_started",
                "message": "Google STT stream started.",
            }
        )

        audit_logger.log_event(
            session_id=session_id,
            event_type="voice_stream_started",
            source="voice_ws_routes",
            payload={
                "message": "Google STT stream started.",
            },
        )

        return active_stream

    async def close_active_audio_stream() -> None:
        nonlocal active_stream

        if active_stream is None:
            return

        active_stream.close()
        active_stream = None

        await safe_send_json(
            {
                "type": "stream_stopped",
                "message": "Google STT stream stopped.",
            }
        )

        audit_logger.log_event(
            session_id=session_id,
            event_type="voice_stream_stopped",
            source="voice_ws_routes",
            payload={
                "message": "Google STT stream stopped.",
            },
        )
    try:
        while True:
            message = await websocket.receive()

            if "text" in message:
                text_message = message["text"]

                if text_message == "START_STREAM":
                    await start_audio_stream_if_needed()
                    continue

                if text_message == "STOP_STREAM":
                    await close_active_audio_stream()
                    continue

            if "bytes" in message and message["bytes"]:
                stream = await start_audio_stream_if_needed()
                stream.write(message["bytes"])

    except WebSocketDisconnect:
        await close_active_audio_stream()
        audit_logger.log_event(
            session_id=session_id,
            event_type="realtime_voice_disconnected",
            source="voice_ws_routes",
            payload={
                "message": "Realtime voice WebSocket disconnected.",
            },
        )

    except Exception as exc:
        await close_active_audio_stream()
        await safe_send_json(
            {
                "type": "error",
                "message": f"Realtime voice WebSocket failed: {exc}",
            }
        )

        audit_logger.log_event(
            session_id=session_id,
            event_type="realtime_voice_error",
            source="voice_ws_routes",
            payload={
                "error": str(exc),
            },
        )

    finally:
        if active_stream is not None:
            active_stream.close()

        for task in list(background_tasks):
            if not task.done():
                task.cancel()