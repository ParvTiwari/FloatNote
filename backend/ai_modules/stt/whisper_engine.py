import asyncio
import os
from collections import deque
from contextlib import asynccontextmanager

import numpy as np
import sounddevice as sd
import whisper
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from database.crud import create_new_meeting, init_db, save_to_database

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

loop: asyncio.AbstractEventLoop | None = None
stream: sd.InputStream | None = None
clients: set[WebSocket] = set()
ocr_processor: OCRProcessor | None = None
queue: asyncio.Queue = asyncio.Queue(maxsize=100)
buffer: deque = deque(maxlen=SAMPLE_RATE * BUFFER_SECONDS)
db_queue: asyncio.Queue = asyncio.Queue(maxsize=100)
active_meeting_id: int | None = None


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
    print("🗄️ Database initialized")
    global loop, stream, ocr_processor
    loop = asyncio.get_running_loop()
    stream = sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="float32",
        blocksize=1024,
        callback=audio_callback,
    )
    stream.start()
    if os.getenv("ENABLE_OCR", "false").strip().lower() == "true":
        ocr_processor = OCRProcessor(
            check_interval=float(os.getenv("OCR_INTERVAL_SECONDS", "1.0")),
            change_threshold=float(os.getenv("OCR_CHANGE_THRESHOLD", "0.02")),
        )
        print(
            f"🖥️ OCR enabled | monitor_index={ocr_processor.monitor_index} "
            f"interval={ocr_processor.check_interval}s"
        )
    else:
        print("⚠️ OCR disabled because ENABLE_OCR is not true")

    asyncio.create_task(audio_collector())
    asyncio.create_task(database_worker_loop())
    print("🎤 Microphone started")

    yield

    if stream:
        stream.stop()
        stream.close()
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


async def audio_collector():
    while True:
        try:
            samples = await asyncio.wait_for(queue.get(), timeout=1.0)
            buffer.extend(samples)
            queue.task_done()
        except asyncio.TimeoutError:
            continue


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

        while True:
            if len(buffer) < CHUNK_SIZE:
                await asyncio.sleep(0.1)
                continue

            audio_np = np.array(buffer, dtype=np.float32)[:CHUNK_SIZE]
            current_volume = float(np.sqrt(np.mean(audio_np**2)))

            if current_volume > 0.0005:
                print(
                    f"🔊 [DEBUG] Mic Volume: {current_volume:.5f} "
                    f"(Required: > {SILENCE_RMS_THRESHOLD})"
                )

            if current_volume <= SILENCE_RMS_THRESHOLD:
                for _ in range(min(CHUNK_SIZE // 4, len(buffer))):
                    try:
                        buffer.popleft()
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
                print("🧠 [DEBUG] Sending to Whisper for processing...")
                result = await loop.run_in_executor(None, _transcribe)
            except Exception as transcribe_err:
                print(f"⚠️ Whisper error: {transcribe_err}")
                continue

            for _ in range(min(CHUNK_SIZE, len(buffer))):
                try:
                    buffer.popleft()
                except IndexError:
                    break

            text = result.get("text", "").strip()
            if len(text) <= 2:
                continue

            analysis = process_text(text)
            ocr_result = (
                await ocr_processor.process_async()
                if ocr_processor is not None
                else OCR_EMPTY_RESULT
            )
            analysis["ocr"] = ocr_result
            analysis["meeting_id"] = active_meeting_id

            print(
                f"📤 Broadcasting text='{text[:60]}' | "
                f"ocr_len={len(ocr_result['text'])} "
                f"ocr_keywords={ocr_result['keywords'][:3]}"
            )

            try:
                await db_queue.put(
                    {
                        "meeting_id": active_meeting_id,
                        "data": analysis,
                    }
                )
            except asyncio.QueueFull:
                print("⚠️ [DB Queue Full] Dropping data packet!")

            disconnected: list[WebSocket] = []
            for client_ws in list(clients):
                try:
                    await client_ws.send_json(analysis)
                except Exception:
                    disconnected.append(client_ws)

            for dead in disconnected:
                clients.discard(dead)

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
