from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from backend.ai_modules.stt.whisper_engine import transcribe_stream
from backend.ai_modules.nlp.nlp_pipeline import process_text

router = APIRouter()   


@router.websocket("/ws/stt")
async def stt_ws(ws: WebSocket):
    await ws.accept()

    try:
        async for text in transcribe_stream():
            nlp_result = process_text(text)
            await ws.send_json(nlp_result)

    except WebSocketDisconnect:
        print("Client disconnected")

    except Exception as e:
        print("Error:", e)
