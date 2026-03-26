import asyncio
import numpy as np
import sounddevice as sd
import whisper
import tempfile
import soundfile as sf
import torch
from speechbrain.utils import fetching as sb_fetching
from speechbrain.utils import parameter_transfer as sb_parameter_transfer
from speechbrain.inference import interfaces as sb_interfaces

from collections import deque
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from contextlib import asynccontextmanager

from pyannote.audio import Pipeline
from nlp_processor import process_text  

# pyannote 3.1 expects the older torch.load default for trusted HF checkpoints.
_original_torch_load = torch.load

def _compat_torch_load(*args, **kwargs):
    kwargs["weights_only"] = False
    return _original_torch_load(*args, **kwargs)

torch.load = _compat_torch_load

_original_sb_fetch = sb_fetching.fetch
_original_sb_link = sb_fetching.link_with_strategy

def _compat_sb_fetch(*args, **kwargs):
    if kwargs.get("local_strategy") in (None, sb_fetching.LocalStrategy.SYMLINK):
        kwargs["local_strategy"] = sb_fetching.LocalStrategy.COPY
    return _original_sb_fetch(*args, **kwargs)

def _compat_sb_link(src, dst, local_strategy):
    if local_strategy == sb_fetching.LocalStrategy.SYMLINK:
        local_strategy = sb_fetching.LocalStrategy.COPY
    return _original_sb_link(src, dst, local_strategy)

sb_fetching.fetch = _compat_sb_fetch
sb_fetching.link_with_strategy = _compat_sb_link
sb_interfaces.fetch = _compat_sb_fetch
sb_parameter_transfer.fetch = _compat_sb_fetch

# ---------------- CONFIG ----------------
SAMPLE_RATE = 16000
CHUNK_SECONDS = 5
CHUNK_SIZE = SAMPLE_RATE * CHUNK_SECONDS
BUFFER_SECONDS = 10
SILENCE_RMS_THRESHOLD = 0.015
MAX_WS_CLIENTS = 3

HF_TOKEN = "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"

# ---------------- MODELS ----------------
model = whisper.load_model("base")

pipeline = Pipeline.from_pretrained(
    "pyannote/speaker-diarization",
    use_auth_token=HF_TOKEN
)

# ---------------- GLOBALS ----------------
queue = asyncio.Queue(maxsize=100)
buffer = deque(maxlen=SAMPLE_RATE * BUFFER_SECONDS)
loop = None
stream = None
clients = set()

# ---------------- LOOPBACK ----------------
def get_loopback_device():
    devices = sd.query_devices()
    for i, dev in enumerate(devices):
        name = dev["name"].lower()
        if (
            "loopback" in name
            or "stereo mix" in name
            or "cable output" in name
            or "vb-audio" in name
        ):
            return i
    return None

# ---------------- AUDIO CALLBACK ----------------
def audio_callback(indata, frames, time, status):
    if status:
        print(f"⚠️ {status}")
        return
    if loop is None:
        return
    audio = indata[:, 0].copy()
    if not queue.full():
        loop.call_soon_threadsafe(queue.put_nowait, audio)

# ---------------- AUDIO COLLECTOR ----------------
async def audio_collector():
    while True:
        try:
            samples = await asyncio.wait_for(queue.get(), timeout=1.0)
            buffer.extend(samples)
            queue.task_done()
        except asyncio.TimeoutError:
            continue

# ---------------- SPEECH DETECTION ----------------
def is_speech(audio):
    return np.sqrt(np.mean(audio**2)) > SILENCE_RMS_THRESHOLD

# ---------------- LIFESPAN ----------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    global loop, stream

    loop = asyncio.get_running_loop()

    device = get_loopback_device()
    if device is None:
        raise RuntimeError("Enable Stereo Mix or install VB-Cable")

    stream = sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="float32",
        blocksize=512,
        device=device,
        callback=audio_callback
    )

    stream.start()
    asyncio.create_task(audio_collector())

    print("System audio capture started")
    yield

    stream.stop()
    stream.close()

# ---------------- FASTAPI ----------------
app = FastAPI(lifespan=lifespan)

# ---------------- WEBSOCKET ----------------
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    client_id = id(ws)
    clients.add(client_id)

    if len(clients) > MAX_WS_CLIENTS:
        await ws.close()
        return

    try:
        while True:
            if len(buffer) < CHUNK_SIZE:
                await asyncio.sleep(0.1)
                continue

            audio_np = np.array(list(buffer)[:CHUNK_SIZE], dtype=np.float32)

            if not is_speech(audio_np):
                buffer.clear()
                continue

            # ---- save temp audio ----
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                sf.write(f.name, audio_np, SAMPLE_RATE)
                temp_path = f.name

            # ---- run models ----
            transcription_future = loop.run_in_executor(
                None,
                lambda: model.transcribe(audio_np, fp16=False)
            )

            diarization_future = loop.run_in_executor(
                None,
                lambda: pipeline(temp_path)
            )

            result = await transcription_future
            diarization = await diarization_future

            text = result.get("text", "").strip()
            buffer.clear()

            if len(text) > 2:
                speakers = []
                for turn, _, speaker in diarization.itertracks(yield_label=True):
                    speakers.append({
                        "start": round(turn.start, 2),
                        "end": round(turn.end, 2),
                        "speaker": speaker
                    })

                # ---- ACTION EXTRACTION ----
                all_actions = []
                for seg in speakers:
                    processed = process_text(text, speaker=seg["speaker"])
                    all_actions.extend(processed["actions"])

                response = {
                    "text": text,
                    "speakers": speakers,
                    "actions": all_actions
                }

                print(response)
                await ws.send_json(response)

    except WebSocketDisconnect:
        pass
    finally:
        clients.discard(client_id)

# ---------------- RUN ----------------
def run():
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

if __name__ == "__main__":
    run()
