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
    
    # Optimized prompt - shorter and more direct
    full_prompt = f"""Context:
{context}

Question: {prompt}

Provide a clear, concise answer based on the context above."""
    
    payload = {
        "model": MODEL,
        "prompt": full_prompt,
        "stream": stream,
        "options": {
            "temperature": temperature,
            "num_predict": 300,  # Reduced from 512 for faster responses
            "top_p": 0.9,
            "top_k": 40,
            "num_ctx": 2048  # Optimized context window
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