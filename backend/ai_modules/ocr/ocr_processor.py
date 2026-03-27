from __future__ import annotations

import asyncio
import threading
import time
from typing import Callable, Dict, List, Optional, Tuple

import cv2
import mss
import numpy as np
import spacy

import pytesseract
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

class OCRProcessor:
    """Capture screen frames and run OCR only when slide content changes."""

    def __init__(
        self,
        change_threshold: float = 0.02,
        check_interval: float = 1.0,
        compare_size: Tuple[int, int] = (300, 200),
        min_text_length: int = 5,
        blur_kernel: Optional[Tuple[int, int]] = (5, 5),
        crop_region: Optional[Dict[str, int]] = None,
        monitor_index: int = 1,
        tesseract_config: str = "--oem 3 --psm 6",
        apply_threshold: bool = True,
        nlp_model: str = "en_core_web_sm",
    ) -> None:
        self.change_threshold = change_threshold
        self.check_interval = check_interval
        self.compare_size = compare_size
        self.min_text_length = min_text_length
        self.blur_kernel = blur_kernel
        self.crop_region = crop_region
        self.monitor_index = monitor_index
        self.tesseract_config = tesseract_config
        self.apply_threshold = apply_threshold

        self._prev_frame: Optional[np.ndarray] = None
        self._last_check = 0.0

        self._lock = threading.Lock()
        self._running = False
        self._worker: Optional[threading.Thread] = None
        self._latest_result: Dict[str, List[str] | str] = {"text": "", "keywords": []}
        self._last_emitted_result: Dict[str, List[str] | str] = {"text": "", "keywords": []}

        if self.crop_region is not None:
            required_keys = {"top", "left", "width", "height"}
            missing_keys = required_keys.difference(self.crop_region.keys())
            if missing_keys:
                missing = ", ".join(sorted(missing_keys))
                raise ValueError(f"crop_region is missing required keys: {missing}")

        try:
            self._nlp = spacy.load(nlp_model)
        except OSError:
            # Fallback keeps processor usable even if model is not installed.
            self._nlp = spacy.blank("en")

    def capture_screen(self) -> np.ndarray:
        """Capture the full screen (or configured crop) as a BGR numpy array."""
        with mss.mss() as sct:
            monitor = self.crop_region or sct.monitors[self.monitor_index]
            screenshot = sct.grab(monitor)
            frame = np.array(screenshot)
        return cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)

    def has_slide_changed(self, prev: np.ndarray, curr: np.ndarray) -> bool:
        """Return True when frame delta exceeds the configured threshold."""
        prev_small = cv2.resize(prev, self.compare_size, interpolation=cv2.INTER_AREA)
        curr_small = cv2.resize(curr, self.compare_size, interpolation=cv2.INTER_AREA)

        prev_gray = cv2.cvtColor(prev_small, cv2.COLOR_BGR2GRAY)
        curr_gray = cv2.cvtColor(curr_small, cv2.COLOR_BGR2GRAY)

        if self.blur_kernel:
            prev_gray = cv2.GaussianBlur(prev_gray, self.blur_kernel, 0)
            curr_gray = cv2.GaussianBlur(curr_gray, self.blur_kernel, 0)

        diff = cv2.absdiff(prev_gray, curr_gray)
        changed_pixels = np.count_nonzero(diff > 25)
        total_pixels = diff.size
        change_ratio = changed_pixels / float(total_pixels)
        return change_ratio > self.change_threshold

    def extract_text(self, frame: np.ndarray) -> str:
        """Run OCR on a frame and return cleaned text lines."""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        if self.apply_threshold:
            gray = cv2.threshold(
                gray,
                0,
                255,
                cv2.THRESH_BINARY + cv2.THRESH_OTSU,
            )[1]

        raw_text = pytesseract.image_to_string(gray, config=self.tesseract_config)
        lines = [line.strip() for line in raw_text.splitlines()]
        cleaned = [line for line in lines if len(line) >= self.min_text_length]
        return "\n".join(cleaned)

    def _extract_keywords(self, text: str) -> List[str]:
        if not text.strip():
            return []

        doc = self._nlp(text)
        keywords: List[str] = []
        seen = set()

        for token in doc:
            if token.pos_ in {"NOUN", "PROPN"}:
                normalized = token.lemma_.strip().lower()
                if normalized and normalized not in seen:
                    seen.add(normalized)
                    keywords.append(token.text)

        return keywords

    def process(self) -> Dict[str, List[str] | str]:
        """Capture screen, detect changes, and OCR only on changed content."""
        now = time.monotonic()
        with self._lock:
            if now - self._last_check < self.check_interval:
                return dict(self._latest_result)
            self._last_check = now

        current_frame = self.capture_screen()

        with self._lock:
            prev_frame = self._prev_frame
        
        if prev_frame is None:
            text = self.extract_text(current_frame)
            result: Dict[str, List[str] | str] = {
                "text": text,
                "keywords": self._extract_keywords(text),
            }
            with self._lock:
                self._prev_frame = current_frame
                self._latest_result = result
            return dict(result)
 
        if self.has_slide_changed(prev_frame, current_frame):
            text = self.extract_text(current_frame)
            result = {"text": text, "keywords": self._extract_keywords(text)}
            with self._lock:
                self._prev_frame = current_frame
                self._latest_result = result

        with self._lock:
            return dict(self._latest_result)

    async def process_async(self) -> Dict[str, List[str] | str]:
        """Async-safe wrapper for event loops (e.g., FastAPI WebSocket handlers)."""
        return await asyncio.to_thread(self.process)

    def start_background(self, callback: Optional[Callable[[Dict[str, List[str] | str]], None]] = None) -> None:
        """Start a non-blocking processing loop in a daemon thread."""
        if self._running:
            return

        self._running = True

        def _loop() -> None:
            while self._running:
                result = self.process()
                if callback is not None:
                    with self._lock:
                        changed = result != self._last_emitted_result
                        if changed:
                            self._last_emitted_result = dict(result)
                    if changed:
                        callback(result)
                time.sleep(max(0.05, self.check_interval / 2))

        self._worker = threading.Thread(target=_loop, daemon=True)
        self._worker.start()

    def stop_background(self) -> None:
        """Stop the background processing thread."""
        self._running = False
        if self._worker and self._worker.is_alive():
            self._worker.join(timeout=self.check_interval * 2)
        self._worker = None

    @property
    def latest_result(self) -> Dict[str, List[str] | str]:
        with self._lock:
            return dict(self._latest_result)