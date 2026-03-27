import asyncio
import os
import sys
import numpy as np
import sounddevice as sd
import whisper
from collections import deque
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from contextlib import asynccontextmanager

utils_path = os.path.join(os.path.dirname(__file__), '../utils')
sys.path.insert(0, utils_path)
from nlp_processor import process_text
from ai_modules.ocr.ocr_processor import OCRProcessor

os.environ.setdefault("ENABLE_OCR", "true")
os.environ.setdefault("OCR_INTERVAL_SECONDS", "1.0")
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

# ---------------- LIFESPAN ----------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    global loop, stream, ocr_processor
    loop = asyncio.get_running_loop()
    stream = sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="float32",
        blocksize=1024,
        callback=audio_callback
    )
    stream.start()
    if os.getenv("ENABLE_OCR", "false").strip().lower() == "true":
        ocr_processor = OCRProcessor(
            check_interval=float(os.getenv("OCR_INTERVAL_SECONDS", "1.0")),
            change_threshold=float(os.getenv("OCR_CHANGE_THRESHOLD", "0.02")),
        )
        print(f"🖥️  OCR enabled — monitor_index={ocr_processor.monitor_index} "
              f"interval={ocr_processor.check_interval}s")
    else:
        print("⚠️  OCR disabled — ENABLE_OCR is not true")

    asyncio.create_task(audio_collector())
    print("🎤 Microphone started")

    yield

    if stream:
        stream.stop()
        stream.close()
    if ocr_processor:
        ocr_processor.stop_background()
        ocr_processor = None

app = FastAPI(lifespan=lifespan)
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

def is_speech(audio: np.ndarray) -> bool:
    return np.sqrt(np.mean(audio**2)) > SILENCE_RMS_THRESHOLD

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    # PING/PONG + Client limiting
    await ws.accept()

    if len(clients) >= MAX_WS_CLIENTS:
        await ws.close(code=1008, reason="Too many clients")
        return
    
    clients.add(ws)
    print(f"🟢 Client {len(clients)} connected")
            
    try:
        # Ping every 30s to keep alive
        ping_task = asyncio.create_task(ping_client(ws))
        
        while True:
            if len(buffer) < CHUNK_SIZE:
                await asyncio.sleep(0.1)
                continue
                
            audio_np = np.fromiter(
                list(buffer)[0:CHUNK_SIZE],  # Safe slicing
                dtype=np.float32, 
                count=CHUNK_SIZE
            )
            
            if not is_speech(audio_np):
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
                result = await loop.run_in_executor(None, _transcribe)
            except Exception as transcribe_err:
                print(f"⚠️  Whisper error: {transcribe_err}")
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
            # print(f"📤 text='{text[:60]}' | "
            #       f"ocr_len={len(ocr_result['text'])} "
            #       f"ocr_keywords={ocr_result['keywords'][:3]}")
                            
            # Send to ALL clients
            disconnected: list[WebSocket] = []
            for client_ws in list(clients):
                try:
                    await client_ws.send_json(analysis)
                except Exception:
                    disconnected.append(client_ws)
                
            # Cleanup dead clients
            for dead in disconnected:
                clients.discard(dead)

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        clients.discard(ws)
        ping_task.cancel()
        print(f"🔴 Client disconnected. Active: {len(clients)}")

async def ping_client(ws: WebSocket):
    """Keep connection alive"""
    while True:
        try:
            await asyncio.sleep(25)
            await ws.ping()
        except:
            break

def run_server(host: str = "0.0.0.0", port: int = 8000):
    import uvicorn
    uvicorn.run(app, host=host, port=port)

if __name__ == "__main__":
    run_server()