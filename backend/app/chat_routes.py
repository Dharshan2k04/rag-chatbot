from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import AsyncGenerator
import json
import asyncio

from .database import (
    get_db,
    create_chat,
    save_message,
    get_chat_messages,
    get_user_chats,
    get_user_chat_count,
    delete_chat,
    update_chat_title,
    record_document,
    update_document_chunks,
    get_user_document_ids,
)

from .rag import rag_answer
from .dependencies import get_current_user
from .models import User

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/new")
async def new_chat(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new chat session for the authenticated user"""
    chat = create_chat(db, current_user.id, title="New Chat")
    return {"chat_id": chat.id, "message": "New chat created"}


@router.post("/{chat_id}")
async def chat_message(
    chat_id: int,
    query: str,
    regenerate: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        if not regenerate:
            save_message(db, chat_id, current_user.id, "user", query)

        temperature = 0.9 if regenerate else 0.7
        doc_ids = get_user_document_ids(db, current_user.id)
        answer, sources = rag_answer(
            query, user_id=current_user.id,
            temperature=temperature, stream=False,
            doc_ids=doc_ids if doc_ids else None
        )

        save_message(db, chat_id, current_user.id, "assistant", answer)
        return {"answer": answer, "sources": sources, "regenerated": regenerate}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post("/{chat_id}/stream")
async def chat_message_stream(
    chat_id: int,
    query: str,
    regenerate: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        # FIX: save the user message immediately on the request db session,
        # which is guaranteed to be open at this point.
        if not regenerate:
            save_message(db, chat_id, current_user.id, "user", query)

        temperature = 0.9 if regenerate else 0.7
        doc_ids = get_user_document_ids(db, current_user.id)

        # Capture values we need inside the generator BEFORE db session closes
        captured_chat_id = chat_id
        captured_user_id = current_user.id

        generator, sources = rag_answer(
            query, user_id=current_user.id, temperature=temperature, stream=True,
            doc_ids=doc_ids if doc_ids else None
        )

        sources_json = json.dumps({"done": True, "sources": sources})
        accumulated_tokens = []

        async def event_generator() -> AsyncGenerator[str, None]:
            loop = asyncio.get_event_loop()
            queue: asyncio.Queue[str | None] = asyncio.Queue()

            def sync_producer():
                try:
                    for token in generator:
                        loop.call_soon_threadsafe(queue.put_nowait, token)
                finally:
                    loop.call_soon_threadsafe(queue.put_nowait, None)

            import threading
            thread = threading.Thread(target=sync_producer)
            thread.start()

            try:
                while True:
                    item = await queue.get()
                    if item is None:
                        break
                    if item.startswith("data: "):
                        try:
                            data = json.loads(item[6:])
                            if "token" in data:
                                accumulated_tokens.append(data["token"])
                        except Exception:
                            pass
                    yield item
            finally:
                thread.join(timeout=30)

            yield f"data: {sources_json}\n\n"

            # FIX: use captured IDs (not current_user — that object is tied to the
            # closed request db session and will raise DetachedInstanceError here)
            if accumulated_tokens:
                full_answer = "".join(accumulated_tokens)
                try:
                    from .database import SessionLocal
                    save_db = SessionLocal()
                    try:
                        save_message(save_db, captured_chat_id, captured_user_id, "assistant", full_answer)
                        save_db.commit()
                    finally:
                        save_db.close()
                except Exception as e:
                    print(f"⚠️  Failed to save streaming response: {e}")

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))    
@router.get("/{chat_id}/messages")
async def get_messages(
    chat_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all messages in a chat (user-isolated)"""
    try:
        messages = get_chat_messages(db, chat_id, current_user.id)
        return {"messages": messages}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/")
async def list_chats(
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    chats = get_user_chats(db, current_user.id, limit=limit, offset=offset)
    total = get_user_chat_count(db, current_user.id)
    return {
        "chats": chats,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": (offset + limit) < total
    }


@router.delete("/{chat_id}")
async def remove_chat(
    chat_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a chat (user-isolated)"""
    success = delete_chat(db, chat_id, current_user.id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
    return {"message": "Chat deleted successfully"}


@router.put("/{chat_id}/title")
async def rename_chat(
    chat_id: int,
    title: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Rename a chat (user-isolated)"""
    chat = update_chat_title(db, chat_id, current_user.id, title)
    if not chat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
    return {"message": "Chat renamed successfully"}