import asyncio
from fastapi import FastAPI, WebSocket
from contextlib import asynccontextmanager

from database import engine, Base, AsyncSessionLocal, Transcript, ActionItem


db_queue = asyncio.Queue()

async def database_worker():
    print("👷 Database Worker started! Sleeping until data arrives...")
    CURRENT_MEETING_ID = 1 
    
    while True:
        data = await db_queue.get()
        try:
            async with AsyncSessionLocal() as session:
                new_transcript = Transcript(
                    meeting_id=CURRENT_MEETING_ID, 
                    text=data["text"], 
                    keywords=",".join(data.get("keywords", []))
                )
                session.add(new_transcript)
                
                for action in data.get("actions", []):
                    new_action = ActionItem(meeting_id=CURRENT_MEETING_ID, description=action)
                    session.add(new_action)
                
                await session.commit()
                print(f"✅ 💾 SUCCESS! Worker woke up and saved to DB: '{data['text']}'")
                
        except Exception as e:
            print(f"❌ DB Error: {e}")
        finally:
            db_queue.task_done()


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all) 
    worker_task = asyncio.create_task(database_worker()) 
    yield
    worker_task.cancel()

app = FastAPI(lifespan=lifespan)

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    print("🟢 Client connected via WebSocket!")
    try:
        while True:
            data = await ws.receive_bytes()
            print("🎤 Received audio data! Processing...")
            
            fake_analysis = {
                "text": "Hello team, please schedule a meeting for tomorrow.",
                "keywords": ["meeting", "tomorrow", "schedule"],
                "actions": ["Schedule a meeting for tomorrow"]
            }
            
            await db_queue.put(fake_analysis)
            await ws.send_json(fake_analysis)
            
    except Exception as e:
        print("🔴 Client disconnected.")