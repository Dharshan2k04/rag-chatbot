import requests
import json

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "phi"  # Fast and quality balanced

def query_ollama(prompt, context="", temperature=0.7, stream=False):
    """Query Ollama with context and temperature control
    
    Temperature:
    - 0.3-0.5: More focused, deterministic answers
    - 0.7-0.9: More creative, varied answers (good for regenerate)
    - 1.0+: Very creative, potentially inconsistent
    """
    
    # Enhanced prompt for better accuracy
    full_prompt = f"""You are a helpful AI assistant analyzing documents. Your task is to answer questions based ONLY on the provided context.

IMPORTANT RULES:
1. Answer ONLY using information from the context below
2. If the context contains the answer, provide it clearly and completely
3. If the information is NOT in the context, say "I cannot find this information in the provided document"
4. Be specific and cite relevant details from the context
5. For lists (like projects), include ALL items mentioned in the context

Context:
{context}

Question: {prompt}

Answer (based strictly on the context above):"""
    
    payload = {
        "model": MODEL,
        "prompt": full_prompt,
        "stream": stream,
        "options": {
            "temperature": temperature,
            "num_predict": 512,  # Increased for complete answers
            "top_p": 0.9,
            "top_k": 40,
            "num_ctx": 4096,  # Increased context window
            "repeat_penalty": 1.1  # Reduce repetition/hallucination
        }
    }
    
    print(f"🤖 Querying Ollama with model: {MODEL}")
    print(f"🌡️  Temperature: {temperature}, Stream: {stream}")
    
    try:
        if stream:
            # Streaming mode
            response = requests.post(OLLAMA_URL, json=payload, stream=True, timeout=120)
            response.raise_for_status()
            return response
        else:
            # Non-streaming mode
            response = requests.post(OLLAMA_URL, json=payload, timeout=120)
            response.raise_for_status()
            result = response.json()
            
            answer = result.get("response", "No response from model")
            print(f"✅ Got response: {answer[:100]}...")
            
            return answer
    except requests.exceptions.Timeout:
        print("❌ Ollama request timed out")
        return "Error: Request timed out. Ollama might be slow or not responding."
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to Ollama")
        return "Error: Cannot connect to Ollama. Make sure it's running with 'ollama serve'"
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return f"Error querying Ollama: {str(e)}"