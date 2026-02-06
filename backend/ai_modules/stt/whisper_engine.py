import asyncio
import numpy as np
import sounddevice as sd
import whisper
from collections import deque

SAMPLE_RATE = 16000
BUFFER_SECONDS = 4
CHUNK_SECONDS = 2

queue = asyncio.Queue()
buffer = deque(maxlen=SAMPLE_RATE * BUFFER_SECONDS)
loop = None
stream = None

model = whisper.load_model("base")

def audio_callback(indata, frames, time, status):
    if loop is None:
        return
    audio = indata[:, 0].copy()
    loop.call_soon_threadsafe(queue.put_nowait, audio)

async def audio_collector():
    while True:
        samples = await queue.get()
        buffer.extend(samples)

async def start_microphone():
    global loop, stream
    loop = asyncio.get_running_loop()

    stream = sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=1,
        callback=audio_callback
    )
    stream.start()

    asyncio.create_task(audio_collector())

async def transcribe_stream():
    await start_microphone()

    while True:
        await asyncio.sleep(0.4)

        if len(buffer) < SAMPLE_RATE * CHUNK_SECONDS:
            continue

        audio = np.array(
            [buffer.popleft() for _ in range(SAMPLE_RATE * CHUNK_SECONDS)],
            dtype=np.float32
        )

        result = await loop.run_in_executor(
            None, lambda: model.transcribe(audio, fp16=False)
        )

        text = result["text"].strip()
        if text:
            yield text