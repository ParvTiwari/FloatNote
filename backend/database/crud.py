from sqlalchemy import select
from .models import AsyncSessionLocal, Meeting, Transcript, ActionItem, engine, Base
from ai_modules.utils.meeting_content import (
    clean_meeting_text,
    is_useful_audio_text,
    is_useful_ocr_text,
)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def create_meeting(session, title: str = "Live FloatNote Meeting"):
    meeting = Meeting(title=title)
    session.add(meeting)
    await session.commit()
    await session.refresh(meeting)
    return meeting

async def create_new_meeting(title: str = "Live FloatNote Meeting") -> Meeting:
    async with AsyncSessionLocal() as session:
        return await create_meeting(session, title=title)

async def get_meeting_by_id(meeting_id: int) -> Meeting | None:
    async with AsyncSessionLocal() as session:
        return await session.get(Meeting, meeting_id)

async def get_latest_meeting() -> Meeting | None:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Meeting).order_by(Meeting.id.desc()).limit(1)
        )
        return result.scalars().first()

async def get_current_meeting_id(session):
    result = await session.execute(select(Meeting).order_by(Meeting.id.desc()).limit(1))
    meeting = result.scalars().first()
    if not meeting:
        meeting = await create_meeting(session)
    return meeting.id

def _split_keywords(raw_keywords: str | None) -> list[str]:
    if not raw_keywords:
        return []
    return [keyword.strip() for keyword in raw_keywords.split(",") if keyword.strip()]


def _filter_keywords_for_item(keywords: list[str], cleaned_text: str, source: str) -> list[str]:
    if source != "ocr":
        return keywords

    lowered_text = cleaned_text.lower()
    filtered = []
    for keyword in keywords:
        normalized = keyword.strip()
        if normalized and normalized.lower() in lowered_text:
            filtered.append(normalized)
    return filtered

async def get_meeting_data(meeting_id: int) -> dict | None:
    async with AsyncSessionLocal() as session:
        meeting = await session.get(Meeting, meeting_id)
        if meeting is None:
            return None

        transcript_result = await session.execute(
            select(Transcript)
            .where(Transcript.meeting_id == meeting_id)
            .order_by(Transcript.timestamp.asc(), Transcript.id.asc())
        )
        transcripts = transcript_result.scalars().all()

        action_result = await session.execute(
            select(ActionItem)
            .where(ActionItem.meeting_id == meeting_id)
            .order_by(ActionItem.id.asc())
        )
        action_items = action_result.scalars().all()

        normalized_items: list[dict] = []
        normalized_actions: list[str] = []

        for transcript in transcripts:
            source = transcript.source or "unknown"
            normalized_source = "ocr" if source.upper() == "OCR" else "audio"
            cleaned_text = clean_meeting_text(transcript.text or "", normalized_source)

            if normalized_source == "ocr" and not is_useful_ocr_text(transcript.text or ""):
                continue
            if normalized_source == "audio" and not is_useful_audio_text(transcript.text or ""):
                continue
            if not cleaned_text:
                continue

            normalized_items.append(
                {
                    "source": normalized_source,
                    "speaker": None if source.upper() == "OCR" else source,
                    "text": cleaned_text,
                    "keywords": _filter_keywords_for_item(
                        _split_keywords(transcript.keywords),
                        cleaned_text,
                        normalized_source,
                    ),
                    "actions": [],
                }
            )

        for action in action_items:
            if action.description:
                normalized_actions.append(action.description)

        if normalized_actions and normalized_items:
            normalized_items[0]["actions"] = normalized_actions

        return {
            "meeting_id": meeting.id,
            "title": meeting.title,
            "summary": meeting.summary,
            "items": normalized_items,
        }

async def get_latest_meeting_data() -> dict | None:
    meeting = await get_latest_meeting()
    if meeting is None:
        return None
    return await get_meeting_data(meeting.id)

async def save_meeting_summary(meeting_id: int, summary: str) -> bool:
    async with AsyncSessionLocal() as session:
        meeting = await session.get(Meeting, meeting_id)
        if meeting is None:
            return False
        meeting.summary = summary
        await session.commit()
        return True

async def save_to_database(data: dict, meeting_id: int | None = None):
    async with AsyncSessionLocal() as session:
        try:
            if meeting_id is None:
                meeting_id = await get_current_meeting_id(session)

            # --- 1. AUDIO TRANSCRIPT SAVE ---
            # `source` distinguishes the local mic ("MIC") from system/loopback
            # audio of remote participants ("SPEAKER"). Defaults to MIC.
            speaker_label = data.get("source") or "MIC"
            if data.get("text"):
                # Speaker nikaalo (Agar PyAnnote ne bheja hai)
                if data.get("speakers") and len(data["speakers"]) > 0:
                    speaker_label = data["speakers"][0].get("speaker") or speaker_label
                
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

        except Exception as e:
            await session.rollback()
            print(f"❌ [DB ERROR]: {e}")
