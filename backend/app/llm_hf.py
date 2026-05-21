from groq import Groq
import os
import json
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")

def get_client():
    """Lazy Groq client initialization"""
    if not GROQ_API_KEY:
        return None
    return Groq(api_key=GROQ_API_KEY)

MODEL = "llama-3.1-8b-instant"

SYSTEM_PROMPT = (
    "You are a helpful AI assistant analyzing documents. "
    "Answer questions based ONLY on the provided context. "
    "If the information is NOT in the context, say 'I cannot find this information in the provided document.' "
    "Be specific and cite relevant details."
)

def _build_messages(prompt: str, context: str = "") -> list[dict]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"Context:\n{context}\n\nQuestion: {prompt}\n\nAnswer (based strictly on the context above):",
        },
    ]

def query_huggingface(prompt: str, context: str = "", temperature: float = 0.7, stream: bool = False):
    if not GROQ_API_KEY:
        return "Error: GROQ_API_KEY not configured. Please add it to Space secrets."

    messages = _build_messages(prompt, context)
    print(f"🚀 Querying Groq with model: {MODEL}")

    try:
        response = get_client().chat.completions.create(
            messages=messages,
            model=MODEL,
            temperature=temperature,
            max_tokens=1024,
            top_p=0.9,
            stream=False,
        )
        answer = response.choices[0].message.content
        print(f"✅ Got response: {answer[:100]}...")
        return answer
    except Exception as e:
        print(f"❌ Groq API Error: {str(e)}")
        return f"Error: {str(e)}"

def stream_groq_response(prompt: str, context: str = "", temperature: float = 0.7):
    if not GROQ_API_KEY:
        yield f"data: {json.dumps({'token': 'Error: GROQ_API_KEY not configured.'})}\n\n"
        yield f"data: {json.dumps({'done': True, 'sources': []})}\n\n"
        return

    messages = _build_messages(prompt, context)
    print(f"🚀 Streaming from Groq with model: {MODEL}")

    try:
        response = get_client().chat.completions.create(
            messages=messages,
            model=MODEL,
            temperature=temperature,
            max_tokens=1024,
            top_p=0.9,
            stream=True,
        )

        for chunk in response:
            delta = chunk.choices[0].delta.content or ""
            if delta:
                yield f"data: {json.dumps({'token': delta})}\n\n"

        yield f"data: {json.dumps({'done': True, 'sources': []})}\n\n"
    except Exception as e:
        print(f"❌ Groq Streaming Error: {str(e)}")
        yield f"data: {json.dumps({'token': f'Error: {str(e)}'})}\n\n"
        yield f"data: {json.dumps({'done': True, 'sources': []})}\n\n"