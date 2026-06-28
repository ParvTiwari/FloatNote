"""Lightweight online (streaming) speaker diarization.

Runs fully offline: Resemblyzer produces a 256-dim d-vector embedding for each
speech segment (model weights ship with the package), and we cluster those
embeddings incrementally with cosine similarity against the speakers seen so far
*in this meeting*. "Online" here means real-time/incremental — not networked.

This gives consistent ``SPEAKER_00 / SPEAKER_01 / ...`` labels across a live
meeting without needing the whole recording up front (unlike file-based
diarizers such as pyannote).
"""

import os
import threading

import numpy as np

try:
    from resemblyzer import VoiceEncoder
except Exception:  # pragma: no cover - optional dependency
    VoiceEncoder = None

ENABLE_DIARIZATION = os.getenv("ENABLE_DIARIZATION", "true").strip().lower() == "true"
# Cosine similarity above which a new utterance is treated as an existing speaker.
SIMILARITY_THRESHOLD = float(os.getenv("DIARIZATION_SIMILARITY", "0.70"))
# Resemblyzer needs ~1s of audio for a stable embedding.
MIN_SAMPLES = int(os.getenv("DIARIZATION_MIN_SAMPLES", "16000"))

_encoder = None
_encoder_lock = threading.Lock()
# meeting_id -> list of {"label": str, "centroid": np.ndarray, "count": int}
_meetings: dict[int, list[dict]] = {}
_state_lock = threading.Lock()


def _get_encoder():
    global _encoder
    if _encoder is None:
        with _encoder_lock:
            if _encoder is None:
                _encoder = VoiceEncoder("cpu", verbose=False)
    return _encoder


def reset_meeting(meeting_id: int) -> None:
    """Drop accumulated speaker centroids for a finished meeting."""
    with _state_lock:
        _meetings.pop(meeting_id, None)


def assign_speaker(audio_16k, meeting_id: int, base_label: str = "SPEAKER") -> str:
    """Return a stable speaker label for this utterance within the meeting.

    Falls back to ``base_label`` when diarization is disabled/unavailable or the
    audio is too short to embed reliably.
    """
    if not ENABLE_DIARIZATION or VoiceEncoder is None or meeting_id is None:
        return base_label

    audio = np.asarray(audio_16k, dtype=np.float32).flatten()
    if audio.size < MIN_SAMPLES:
        return base_label

    try:
        emb = _get_encoder().embed_utterance(audio)
    except Exception as exc:  # pragma: no cover - runtime/audio dependent
        print(f"⚠️ Diarization embed failed: {exc}")
        return base_label

    emb = emb / (np.linalg.norm(emb) + 1e-9)

    with _state_lock:
        speakers = _meetings.setdefault(meeting_id, [])
        best, best_sim = None, -1.0
        for sp in speakers:
            sim = float(np.dot(emb, sp["centroid"]))
            if sim > best_sim:
                best_sim, best = sim, sp

        if best is not None and best_sim >= SIMILARITY_THRESHOLD:
            n = best["count"]
            updated = (best["centroid"] * n + emb) / (n + 1)
            best["centroid"] = updated / (np.linalg.norm(updated) + 1e-9)
            best["count"] = n + 1
            return best["label"]

        label = f"{base_label}_{len(speakers):02d}"
        speakers.append({"label": label, "centroid": emb, "count": 1})
        return label
