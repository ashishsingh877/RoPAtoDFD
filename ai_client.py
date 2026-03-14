"""
ai_client.py  —  Google Gemini API wrapper
gemini-2.5-flash / gemini-2.5-pro
"""

import json, re, requests

BASE       = "https://generativelanguage.googleapis.com/v1beta/models"
ALL_MODELS = ["gemini-2.5-flash", "gemini-2.5-pro"]

def _body(system: str, user: str, max_tokens: int) -> dict:
    return {
        "system_instruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": user}]}],
        "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.2}
    }

def _extract_text(data: dict) -> str:
    """Collect all non-thought text parts from a Gemini response."""
    parts = []
    for cand in data.get("candidates", []):
        for part in cand.get("content", {}).get("parts", []):
            if not part.get("thought") and part.get("text"):
                parts.append(part["text"])
    return "\n".join(parts)

def chat(api_key: str, system: str, user: str,
         max_tokens: int = 6000, model: str = "gemini-2.5-flash") -> str:
    """Blocking call — returns full response text."""
    payload = _body(system, user, max_tokens)
    models  = [model] + [m for m in ALL_MODELS if m != model]
    errors  = []
    for m in models:
        url = f"{BASE}/{m}:generateContent?key={api_key}"
        try:
            r = requests.post(url, json=payload, timeout=300)
            if r.status_code == 200:
                txt = _extract_text(r.json())
                if txt:
                    return txt
                errors.append(f"[{m}] empty response body")
                continue
            if r.status_code == 401:
                raise ValueError("Invalid API key. Visit https://aistudio.google.com/apikey")
            if r.status_code == 403:
                raise ValueError("Permission denied (403). Enable Generative Language API.")
            try:    msg = r.json().get("error", {}).get("message", r.text[:300])
            except: msg = r.text[:300]
            errors.append(f"[{m}] {r.status_code}: {msg}")
        except ValueError: raise
        except Exception as e: errors.append(f"[{m}] {e}")
    raise ValueError("Gemini failed:\n" + "\n".join(errors))


def stream_chat(api_key: str, system: str, user: str,
                max_tokens: int = 6000, model: str = "gemini-2.5-flash"):
    """Streaming — for display only. Falls back to blocking automatically."""
    # For streaming we collect everything then yield it so we never lose chunks
    try:
        full = chat(api_key, system, user, max_tokens, model)
        # Yield in chunks for the live preview effect
        chunk_size = 120
        for i in range(0, len(full), chunk_size):
            yield full[i:i+chunk_size]
    except Exception as e:
        raise ValueError(str(e))


def parse_json_from_response(text: str) -> list:
    """
    Robust JSON extractor. Handles:
    - ```json ... ``` fences
    - Prose before/after JSON
    - Truncated closing fence
    - Trailing commas
    """
    if not text:
        raise ValueError("Empty response from Gemini")

    # Step 1: strip ALL backtick fences and surrounding whitespace
    cleaned = re.sub(r"```+\w*", "", text)
    cleaned = cleaned.strip()

    # Step 2: find the outermost [ ... ] array
    s = cleaned.find("[")
    e = cleaned.rfind("]")
    if s != -1 and e > s:
        candidate = cleaned[s : e + 1]
        # Fix trailing commas (common LLM mistake)
        candidate = re.sub(r",\s*([\]\}])", r"\1", candidate)
        try:
            result = json.loads(candidate)
            return result if isinstance(result, list) else [result]
        except json.JSONDecodeError:
            pass

    # Step 3: find outermost { ... } object
    s = cleaned.find("{")
    e = cleaned.rfind("}")
    if s != -1 and e > s:
        candidate = cleaned[s : e + 1]
        candidate = re.sub(r",\s*([\]\}])", r"\1", candidate)
        try:
            return [json.loads(candidate)]
        except json.JSONDecodeError:
            pass

    # Step 4: direct parse
    try:
        result = json.loads(cleaned)
        return result if isinstance(result, list) else [result]
    except Exception:
        pass

    raise ValueError(
        f"Could not extract valid JSON.\nFirst 600 chars:\n{text[:600]}"
    )
