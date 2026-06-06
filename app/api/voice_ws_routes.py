from __future__ import annotations

import base64
from app.services.tts_service import synthesize_speech_to_file

import asyncio
from queue import Queue
from typing import Iterator

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from google.cloud import speech_v1 as speech

from app.agents.orchestrator_agent import OrchestratorAgent
from app.services.session_store import session_store


router = APIRouter()
orchestrator = OrchestratorAgent()


class AudioStream:
    def __init__(self) -> None:
        self.queue: Queue[bytes | None] = Queue()

    def write(self, chunk: bytes) -> None:
        self.queue.put(chunk)

    def close(self) -> None:
        self.queue.put(None)

    def generator(self) -> Iterator[speech.StreamingRecognizeRequest]:
        while True:
            chunk = self.queue.get()

            if chunk is None:
                return

            yield speech.StreamingRecognizeRequest(audio_content=chunk)


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

    loop = asyncio.get_running_loop()
    audio_stream = AudioStream()
    stop_event = asyncio.Event()

    async def safe_send_json(payload: dict) -> None:
        try:
            await websocket.send_json(payload)
        except Exception:
            pass

    async def receive_audio() -> None:
        try:
            while True:
                chunk = await websocket.receive_bytes()
                audio_stream.write(chunk)

        except WebSocketDisconnect:
            audio_stream.close()
            stop_event.set()

        except Exception as exc:
            audio_stream.close()
            stop_event.set()
            await safe_send_json(
                {
                    "type": "error",
                    "message": f"Audio receive failed: {exc}",
                }
            )

    def run_google_stt_blocking() -> None:
        speech_client = speech.SpeechClient()

        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.WEBM_OPUS,
            sample_rate_hertz=48000,
            language_code="en-IN",
            alternative_language_codes=["hi-IN", "ta-IN"],
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

                    asyncio.run_coroutine_threadsafe(
                        safe_send_json(
                            {
                                "type": "partial" if not result.is_final else "final",
                                "transcript": transcript,
                            }
                        ),
                        loop,
                    )

                    if result.is_final:
                        turn_result = orchestrator.process_turn(
                            state=state,
                            user_text=transcript,
                            channel="realtime_voice",
                        )

                        session_store.save_session(state)

                        asyncio.run_coroutine_threadsafe(
                            safe_send_json(
                                {
                                    "type": "nira_response",
                                    "transcript": transcript,
                                    "response": turn_result.final_response,
                                    "intent": turn_result.intent_result.intent.value,
                                    "agent": turn_result.agent_decision.selected_agent.value,
                                }
                            ),
                            loop,
                        )

        except Exception as exc:
            asyncio.run_coroutine_threadsafe(
                safe_send_json(
                    {
                        "type": "error",
                        "message": str(exc),
                    }
                ),
                loop,
            )

        finally:
            asyncio.run_coroutine_threadsafe(stop_event.set(), loop)

    receiver_task = asyncio.create_task(receive_audio())
    stt_task = asyncio.to_thread(run_google_stt_blocking)

    await asyncio.gather(
        receiver_task,
        stt_task,
        return_exceptions=True,
    )

    audio_stream.close()