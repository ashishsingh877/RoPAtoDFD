"""
ai_client.py  —  Google Gemini API wrapper
Uses: gemini-1.5-pro (best quality) with fallback to gemini-1.5-flash
"""

import json
import re
import requests

GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta/models"

def _model_url(model: str, api_key: str, stream: bool = False) -> str:
    action = "streamGenerateContent" if stream else "generateContent"
    return f"{GEMINI_BASE}/{model}:{action}?key={api_key}"

def _build_body(system: str, user: str, max_tokens: int) -> dict:
    return {
        "system_instruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": user}]}],
        "generationConfig": {
            "maxOutputTokens": max_tokens,
            "temperature": 0.2,
        }
    }

def chat(api_key: str, system: str, user: str,
         max_tokens: int = 6000, model: str = "gemini-1.5-pro") -> str:
    """Blocking Gemini call. Returns full response text."""
    body = _build_body(system, user, max_tokens)
    for try_model in [model, "gemini-1.5-flash", "gemini-1.5-pro"]:
        try:
            r = requests.post(_model_url(try_model, api_key, stream=False),
                              json=body, timeout=120)
            if r.status_code == 200:
                data = r.json()
                return data["candidates"][0]["content"]["parts"][0]["text"]
            elif r.status_code == 429:
                continue   # quota hit, try next model
            else:
                raise ValueError(f"Gemini error {r.status_code}: {r.text[:300]}")
        except (ValueError, KeyError):
            raise
        except Exception as e:
            raise ValueError(f"Gemini request failed: {e}")
    raise ValueError("All Gemini models failed (quota exceeded?)")


def stream_chat(api_key: str, system: str, user: str,
                max_tokens: int = 6000, model: str = "gemini-1.5-pro"):
    """
    Streaming Gemini call. Yields text chunks.
    Falls back to blocking call if streaming fails.
    """
    body = _build_body(system, user, max_tokens)
    try:
        r = requests.post(_model_url(model, api_key, stream=True),
                          json=body, stream=True, timeout=180)
        if r.status_code != 200:
            # fall back to blocking
            yield chat(api_key, system, user, max_tokens, model)
            return

        buffer = ""
        for raw_line in r.iter_lines(decode_unicode=True):
            if not raw_line:
                continue
            line = raw_line.strip()
            if line.startswith("data:"):
                line = line[5:].strip()
            if not line or line == "[DONE]":
                continue
            buffer += line
            # Try to extract text chunks from accumulated JSON fragments
            try:
                obj = json.loads(buffer)
                buffer = ""
                for cand in obj.get("candidates", []):
                    for part in cand.get("content", {}).get("parts", []):
                        txt = part.get("text", "")
                        if txt:
                            yield txt
            except json.JSONDecodeError:
                # Incomplete JSON — keep buffering
                pass

        # Flush any remaining buffer
        if buffer:
            try:
                obj = json.loads(buffer)
                for cand in obj.get("candidates", []):
                    for part in cand.get("content", {}).get("parts", []):
                        txt = part.get("text", "")
                        if txt:
                            yield txt
            except Exception:
                pass

    except Exception:
        # Full fallback to blocking
        yield chat(api_key, system, user, max_tokens, model)


def parse_json_from_response(text: str) -> list:
    """
    Extract a JSON array from Gemini response.
    Handles markdown fences and leading/trailing text.
    """
    if not text:
        raise ValueError("Empty response")

    # Strip markdown fences
    cleaned = re.sub(r"```(?:json)?", "", text).strip().rstrip("`").strip()

    # Try direct parse
    try:
        result = json.loads(cleaned)
        return result if isinstance(result, list) else [result]
    except json.JSONDecodeError:
        pass

    # Find first [ ... ] block
    start = cleaned.find("[")
    end   = cleaned.rfind("]")
    if start != -1 and end > start:
        try:
            result = json.loads(cleaned[start:end+1])
            return result if isinstance(result, list) else [result]
        except json.JSONDecodeError:
            pass

    # Find first { ... } block (single object)
    start = cleaned.find("{")
    end   = cleaned.rfind("}")
    if start != -1 and end > start:
        try:
            result = json.loads(cleaned[start:end+1])
            return [result]
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Could not parse JSON from response. First 200 chars: {text[:200]}")
