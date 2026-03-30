import os
import warnings

warnings.filterwarnings(
    "ignore",
    message="TypedStorage is deprecated"
)

from ai_modules.stt.whisper_engine import run_server


if __name__ == "__main__":
    print("🌐 Running Server...\n")
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    run_server(host=host, port=port)
