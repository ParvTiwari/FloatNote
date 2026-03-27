"""
Standalone test for OCRProcessor — run this BEFORE integrating with server.py.

Usage:
    python test_ocr.py

What it tests:
    1. Single process() call — basic capture + OCR
    2. Change detection — two rapid calls (should throttle, return same result)
    3. Background thread + callback — verifies thread starts, fires callback,
       and stops cleanly
    4. process_async() — verifies the asyncio wrapper works
    5. Thread safety — 4 threads calling process() concurrently
"""

import asyncio
import threading
import time

# Adjust import path if needed
from ocr_processor import OCRProcessor


def test_single_call():
    print("\n--- Test 1: single process() call ---")
    proc = OCRProcessor(check_interval=0.5)
    result = proc.process()
    assert isinstance(result, dict), "result should be a dict"
    assert "text" in result, "result should have 'text' key"
    assert "keywords" in result, "result should have 'keywords' key"
    assert isinstance(result["keywords"], list), "keywords should be a list"
    print(f"  text preview : {repr(result['text'][:80])}")
    print(f"  keywords     : {result['keywords'][:5]}")
    print("  PASS")


def test_throttle():
    print("\n--- Test 2: throttle (rapid second call) ---")
    proc = OCRProcessor(check_interval=2.0)
    r1 = proc.process()
    r2 = proc.process()  # should be throttled → identical object returned
    assert r1 == r2, "Second call within interval should return cached result"
    print("  PASS — second call returned cached result as expected")


def test_background_callback():
    print("\n--- Test 3: background thread + callback ---")
    received = []
    proc = OCRProcessor(check_interval=0.5)

    def on_result(r):
        received.append(r)

    proc.start_background(callback=on_result)
    time.sleep(2.5)  # let it fire a few times
    proc.stop_background()

    assert len(received) >= 1, f"Expected >=1 callback, got {len(received)}"
    print(f"  Received {len(received)} callback(s)")
    print(f"  Last result text: {repr(received[-1]['text'][:60])}")
    print("  PASS")


def test_async_wrapper():
    print("\n--- Test 4: process_async() ---")
    proc = OCRProcessor(check_interval=0.5)

    async def run():
        return await proc.process_async()

    result = asyncio.run(run())
    assert "text" in result
    print(f"  async result text: {repr(result['text'][:60])}")
    print("  PASS")


def test_thread_safety():
    print("\n--- Test 5: thread safety (4 concurrent callers) ---")
    proc = OCRProcessor(check_interval=0.1)
    errors = []
    results = []

    def worker():
        try:
            for _ in range(5):
                r = proc.process()
                results.append(r)
                time.sleep(0.05)
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"Errors in threads: {errors}"
    assert all("text" in r for r in results), "All results should have 'text'"
    print(f"  {len(results)} results collected across 4 threads, 0 errors")
    print("  PASS")


if __name__ == "__main__":
    test_single_call()
    test_throttle()
    test_background_callback()
    test_async_wrapper()
    test_thread_safety()
    print("\n✅ All OCR tests passed — safe to integrate with server.py")