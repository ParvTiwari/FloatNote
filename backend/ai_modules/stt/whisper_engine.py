import asyncio
import json
import os
import threading
from collections import deque
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

import numpy as np
import sounddevice as sd
import whisper

try:
    import soundcard as sc
except Exception:  # pragma: no cover - optional/loopback may be unavailable
    sc = None
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from ai_modules.chatbot.chatbot import ask_question, ask_question_debug, convert_to_documents, create_vector_store
from ai_modules.summarizer.summarizer import summarize_meeting_result
from database.crud import (
    create_new_meeting,
    get_latest_meeting_data,
    get_meeting_data,
    init_db,
    save_meeting_summary,
    save_to_database,
)

from ai_modules.utils.nlp_processor import process_text
from ai_modules.ocr.ocr_processor import OCRProcessor

os.environ.setdefault("ENABLE_OCR", "true")
os.environ.setdefault("OCR_INTERVAL_SECONDS", "3.0")
os.environ.setdefault("OCR_CHANGE_THRESHOLD", "0.02")

SAMPLE_RATE = 16000
CHUNK_SECONDS = 3
CHUNK_SIZE = SAMPLE_RATE * CHUNK_SECONDS
BUFFER_SECONDS = 8

SILENCE_RMS_THRESHOLD = 0.015
MAX_WS_CLIENTS = 3
OCR_EMPTY_RESULT = {"text": "", "keywords": []}

# Source labels for the two audio pipelines.
SOURCE_MIC = "MIC"          # the local user's microphone
SOURCE_SPEAKER = "SPEAKER"  # system/loopback audio (remote participants)

# System-output (loopback) capture can run at the render device's native rate
# (commonly 48 kHz stereo); we downmix + resample to SAMPLE_RATE for Whisper.
ENABLE_SPEAKER = os.getenv("ENABLE_SPEAKER", "true").strip().lower() == "true"

loop: asyncio.AbstractEventLoop | None = None
stream: sd.InputStream | None = None
speaker_thread: threading.Thread | None = None
speaker_stop = threading.Event()
clients: set[WebSocket] = set()
ocr_processor: OCRProcessor | None = None
queue: asyncio.Queue = asyncio.Queue(maxsize=100)
buffer: deque = deque(maxlen=SAMPLE_RATE * BUFFER_SECONDS)
speaker_queue: asyncio.Queue = asyncio.Queue(maxsize=100)
speaker_buffer: deque = deque(maxlen=SAMPLE_RATE * BUFFER_SECONDS)
db_queue: asyncio.Queue = asyncio.Queue(maxsize=100)
active_meeting_id: int | None = None
DEBUG_EXPORT_DIR = Path(__file__).resolve().parents[2] / "debug_exports"


class ChatRequest(BaseModel):
    question: str


async def wait_for_pending_meeting_writes():
    if db_queue.qsize() > 0:
        print(f"⏳ Waiting for {db_queue.qsize()} pending DB write(s) before answering...")
    await db_queue.join()


async def load_meeting_payload(meeting_id: int | None = None) -> dict:
    meeting_payload = (
        await get_meeting_data(meeting_id)
        if meeting_id is not None
        else await get_latest_meeting_data()
    )
    if meeting_payload is None:
        raise HTTPException(status_code=404, detail="Meeting not found.")
    if not meeting_payload["items"]:
        raise HTTPException(status_code=400, detail="Meeting has no captured data yet.")
    return meeting_payload


def _write_debug_export(meeting_id: int, kind: str, payload: dict) -> str:
    DEBUG_EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = DEBUG_EXPORT_DIR / f"meeting_{meeting_id}_{kind}_{timestamp}.json"
    file_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return str(file_path)


def _build_meeting_debug_payload(meeting_payload: dict) -> dict:
    docs = convert_to_documents(meeting_payload["items"])
    summary_result = summarize_meeting_result(meeting_payload["items"])
    return {
        "meeting_id": meeting_payload["meeting_id"],
        "title": meeting_payload["title"],
        "saved_summary": meeting_payload.get("summary"),
        "fresh_summary_result": summary_result,
        "captured_items": meeting_payload["items"],
        "document_count": len(docs),
        "documents": [doc.page_content for doc in docs],
    }


async def database_worker_loop():
    print("💾 Database worker started. Waiting for live data...")
    while True:
        try:
            payload = await db_queue.get()
            await save_to_database(
                payload["data"],
                meeting_id=payload.get("meeting_id"),
            )
        except Exception as e:
            print(f"[DB Worker Error]: {e}")
        finally:
            db_queue.task_done()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    print("🗄️  Database initialized")
    global loop, stream, speaker_thread, ocr_processor
    loop = asyncio.get_running_loop()
    stream = sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="float32",
        blocksize=1024,
        callback=audio_callback,
    )
    stream.start()
    print("🎤 Microphone started")

    if ENABLE_SPEAKER:
        speaker_thread = start_speaker_capture()
        if speaker_thread is not None:
            print("🔊 Speaker (system audio) capture started")
        else:
            print("⚠️ Speaker capture unavailable — continuing with microphone only")
    else:
        print("⚠️ Speaker capture disabled because ENABLE_SPEAKER is not true")

    if os.getenv("ENABLE_OCR", "false").strip().lower() == "true":
        ocr_processor = OCRProcessor(
            check_interval=float(os.getenv("OCR_INTERVAL_SECONDS", "1.0")),
            change_threshold=float(os.getenv("OCR_CHANGE_THRESHOLD", "0.02")),
        )
        print(
            f"🖥️  OCR enabled | monitor_index={ocr_processor.monitor_index} "
            f"interval={ocr_processor.check_interval}s"
        )
    else:
        print("⚠️ OCR disabled because ENABLE_OCR is not true")

    asyncio.create_task(audio_collector(queue, buffer))
    asyncio.create_task(database_worker_loop())
    # One transcription worker per source. OCR is attached to the mic worker
    # only so a slide is captured once per chunk (not duplicated per stream).
    asyncio.create_task(transcription_worker(SOURCE_MIC, buffer, with_ocr=True))
    if speaker_thread is not None:
        asyncio.create_task(audio_collector(speaker_queue, speaker_buffer))
        asyncio.create_task(
            transcription_worker(SOURCE_SPEAKER, speaker_buffer, with_ocr=False)
        )

    yield

    if stream:
        stream.stop()
        stream.close()
    if speaker_thread is not None:
        speaker_stop.set()
        speaker_thread.join(timeout=2.0)
    if ocr_processor:
        ocr_processor.stop_background()
        ocr_processor = None


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
model = whisper.load_model("base")


def audio_callback(indata, frames, time, status):
    if status:
        print(f"⚠️ Audio status: {status}")
        return
    if loop is None:
        return
    audio = indata[:, 0].copy()
    if not queue.full():
        try:
            loop.call_soon_threadsafe(queue.put_nowait, audio)
        except RuntimeError:
            pass


def _speaker_capture_loop():
    """Capture system/loopback audio in a background thread.

    Uses `soundcard`'s WASAPI loopback microphone (the default speaker captured
    as an input) so it records whatever is playing through the speakers — i.e.
    remote meeting participants. Records mono at SAMPLE_RATE (soundcard resamples
    internally) and feeds chunks into `speaker_queue`, mirroring the mic path.
    """
    try:
        speaker = sc.default_speaker()
        mic = sc.get_microphone(id=str(speaker.name), include_loopback=True)
        print(f"🔊 Loopback target: '{speaker.name}'")
        with mic.recorder(samplerate=SAMPLE_RATE, channels=1, blocksize=1024) as rec:
            while not speaker_stop.is_set():
                data = rec.record(numframes=4096)  # blocks until available
                if loop is None or speaker_queue.full():
                    continue
                samples = (
                    data[:, 0] if getattr(data, "ndim", 1) > 1 else data
                ).astype(np.float32, copy=False)
                try:
                    loop.call_soon_threadsafe(speaker_queue.put_nowait, samples)
                except RuntimeError:
                    pass
    except Exception as exc:  # pragma: no cover - hardware/host dependent
        print(f"⚠️ Speaker loopback capture stopped: {exc}")


def start_speaker_capture() -> threading.Thread | None:
    """Start the loopback capture thread, or return None if unsupported."""
    if sc is None:
        print("⚠️ `soundcard` not installed; cannot capture system audio")
        return None
    try:
        # Probe that a loopback device can be opened before committing.
        speaker = sc.default_speaker()
        sc.get_microphone(id=str(speaker.name), include_loopback=True)
    except Exception as exc:  # pragma: no cover - hardware/host dependent
        print(f"⚠️ Speaker loopback unavailable: {exc}")
        return None

    speaker_stop.clear()
    thread = threading.Thread(
        target=_speaker_capture_loop, name="speaker-capture", daemon=True
    )
    thread.start()
    return thread


async def audio_collector(source_queue: asyncio.Queue, target_buffer: deque):
    while True:
        try:
            samples = await asyncio.wait_for(source_queue.get(), timeout=1.0)
            target_buffer.extend(samples)
            source_queue.task_done()
        except asyncio.TimeoutError:
            continue


async def broadcast(payload: dict):
    disconnected: list[WebSocket] = []
    for client_ws in list(clients):
        try:
            await client_ws.send_json(payload)
        except Exception:
            disconnected.append(client_ws)
    for dead in disconnected:
        clients.discard(dead)


async def transcription_worker(source: str, target_buffer: deque, with_ocr: bool):
    """Continuously transcribe one audio source, persist, and broadcast.

    Runs only while a meeting is active (i.e. a client is connected). Each
    emitted packet carries a `source` label so the UI/DB can tell the local
    microphone apart from remote participants captured via system audio.
    """
    print(f"🧠 Transcription worker started for {source}")
    while True:
        if active_meeting_id is None or len(target_buffer) < CHUNK_SIZE:
            await asyncio.sleep(0.1)
            continue

        audio_np = np.array(target_buffer, dtype=np.float32)[:CHUNK_SIZE]
        current_volume = float(np.sqrt(np.mean(audio_np**2)))

        if current_volume <= SILENCE_RMS_THRESHOLD:
            for _ in range(min(CHUNK_SIZE // 4, len(target_buffer))):
                try:
                    target_buffer.popleft()
                except IndexError:
                    break
            continue

        def _transcribe(audio: np.ndarray = audio_np) -> dict:
            return model.transcribe(
                audio,
                fp16=False,
                language="en",
                temperature=0,
            )

        try:
            result = await loop.run_in_executor(None, _transcribe)
        except Exception as transcribe_err:
            print(f"⚠️ Whisper error ({source}): {transcribe_err}")
            continue

        for _ in range(min(CHUNK_SIZE, len(target_buffer))):
            try:
                target_buffer.popleft()
            except IndexError:
                break

        text = result.get("text", "").strip()
        if len(text) <= 2:
            continue

        analysis = process_text(text)
        ocr_result = (
            await ocr_processor.process_async()
            if with_ocr and ocr_processor is not None
            else OCR_EMPTY_RESULT
        )
        analysis["ocr"] = ocr_result
        analysis["source"] = source
        analysis["meeting_id"] = active_meeting_id

        try:
            await db_queue.put(
                {
                    "meeting_id": active_meeting_id,
                    "data": analysis,
                }
            )
        except asyncio.QueueFull:
            print("⚠️ [DB Queue Full] Dropping data packet!")

        await broadcast(analysis)


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    global active_meeting_id
    await ws.accept()

    if len(clients) >= MAX_WS_CLIENTS:
        await ws.close(code=1008, reason="Too many clients")
        return

    if active_meeting_id is None:
        active_meeting = await create_new_meeting()
        active_meeting_id = active_meeting.id
        print(f"🆕 Started meeting #{active_meeting_id}")

    clients.add(ws)
    print(f"🟢 Client {len(clients)} connected")
    ping_task = None

    await ws.send_json(
        {
            "type": "connected",
            "meeting_id": active_meeting_id,
        }
    )

    try:
        ping_task = asyncio.create_task(ping_client(ws))

        # Transcription + broadcast now happen in the per-source background
        # workers; the socket just stays open to receive broadcasts and detect
        # disconnects. receive() returns when the client goes away.
        while True:
            await ws.receive_text()

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        clients.discard(ws)
        if ping_task is not None:
            ping_task.cancel()
        if not clients:
            active_meeting_id = None
            print("🔁 Active meeting closed. Next connection will create a new meeting.")
        print(f"🔴 Client disconnected. Active: {len(clients)}")


@app.get("/meetings/latest/summary")
async def get_latest_meeting_summary():
    await wait_for_pending_meeting_writes()
    meeting_payload = await load_meeting_payload()
    summary_result = summarize_meeting_result(meeting_payload["items"])
    await save_meeting_summary(meeting_payload["meeting_id"], summary_result["summary"])
    return {
        "meeting_id": meeting_payload["meeting_id"],
        "title": meeting_payload["title"],
        "summary": summary_result["summary"],
        "summary_source": summary_result["source"],
        "summary_model": summary_result["model"],
        "used_groq": summary_result["used_groq"],
        "used_huggingface": summary_result["used_huggingface"],
        "summary_error": summary_result["error"],
    }


@app.get("/meetings/{meeting_id}/summary")
async def get_meeting_summary(meeting_id: int):
    await wait_for_pending_meeting_writes()
    meeting_payload = await load_meeting_payload(meeting_id)
    summary_result = summarize_meeting_result(meeting_payload["items"])
    await save_meeting_summary(meeting_id, summary_result["summary"])
    return {
        "meeting_id": meeting_payload["meeting_id"],
        "title": meeting_payload["title"],
        "summary": summary_result["summary"],
        "summary_source": summary_result["source"],
        "summary_model": summary_result["model"],
        "used_groq": summary_result["used_groq"],
        "used_huggingface": summary_result["used_huggingface"],
        "summary_error": summary_result["error"],
    }


@app.post("/meetings/latest/chat")
async def chat_with_latest_meeting(request: ChatRequest):
    await wait_for_pending_meeting_writes()
    meeting_payload = await load_meeting_payload()
    docs = convert_to_documents(meeting_payload["items"])
    vector_db = create_vector_store(docs)
    answer = ask_question(request.question, vector_db)
    return {
        "meeting_id": meeting_payload["meeting_id"],
        "title": meeting_payload["title"],
        "question": request.question,
        "answer": answer,
    }


@app.post("/meetings/{meeting_id}/chat")
async def chat_with_meeting(meeting_id: int, request: ChatRequest):
    await wait_for_pending_meeting_writes()
    meeting_payload = await load_meeting_payload(meeting_id)
    docs = convert_to_documents(meeting_payload["items"])
    vector_db = create_vector_store(docs)
    answer = ask_question(request.question, vector_db)
    return {
        "meeting_id": meeting_payload["meeting_id"],
        "title": meeting_payload["title"],
        "question": request.question,
        "answer": answer,
    }


@app.get("/meetings/latest/debug/export")
async def export_latest_meeting_debug():
    await wait_for_pending_meeting_writes()
    meeting_payload = await load_meeting_payload()
    debug_payload = _build_meeting_debug_payload(meeting_payload)
    export_path = _write_debug_export(
        meeting_payload["meeting_id"],
        "snapshot",
        debug_payload,
    )
    return {
        "meeting_id": meeting_payload["meeting_id"],
        "title": meeting_payload["title"],
        "export_path": export_path,
        "debug": debug_payload,
    }


@app.get("/meetings/{meeting_id}/debug/export")
async def export_meeting_debug(meeting_id: int):
    await wait_for_pending_meeting_writes()
    meeting_payload = await load_meeting_payload(meeting_id)
    debug_payload = _build_meeting_debug_payload(meeting_payload)
    export_path = _write_debug_export(
        meeting_payload["meeting_id"],
        "snapshot",
        debug_payload,
    )
    return {
        "meeting_id": meeting_payload["meeting_id"],
        "title": meeting_payload["title"],
        "export_path": export_path,
        "debug": debug_payload,
    }


@app.post("/meetings/latest/chat/debug")
async def chat_with_latest_meeting_debug(request: ChatRequest):
    await wait_for_pending_meeting_writes()
    meeting_payload = await load_meeting_payload()
    docs = convert_to_documents(meeting_payload["items"])
    vector_db = create_vector_store(docs)
    chat_debug = ask_question_debug(request.question, vector_db)
    debug_payload = {
        "meeting_id": meeting_payload["meeting_id"],
        "title": meeting_payload["title"],
        "captured_items": meeting_payload["items"],
        "documents": [doc.page_content for doc in docs],
        "chat_debug": chat_debug,
    }
    export_path = _write_debug_export(
        meeting_payload["meeting_id"],
        "chat_debug",
        debug_payload,
    )
    return {
        "meeting_id": meeting_payload["meeting_id"],
        "title": meeting_payload["title"],
        "export_path": export_path,
        **chat_debug,
    }


@app.post("/meetings/{meeting_id}/chat/debug")
async def chat_with_meeting_debug(meeting_id: int, request: ChatRequest):
    await wait_for_pending_meeting_writes()
    meeting_payload = await load_meeting_payload(meeting_id)
    docs = convert_to_documents(meeting_payload["items"])
    vector_db = create_vector_store(docs)
    chat_debug = ask_question_debug(request.question, vector_db)
    debug_payload = {
        "meeting_id": meeting_payload["meeting_id"],
        "title": meeting_payload["title"],
        "captured_items": meeting_payload["items"],
        "documents": [doc.page_content for doc in docs],
        "chat_debug": chat_debug,
    }
    export_path = _write_debug_export(
        meeting_payload["meeting_id"],
        "chat_debug",
        debug_payload,
    )
    return {
        "meeting_id": meeting_payload["meeting_id"],
        "title": meeting_payload["title"],
        "export_path": export_path,
        **chat_debug,
    }


async def ping_client(ws: WebSocket):
    while True:
        try:
            await asyncio.sleep(25)
            await ws.ping()
        except Exception:
            break


def run_server(host: str = "0.0.0.0", port: int = 8000):
    import uvicorn

    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_server()
