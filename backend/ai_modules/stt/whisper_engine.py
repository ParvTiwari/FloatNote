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

SAMPLE_RATE = 16000
CHUNK_SECONDS = 3
CHUNK_SIZE = SAMPLE_RATE * CHUNK_SECONDS
BUFFER_SECONDS = 8
SILENCE_RMS_THRESHOLD = 0.0001  # Lowered from 0.015 to match actual mic levels
MAX_WS_CLIENTS = 3

# ---------------- LIFESPAN ----------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    global loop, stream
    loop = asyncio.get_running_loop()
    stream = sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="float32",
        blocksize=512,  # ↑ Fixed overflow
        callback=audio_callback
    )
    stream.start()
    asyncio.create_task(audio_collector())
    print("🎤 Microphone started")
    yield
    if stream:
        stream.stop()
        stream.close()

app = FastAPI(lifespan=lifespan)
model = whisper.load_model("base")
queue = asyncio.Queue(maxsize=100)
buffer = deque(maxlen=SAMPLE_RATE * BUFFER_SECONDS)
loop = None
stream = None
clients = {}  # Track active clients: {client_id: websocket}

def audio_callback(indata, frames, time, status):
    if status:
        print(f"⚠️ Audio status: {status}")
        return
    if loop is None: 
        return
    try:
        audio = indata[:, 0].copy()
        if not queue.full():  # Prevent overflow
            loop.call_soon_threadsafe(queue.put_nowait, audio)
    except:
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
    client_id = id(ws)
    clients[client_id] = ws
    print(f"🟢 Client {len(clients)} connected")
    
    if len(clients) > MAX_WS_CLIENTS:
        await ws.close(code=1008, reason="Too many clients")
        return
        
    try:
        # Ping every 30s to keep alive
        ping_task = asyncio.create_task(ping_client(ws))
        
        while True:
            if len(buffer) < CHUNK_SIZE:
                await asyncio.sleep(0.1)
                continue

            if len(buffer) < CHUNK_SIZE:
                continue
            
            print(f"📊 Buffer size: {len(buffer)}, CHUNK_SIZE: {CHUNK_SIZE}")
            audio_np = np.fromiter(
                list(buffer)[0:CHUNK_SIZE],  # Safe slicing
                dtype=np.float32, 
                count=CHUNK_SIZE
            )
            
            rms = np.sqrt(np.mean(audio_np**2))
            print(f"🔊 RMS: {rms:.6f}, Threshold: {SILENCE_RMS_THRESHOLD}")
            
            # Skip if not enough valid audio
            if len(audio_np) < CHUNK_SIZE * 0.8:
                print("❌ Not enough audio data")
                buffer.clear()
                continue
                
            if not is_speech(audio_np):
                print("❌ Silence detected, skipping")
                buffer.clear()
                continue
            
            print("✅ Speech detected! Transcribing...")
            result = await loop.run_in_executor(
                None,
                lambda: model.transcribe(
                    audio_np,
                    fp16=False,
                    language="en",
                    temperature=0
                )
            )

            text = result.get("text", "").strip()
            print(f"📝 Transcribed: '{text}'")
            buffer.clear()
            
            if len(text) > 2:
                print(f"✨ Sending to {len(clients)} clients: {text}")
                analysis = process_text(text)
                
                # Send to ALL clients
                disconnected = []
                for client_id, client_ws in list(clients.items()):
                    try:
                        await client_ws.send_json(analysis)
                        print(f"✅ Sent to client {client_id}")
                    except Exception as e:
                        print(f"❌ Failed to send to client {client_id}: {e}")
                        disconnected.append(client_id)
                
                # Cleanup dead clients
                for cid in disconnected:
                    clients.pop(cid, None)
            else:
                print(f"⏭️  Text too short ({len(text)} chars), skipping")

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        clients.pop(client_id, None)
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