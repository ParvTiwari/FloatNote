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
import torch
import whisper

try:
    import soundcard as sc
except Exception:  # pragma: no cover - optional/loopback may be unavailable
    sc = None

from silero_vad import load_silero_vad, get_speech_timestamps
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from ai_modules.chatbot.chatbot import ask_question, ask_question_debug, convert_to_documents, create_vector_store
from ai_modules.summarizer.summarizer import summarize_meeting_result
from database.crud import (
    create_new_meeting,
    get_latest_meeting_data,
    get_meeting_data,
    get_speaker_aliases,
    init_db,
    save_meeting_summary,
    save_to_database,
    set_meeting_title,
    set_speaker_alias,
)

from ai_modules.utils.nlp_processor import process_text
from ai_modules.ocr.ocr_processor import OCRProcessor
from ai_modules.diarization.diarizer import assign_speaker, reset_meeting

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

# --- Meeting / capture control state ---
# Nothing is captured until the user explicitly starts a meeting. Muting a
# source releases its OS audio device (stops the stream), not just discards it.
recording: bool = False
paused: bool = False
mic_muted: bool = False
speaker_muted: bool = False
speaker_enabled: bool = False  # speaker (loopback) capture consent for the meeting
meeting_title: str = "Live FloatNote Meeting"
control_lock: asyncio.Lock = asyncio.Lock()


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
        # Only call task_done() for an item we actually dequeued; calling it in
        # a finally would over-count when get() is cancelled at shutdown.
        payload = await db_queue.get()
        try:
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
    global loop, ocr_processor
    loop = asyncio.get_running_loop()

    # Privacy-first: capture devices are NOT opened at boot. They start only
    # when the user presses Start (see /meetings/start). The OCR processor is
    # constructed up front but only polled by the mic worker while recording.
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

    # Collectors + transcription workers run for the whole process lifetime but
    # stay idle until a meeting is recording and the relevant stream is open.
    asyncio.create_task(audio_collector(queue, buffer))
    asyncio.create_task(audio_collector(speaker_queue, speaker_buffer))
    asyncio.create_task(database_worker_loop())
    asyncio.create_task(transcription_worker(SOURCE_MIC, buffer, with_ocr=True))
    asyncio.create_task(transcription_worker(SOURCE_SPEAKER, speaker_buffer, with_ocr=False))
    print("🟡 Idle — waiting for Start. No audio is being captured.")

    yield

    stop_mic_stream()
    stop_speaker_capture()
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
# Silero VAD: local neural speech detector. Replaces the crude RMS gate so only
# real speech reaches Whisper (kills silence/noise hallucinations, saves CPU).
vad_model = load_silero_vad()
VAD_THRESHOLD = float(os.getenv("VAD_THRESHOLD", "0.5"))
VAD_PAD_MS = 120  # keep a little audio either side of detected speech


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


def start_mic_stream() -> "sd.InputStream | None":
    """Open the microphone input stream (idempotent)."""
    global stream
    if stream is not None:
        return stream
    try:
        stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="float32",
            blocksize=1024,
            callback=audio_callback,
        )
        stream.start()
        print("🎤 Microphone stream started")
    except Exception as exc:  # pragma: no cover - hardware dependent
        print(f"⚠️ Could not start microphone: {exc}")
        stream = None
    return stream


def stop_mic_stream() -> None:
    """Stop and release the microphone device."""
    global stream
    if stream is not None:
        try:
            stream.stop()
            stream.close()
        except Exception:
            pass
        stream = None
        buffer.clear()
        print("🎤 Microphone stream stopped")


def stop_speaker_capture() -> None:
    """Stop and release the loopback (system audio) device."""
    global speaker_thread
    if speaker_thread is not None:
        speaker_stop.set()
        speaker_thread.join(timeout=2.0)
        speaker_thread = None
        speaker_buffer.clear()
        print("🔊 Speaker capture stopped")


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


def _drain_buffer(target_buffer: deque, count: int) -> None:
    for _ in range(min(count, len(target_buffer))):
        try:
            target_buffer.popleft()
        except IndexError:
            break


def _detect_speech(audio_np: np.ndarray):
    """Return the speech-only span of a chunk via Silero VAD, or None.

    Trims leading/trailing silence (with small padding) so Whisper only ever
    sees actual speech — this is what kills the silence/noise hallucinations.
    """
    audio_t = torch.from_numpy(np.ascontiguousarray(audio_np, dtype=np.float32))
    timestamps = get_speech_timestamps(
        audio_t, vad_model, sampling_rate=SAMPLE_RATE, threshold=VAD_THRESHOLD
    )
    if not timestamps:
        return None
    pad = int(SAMPLE_RATE * VAD_PAD_MS / 1000)
    start = max(0, timestamps[0]["start"] - pad)
    end = min(len(audio_np), timestamps[-1]["end"] + pad)
    return audio_np[start:end]


async def transcription_worker(source: str, target_buffer: deque, with_ocr: bool):
    """Continuously transcribe one audio source, persist, and broadcast.

    Idle unless a meeting is recording (not paused) and this source isn't muted.
    Speech is gated by VAD; for the speaker stream each utterance is diarized to
    a stable ``SPEAKER_0X`` label so the UI/DB can tell participants apart.
    """
    print(f"🧠 Transcription worker started for {source}")
    is_mic = source == SOURCE_MIC
    while True:
        muted = mic_muted if is_mic else speaker_muted
        if not recording or paused or active_meeting_id is None or muted:
            await asyncio.sleep(0.15)
            continue
        if len(target_buffer) < CHUNK_SIZE:
            await asyncio.sleep(0.1)
            continue

        # Capture the meeting id now; if it changes (Stop) while we transcribe,
        # we discard the result so nothing is saved/emitted after the meeting ends.
        chunk_meeting_id = active_meeting_id
        audio_np = np.array(target_buffer, dtype=np.float32)[:CHUNK_SIZE]

        # Cheap energy pre-filter: skip dead-silent chunks without running VAD.
        if float(np.sqrt(np.mean(audio_np**2))) <= SILENCE_RMS_THRESHOLD:
            _drain_buffer(target_buffer, CHUNK_SIZE // 4)
            continue

        try:
            speech_audio = await loop.run_in_executor(None, _detect_speech, audio_np)
        except Exception as vad_err:
            print(f"⚠️ VAD error ({source}): {vad_err}")
            speech_audio = audio_np

        if speech_audio is None:
            # No speech in this chunk — drop most of it and move on.
            _drain_buffer(target_buffer, CHUNK_SIZE // 2)
            continue

        def _transcribe(audio: np.ndarray = speech_audio) -> dict:
            return model.transcribe(audio, fp16=False, language="en", temperature=0)

        try:
            result = await loop.run_in_executor(None, _transcribe)
        except Exception as transcribe_err:
            print(f"⚠️ Whisper error ({source}): {transcribe_err}")
            _drain_buffer(target_buffer, CHUNK_SIZE)
            continue

        _drain_buffer(target_buffer, CHUNK_SIZE)

        text = result.get("text", "").strip()
        if len(text) <= 2:
            continue

        # Re-check the gate after the (slow) transcription: drop anything that
        # finished after Stop/Pause/Mute or after the meeting changed.
        muted = mic_muted if is_mic else speaker_muted
        if not recording or paused or muted or active_meeting_id != chunk_meeting_id:
            continue

        if is_mic:
            emit_source = SOURCE_MIC
        else:
            emit_source = await loop.run_in_executor(
                None, assign_speaker, speech_audio, chunk_meeting_id, SOURCE_SPEAKER
            )

        analysis = process_text(text)
        ocr_result = (
            await ocr_processor.process_async()
            if with_ocr and ocr_processor is not None
            else OCR_EMPTY_RESULT
        )
        analysis["ocr"] = ocr_result
        analysis["source"] = emit_source
        analysis["meeting_id"] = chunk_meeting_id

        try:
            await db_queue.put(
                {
                    "meeting_id": chunk_meeting_id,
                    "data": analysis,
                }
            )
        except asyncio.QueueFull:
            print("⚠️ [DB Queue Full] Dropping data packet!")

        await broadcast(analysis)


def status_payload() -> dict:
    return {
        "type": "status",
        "recording": recording,
        "paused": paused,
        "meeting_id": active_meeting_id,
        "title": meeting_title,
        "mic_muted": mic_muted,
        "speaker_muted": speaker_muted,
        "speaker_enabled": speaker_enabled,
    }


async def broadcast_status() -> None:
    await broadcast(status_payload())


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()

    if len(clients) >= MAX_WS_CLIENTS:
        await ws.close(code=1008, reason="Too many clients")
        return

    clients.add(ws)
    print(f"🟢 Client {len(clients)} connected")
    ping_task = None

    # Connecting no longer starts a meeting — the user controls that explicitly.
    # Send the current status snapshot so a fresh client renders the right state.
    await ws.send_json(status_payload())

    try:
        ping_task = asyncio.create_task(ping_client(ws))

        # Transcription + broadcast happen in the per-source background workers;
        # the socket just stays open to receive broadcasts and detect disconnects.
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
        print(f"🔴 Client disconnected. Active: {len(clients)}")


class StartMeetingRequest(BaseModel):
    title: str | None = None
    capture_speaker: bool = False


class MuteRequest(BaseModel):
    source: str  # "mic" or "speaker"
    muted: bool


class TitleRequest(BaseModel):
    title: str


class SpeakerAliasRequest(BaseModel):
    speaker_key: str
    display_name: str


@app.post("/meetings/start")
async def start_meeting(request: StartMeetingRequest):
    global recording, paused, active_meeting_id, meeting_title
    global speaker_enabled, mic_muted, speaker_muted, speaker_thread
    async with control_lock:
        if recording:
            return {"status": "already_recording", **status_payload()}

        meeting_title = (request.title or "").strip() or "Live FloatNote Meeting"
        meeting = await create_new_meeting(title=meeting_title)
        active_meeting_id = meeting.id
        mic_muted = False
        speaker_muted = False
        paused = False

        start_mic_stream()

        speaker_enabled = bool(request.capture_speaker) and ENABLE_SPEAKER
        if speaker_enabled:
            speaker_thread = start_speaker_capture()
            if speaker_thread is None:
                speaker_enabled = False
                print("⚠️ Speaker capture requested but unavailable")

        recording = True
        print(f"🔴 Recording started — meeting #{active_meeting_id} ('{meeting_title}')")
        await broadcast_status()
        return {"status": "recording", **status_payload()}


@app.post("/meetings/pause")
async def pause_meeting():
    global paused
    async with control_lock:
        if recording:
            paused = True
            print("⏸️ Recording paused")
            await broadcast_status()
        return status_payload()


@app.post("/meetings/resume")
async def resume_meeting():
    global paused
    async with control_lock:
        if recording:
            paused = False
            print("▶️ Recording resumed")
            await broadcast_status()
        return status_payload()


@app.post("/meetings/stop")
async def stop_meeting():
    global recording, paused, active_meeting_id, speaker_enabled
    async with control_lock:
        stopped_id = active_meeting_id
        recording = False
        paused = False
        stop_mic_stream()
        stop_speaker_capture()
        if stopped_id is not None:
            reset_meeting(stopped_id)
        speaker_enabled = False
        active_meeting_id = None
        print(f"⏹️ Recording stopped (meeting #{stopped_id})")
        await broadcast_status()
        return {"status": "stopped", "meeting_id": stopped_id}


@app.post("/meetings/mute")
async def mute_source(request: MuteRequest):
    """Mute a source by releasing its OS audio device (strong privacy)."""
    global mic_muted, speaker_muted, speaker_thread
    async with control_lock:
        src = request.source.strip().lower()
        if src == "mic":
            mic_muted = request.muted
            if request.muted:
                stop_mic_stream()
            elif recording:
                start_mic_stream()
        elif src == "speaker":
            speaker_muted = request.muted
            if request.muted:
                stop_speaker_capture()
            elif recording and speaker_enabled:
                speaker_thread = start_speaker_capture()
        else:
            raise HTTPException(status_code=400, detail="source must be 'mic' or 'speaker'")
        print(f"🔇 {src} muted={request.muted}")
        await broadcast_status()
        return status_payload()


@app.post("/meetings/title")
async def update_meeting_title(request: TitleRequest):
    """Set/edit the title of the active meeting (allowed mid-recording)."""
    global meeting_title
    async with control_lock:
        meeting_title = request.title.strip() or "Live FloatNote Meeting"
        if active_meeting_id is not None:
            await set_meeting_title(active_meeting_id, meeting_title)
        await broadcast_status()
        return status_payload()


@app.get("/meetings/{meeting_id}/speakers")
async def list_speakers(meeting_id: int):
    return {"meeting_id": meeting_id, "aliases": await get_speaker_aliases(meeting_id)}


@app.post("/meetings/{meeting_id}/speakers")
async def rename_speaker(meeting_id: int, request: SpeakerAliasRequest):
    name = request.display_name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="display_name cannot be empty")
    aliases = await set_speaker_alias(meeting_id, request.speaker_key.strip(), name)
    await broadcast(
        {
            "type": "speaker_renamed",
            "meeting_id": meeting_id,
            "speaker_key": request.speaker_key.strip(),
            "display_name": name,
        }
    )
    return {"meeting_id": meeting_id, "aliases": aliases}


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
