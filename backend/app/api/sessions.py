"""Session CRUD — create a session, list a session's message history."""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.db_models import ChatSession
from app.models.schemas import CreateSessionRequest, SessionDetailResponse, SessionResponse

router = APIRouter(prefix="/api/sessions", tags=["Sessions"])


@router.post("", response_model=SessionResponse, status_code=201)
async def create_session(req: CreateSessionRequest, db: AsyncSession = Depends(get_db)) -> ChatSession:
    session = ChatSession(title=req.title or "New chat", llm_provider=req.llm_provider)
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


@router.get("", response_model=list[SessionResponse])
async def list_sessions(db: AsyncSession = Depends(get_db)) -> list[ChatSession]:
    result = await db.execute(select(ChatSession).order_by(ChatSession.updated_at.desc()).limit(50))
    return list(result.scalars().all())


@router.get("/{session_id}", response_model=SessionDetailResponse)
async def get_session(session_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> ChatSession:
    result = await db.execute(
        select(ChatSession).where(ChatSession.id == session_id).options(selectinload(ChatSession.messages))
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    return session


@router.delete("/{session_id}", status_code=204)
async def delete_session(session_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> None:
    result = await db.execute(select(ChatSession).where(ChatSession.id == session_id))
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    await db.delete(session)
    await db.commit()
