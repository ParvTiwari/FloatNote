from fastapi import FastAPI
from backend.api.routes.audio import router as audio_router

app = FastAPI(title="FloatNote Backend")

app.include_router(audio_router)