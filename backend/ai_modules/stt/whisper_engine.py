import asyncio
import numpy as np
import sounddevice as sd
import whisper
from collections import deque
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

SAMPLE_RATE = 16000
CHUNK_SECONDS = 3
CHUNK_SIZE = SAMPLE_RATE * CHUNK_SECONDS
BUFFER_SECONDS = 10
SILENCE_RMS_THRESHOLD = 0.01

app = FastAPI()
model = whisper.load_model("base") 

queue = asyncio.Queue()
buffer = deque(maxlen=SAMPLE_RATE * BUFFER_SECONDS)
loop = None
stream = None

def audio_callback(indata, frames, time, status):
    if status:
        print(f"⚠️ Audio status: {status}")
        return
    if loop is None: return

    audio = indata[:, 0].copy()
    loop.call_soon_threadsafe(queue.put_nowait, audio)

async def audio_collector():
    while True:
        samples = await queue.get()
        buffer.extend(samples)

def is_speech(audio: np.ndarray) -> bool:
    return np.sqrt(np.mean(audio**2)) > SILENCE_RMS_THRESHOLD

@app.on_event("startup")
async def start_mic():
    global loop, stream
    loop = asyncio.get_running_loop()
    stream = sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="float32",
        blocksize=406,
        callback=audio_callback
    )
    stream.start()
    asyncio.create_task(audio_collector())

@app.on_event("shutdown")
async def cleanup():
    if stream:
        stream.stop()
        stream.close()

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    print("🟢 NLP Client Connected")

    try:
        while True:
            if len(buffer) < CHUNK_SIZE:
                await asyncio.sleep(0.05)
                continue

            audio_np = np.fromiter((buffer.popleft() for _ in range(CHUNK_SIZE)), dtype=np.float32, count=CHUNK_SIZE)

            if not is_speech(audio_np):
                continue

            result = await loop.run_in_executor(
                None,
                lambda: model.transcribe(
                    audio_np,
                    fp16=False,
                    language="en", # Hardcoding saves 100-200ms of detection time
                    temperature=0
                )
            )

            text = result.get("text", "").strip()
            
            if len(text) > 2:
                # Send clean text to your NLP client
                await ws.send_text(text)

    except WebSocketDisconnect:
        print("🔴 Client disconnected")
    except Exception as e:
        print(f"❌ Error: {e}")