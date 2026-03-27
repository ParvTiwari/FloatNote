import asyncio
import os
import tempfile
from collections import deque
from contextlib import asynccontextmanager

import numpy as np
import sounddevice as sd
import soundfile as sf
import torch
import whisper
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pyannote.audio import Pipeline
from scipy.signal import resample_poly
from speechbrain.inference import interfaces as sb_interfaces
from speechbrain.utils import fetching as sb_fetching
from speechbrain.utils import parameter_transfer as sb_parameter_transfer

from nlp_processor import process_text

try:
    import pyaudiowpatch as pyaudio
except ImportError:
    pyaudio = None

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
MODEL_SAMPLE_RATE = 16000
CHUNK_SECONDS = 5
BUFFER_SECONDS = 10
SILENCE_RMS_THRESHOLD = 0.015
MAX_WS_CLIENTS = 3

HF_TOKEN = os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACE_TOKEN") or "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"

# ---------------- MODELS ----------------
model = whisper.load_model("base")

pipeline = Pipeline.from_pretrained(
    "pyannote/speaker-diarization",
    use_auth_token=HF_TOKEN,
)

# ---------------- GLOBALS ----------------
queue = asyncio.Queue(maxsize=100)
buffer = deque(maxlen=MODEL_SAMPLE_RATE * BUFFER_SECONDS)
loop = None
stream = None
clients = set()
stream_sample_rate = MODEL_SAMPLE_RATE
capture_details = "uninitialized"
chunk_size = MODEL_SAMPLE_RATE * CHUNK_SECONDS
capture_warnings = []
capture_backend = "sounddevice"
pyaudio_instance = None


# ---------------- LOOPBACK ----------------
def _env_device_index():
    raw_value = os.getenv("FLOATNOTE_AUDIO_DEVICE")
    if raw_value is None or not raw_value.strip():
        return None

    return int(raw_value)


def _capture_from_device(device_index, *, use_wasapi_loopback=False, reason=""):
    devices = sd.query_devices()
    device = devices[device_index]
    channels_key = "max_output_channels" if use_wasapi_loopback else "max_input_channels"
    channels = max(1, min(2, int(device[channels_key])))
    extra_settings = None
    if use_wasapi_loopback:
        try:
            extra_settings = sd.WasapiSettings(loopback=True)
        except TypeError:
            extra_settings = None
            reason = f"{reason}; loopback unsupported by installed sounddevice"
    mode = "WASAPI loopback" if use_wasapi_loopback else "input capture"

    return {
        "device": device_index,
        "samplerate": int(device["default_samplerate"]),
        "channels": channels,
        "extra_settings": extra_settings,
        "details": f"{mode} on device {device_index}: {device['name']} ({reason})",
    }


def _iter_capture_candidates():
    devices = sd.query_devices()
    seen = set()

    env_device = _env_device_index()
    if env_device is not None:
        use_wasapi_loopback = devices[env_device]["max_input_channels"] == 0 and devices[env_device]["hostapi"] == 2
        reason = "FLOATNOTE_AUDIO_DEVICE override"
        if use_wasapi_loopback:
            seen.add(env_device)
            yield _capture_from_device(env_device, use_wasapi_loopback=True, reason=reason)
        else:
            seen.add(env_device)
            yield _capture_from_device(env_device, reason=reason)

    for i, dev in enumerate(devices):
        if i in seen:
            continue
        name = dev["name"].lower()
        if (
            "loopback" in name
            or "stereo mix" in name
            or "cable output" in name
            or "vb-audio" in name
        ):
            seen.add(i)
            yield _capture_from_device(i, reason="matched loopback-style device name")

    hostapis = sd.query_hostapis()
    for hostapi in hostapis:
        if hostapi["name"] == "Windows WASAPI":
            default_output = hostapi["default_output_device"]
            if default_output is not None and default_output >= 0 and default_output not in seen:
                seen.add(default_output)
                yield _capture_from_device(
                    default_output,
                    use_wasapi_loopback=True,
                    reason="fallback to default WASAPI output device",
                )

    for i, dev in enumerate(devices):
        if i in seen:
            continue
        if int(dev["max_input_channels"]) > 0 and int(dev["hostapi"]) != 3:
            seen.add(i)
            yield _capture_from_device(i, reason="fallback to regular input device")


def open_best_input_stream():
    errors = []
    for capture_config in _iter_capture_candidates():
        try:
            stream = sd.InputStream(
                samplerate=capture_config["samplerate"],
                channels=capture_config["channels"],
                dtype="float32",
                blocksize=512,
                device=capture_config["device"],
                extra_settings=capture_config["extra_settings"],
                callback=audio_callback,
            )
            capture_config["backend"] = "sounddevice"
            return stream, capture_config, errors
        except Exception as exc:
            errors.append(f"{capture_config['details']} -> {exc}")

    return None, None, errors


def resample_audio(audio, original_sample_rate, target_sample_rate):
    if original_sample_rate == target_sample_rate:
        return audio.astype(np.float32, copy=False)

    gcd = np.gcd(original_sample_rate, target_sample_rate)
    up = target_sample_rate // gcd
    down = original_sample_rate // gcd
    return resample_poly(audio, up, down).astype(np.float32, copy=False)


def pyaudio_audio_callback(in_data, frame_count, time_info, status):
    if status:
        print(f"PyAudio callback status: {status}")
    if loop is None:
        return (None, pyaudio.paContinue)

    audio = np.frombuffer(in_data, dtype=np.float32)
    if audio.size == 0:
        return (None, pyaudio.paContinue)

    channels = 2 if audio.size % 2 == 0 else 1
    if channels > 1:
        audio = audio.reshape(-1, channels).mean(axis=1, dtype=np.float32)

    if not queue.full():
        loop.call_soon_threadsafe(queue.put_nowait, audio.copy())

    return (None, pyaudio.paContinue)


def open_pyaudio_loopback_stream():
    global pyaudio_instance

    if pyaudio is None:
        return None, None, ["PyAudioWPatch is not installed."]

    errors = []
    try:
        pyaudio_instance = pyaudio.PyAudio()
        device = pyaudio_instance.get_default_wasapi_loopback()
        sample_rate = int(device["defaultSampleRate"])
        channels = max(1, min(2, int(device["maxInputChannels"])))
        stream = pyaudio_instance.open(
            format=pyaudio.paFloat32,
            channels=channels,
            rate=sample_rate,
            input=True,
            input_device_index=device["index"],
            frames_per_buffer=512,
            stream_callback=pyaudio_audio_callback,
            start=False,
        )
        capture_config = {
            "device": device["index"],
            "samplerate": sample_rate,
            "channels": channels,
            "extra_settings": None,
            "details": f"PyAudio WASAPI loopback on device {device['index']}: {device['name']}",
            "backend": "pyaudio",
        }
        return stream, capture_config, errors
    except Exception as exc:
        errors.append(f"PyAudio WASAPI loopback failed -> {exc}")
        if pyaudio_instance is not None:
            pyaudio_instance.terminate()
            pyaudio_instance = None
        return None, None, errors


def open_preferred_input_stream():
    errors = []

    pyaudio_stream, pyaudio_config, pyaudio_errors = open_pyaudio_loopback_stream()
    errors.extend(pyaudio_errors)
    if pyaudio_stream is not None and pyaudio_config is not None:
        return pyaudio_stream, pyaudio_config, errors

    stream, capture_config, sd_errors = open_best_input_stream()
    errors.extend(sd_errors)
    return stream, capture_config, errors


# ---------------- AUDIO CALLBACK ----------------
def audio_callback(indata, frames, time, status):
    if status:
        print(f"Audio callback status: {status}")
        return
    if loop is None:
        return

    audio = np.mean(indata, axis=1, dtype=np.float32).copy()
    if not queue.full():
        loop.call_soon_threadsafe(queue.put_nowait, audio)


# ---------------- AUDIO COLLECTOR ----------------
async def audio_collector():
    while True:
        try:
            samples = await asyncio.wait_for(queue.get(), timeout=1.0)
            samples = resample_audio(samples, stream_sample_rate, MODEL_SAMPLE_RATE)
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
    global loop, stream, stream_sample_rate, capture_details, capture_warnings, capture_backend

    loop = asyncio.get_running_loop()

    stream, capture_config, capture_warnings = open_preferred_input_stream()
    if capture_config is None or stream is None:
        details = "\n".join(capture_warnings) if capture_warnings else "No candidates were generated."
        raise RuntimeError(
            "No audio capture device could be opened.\n"
            f"{details}"
        )

    stream_sample_rate = capture_config["samplerate"]
    capture_details = capture_config["details"]
    capture_backend = capture_config.get("backend", "sounddevice")

    if capture_backend == "pyaudio":
        stream.start_stream()
    else:
        stream.start()
    asyncio.create_task(audio_collector())

    print("System audio capture started")
    print(f"Capture source: {capture_details}")
    print(f"Capture backend: {capture_backend}")
    print(f"Stream sample rate: {stream_sample_rate} Hz -> model sample rate: {MODEL_SAMPLE_RATE} Hz")
    if capture_warnings:
        print("Capture fallbacks tried before success:")
        for warning in capture_warnings:
            print(f"  - {warning}")
    yield

    if capture_backend == "pyaudio":
        stream.stop_stream()
        stream.close()
        if pyaudio_instance is not None:
            pyaudio_instance.terminate()
    else:
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
            if len(buffer) < chunk_size:
                await asyncio.sleep(0.1)
                continue

            audio_np = np.array(list(buffer)[:chunk_size], dtype=np.float32)

            if not is_speech(audio_np):
                buffer.clear()
                continue

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                sf.write(f.name, audio_np, MODEL_SAMPLE_RATE)
                temp_path = f.name

            transcription_future = loop.run_in_executor(
                None,
                lambda: model.transcribe(audio_np, fp16=False),
            )

            diarization_future = loop.run_in_executor(
                None,
                lambda: pipeline(temp_path),
            )

            result = await transcription_future
            diarization = await diarization_future

            text = result.get("text", "").strip()
            buffer.clear()

            if len(text) > 2:
                speakers = []
                for turn, _, speaker in diarization.itertracks(yield_label=True):
                    speakers.append(
                        {
                            "start": round(turn.start, 2),
                            "end": round(turn.end, 2),
                            "speaker": speaker,
                        }
                    )

                all_actions = []
                for seg in speakers:
                    processed = process_text(text, speaker=seg["speaker"])
                    all_actions.extend(processed["actions"])

                response = {
                    "text": text,
                    "speakers": speakers,
                    "actions": all_actions,
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
