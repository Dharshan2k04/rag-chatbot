from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from .database import (
    create_chat, 
    save_message, 
    get_chat_messages, 
    get_all_chats,
    delete_chat,
    update_chat_title
)
from .rag import rag_answer
import json

router = APIRouter()

@router.post("/chat/new")
async def new_chat():
    """Create a new chat session"""
    chat_id = create_chat()
    return {"chat_id": chat_id, "message": "New chat created"}

@router.post("/chat/{chat_id}")
async def chat_message(chat_id: int, query: str, regenerate: bool = False):
    """Send a message in a chat"""
    try:
        # If not regenerating, save user message
        if not regenerate:
            save_message(chat_id, "user", query)
        
        # Use higher temperature for regeneration (more variation)
        temperature = 0.9 if regenerate else 0.7
        
        # Get RAG answer (non-streaming for now)
        answer, sources = rag_answer(query, temperature=temperature, stream=False)
        
        # Save assistant message
        save_message(chat_id, "assistant", answer)
        
        return {
            "answer": answer,
            "sources": sources,
            "regenerated": regenerate
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/chat/{chat_id}/stream")
async def chat_message_stream(chat_id: int, query: str, regenerate: bool = False):
    """Send a message with streaming response"""
    try:
        # If not regenerating, save user message
        if not regenerate:
            save_message(chat_id, "user", query)
        
        # Use higher temperature for regeneration
        temperature = 0.9 if regenerate else 0.7
        
        # Get RAG answer with streaming
        response, sources = rag_answer(query, temperature=temperature, stream=True)
        
        async def generate():
            """Stream the response"""
            full_answer = ""
            
            # Stream chunks
            for line in response.iter_lines():
                if line:
                    try:
                        json_response = json.loads(line)
                        if "response" in json_response:
                            token = json_response["response"]
                            full_answer += token
                            
                            # Send token to client
                            yield f"data: {json.dumps({'token': token})}\n\n"
                        
                        # Check if done
                        if json_response.get("done", False):
                            # Save complete answer
                            save_message(chat_id, "assistant", full_answer)
                            
                            # Send sources
                            yield f"data: {json.dumps({'done': True, 'sources': sources})}\n\n"
                            break
                    except json.JSONDecodeError:
                        continue
        
        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            }
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/chat/{chat_id}/messages")
async def get_messages(chat_id: int):
    """Get all messages in a chat"""
    messages = get_chat_messages(chat_id)
    return {"messages": messages}

@router.get("/chats")
async def list_chats():
    """List all chats"""
    chats = get_all_chats()
    return {"chats": chats}

@router.delete("/chat/{chat_id}")
async def remove_chat(chat_id: int):
    """Delete a chat"""
    try:
        delete_chat(chat_id)
        return {"message": "Chat deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/chat/{chat_id}/title")
async def rename_chat(chat_id: int, title: str):
    """Rename a chat"""
    try:
        update_chat_title(chat_id, title)
        return {"message": "Chat renamed successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))