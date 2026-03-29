from sqlalchemy import select
from .models import AsyncSessionLocal, Meeting, Transcript, ActionItem, engine, Base

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def get_current_meeting_id(session):
    result = await session.execute(select(Meeting).order_by(Meeting.id.desc()).limit(1))
    meeting = result.scalars().first()
    if not meeting:
        meeting = Meeting(title="Live FloatNote Meeting")
        session.add(meeting)
        await session.commit()
        await session.refresh(meeting)
    return meeting.id

async def save_to_database(data: dict):
    async with AsyncSessionLocal() as session:
        try:
            meeting_id = await get_current_meeting_id(session)

            # --- 1. AUDIO TRANSCRIPT SAVE ---
            speaker_label = "unknown"
            if data.get("text"):
                # Speaker nikaalo (Agar PyAnnote ne bheja hai)
                if data.get("speakers") and len(data["speakers"]) > 0:
                    speaker_label = data["speakers"][0].get("speaker", "unknown")
                
                keywords_list = data.get("keywords", [])
                audio_keywords = ",".join(keywords_list) if isinstance(keywords_list, list) else ""

                new_transcript = Transcript(
                    meeting_id=meeting_id,
                    text=data.get("text", ""),
                    keywords=audio_keywords,
                    source=speaker_label  # Yahan SPEAKER_00 ya unknown aayega
                )
                session.add(new_transcript)

            # --- 2. OCR DATA SAVE ---
            ocr_data = data.get("ocr", {})
            if ocr_data and ocr_data.get("text"):
                ocr_keywords = ",".join(ocr_data.get("keywords", []))
                ocr_txn = Transcript(
                    meeting_id=meeting_id,
                    text=ocr_data["text"],
                    keywords=ocr_keywords,
                    source="OCR"  # Screen data ko alag mark kar diya
                )
                session.add(ocr_txn)

            # --- 3. ACTION ITEMS SAVE ---
            # NLP file 'actions' bhej sakti hai ya 'action_items', dono handle kar lete hain
            actions_list = data.get("actions", []) or data.get("action_items", [])
            for action in actions_list:
                # Agar NLP directly dict bhej raha hai:
                if isinstance(action, dict):
                    task_desc = action.get("task", "Unknown Task")
                    task_assignee = action.get("assignee", speaker_label)
                # Agar NLP purane format mein string bhej raha hai:
                else:
                    task_desc = str(action)
                    task_assignee = speaker_label

                new_action = ActionItem(
                    meeting_id=meeting_id,
                    description=task_desc,
                    assignee=task_assignee,
                    status="pending"
                )
                session.add(new_action)

            await session.commit()
            print(f"✅ 💾 SAVED TO DB: [{speaker_label}] {data.get('text', '')[:30]}...")

        except Exception as e:
            await session.rollback()
            print(f"❌ [DB ERROR]: {e}")