"""
ai_client.py  —  Google Gemini API wrapper
Uses v1beta REST API with correct current model names.
"""

import json, re, requests

GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta/models"

# Correct model IDs as of 2025 — in order of preference
FALLBACK_MODELS = [
    "gemini-2.0-flash",
    "gemini-1.5-flash-latest",
    "gemini-1.5-flash",
    "gemini-1.5-pro-latest",
]

def _url(model: str, api_key: str, stream: bool = False) -> str:
    action = "streamGenerateContent" if stream else "generateContent"
    return f"{GEMINI_BASE}/{model}:{action}?key={api_key}"

def _body(system: str, user: str, max_tokens: int) -> dict:
    return {
        "system_instruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": user}]}],
        "generationConfig": {
            "maxOutputTokens": max_tokens,
            "temperature": 0.2,
        }
    }

def chat(api_key: str, system: str, user: str,
         max_tokens: int = 6000, model: str = "gemini-2.0-flash") -> str:
    """Blocking call — tries primary model then fallbacks."""
    payload = _body(system, user, max_tokens)
    models_to_try = [model] + [m for m in FALLBACK_MODELS if m != model]

    for m in models_to_try:
        try:
            r = requests.post(_url(m, api_key, stream=False),
                              json=payload, timeout=120)
            if r.status_code == 200:
                data = r.json()
                return data["candidates"][0]["content"]["parts"][0]["text"]
            elif r.status_code in (404, 400):
                continue   # model not available, try next
            elif r.status_code == 429:
                continue   # quota, try next
            else:
                raise ValueError(f"Gemini error {r.status_code}: {r.text[:400]}")
        except (KeyError, IndexError):
            continue
        except ValueError:
            raise
        except Exception as e:
            raise ValueError(f"Request failed: {e}")

    raise ValueError(
        "No working Gemini model found. "
        "Check your API key is valid at aistudio.google.com"
    )


def stream_chat(api_key: str, system: str, user: str,
                max_tokens: int = 6000, model: str = "gemini-2.0-flash"):
    """Streaming call — yields text chunks. Falls back to blocking if needed."""
    payload = _body(system, user, max_tokens)
    models_to_try = [model] + [m for m in FALLBACK_MODELS if m != model]

    for m in models_to_try:
        try:
            r = requests.post(_url(m, api_key, stream=True),
                              json=payload, stream=True, timeout=180)
            if r.status_code in (404, 400):
                continue
            if r.status_code != 200:
                raise ValueError(f"Gemini error {r.status_code}: {r.text[:400]}")

            # Stream JSON lines
            buffer = ""
            for raw in r.iter_lines(decode_unicode=True):
                if not raw:
                    continue
                line = raw.strip().lstrip("data:").strip()
                if not line or line == "[DONE]":
                    continue
                buffer += line
                try:
                    obj = json.loads(buffer)
                    buffer = ""
                    for cand in obj.get("candidates", []):
                        for part in cand.get("content", {}).get("parts", []):
                            txt = part.get("text", "")
                            if txt:
                                yield txt
                except json.JSONDecodeError:
                    pass  # incomplete chunk, keep buffering

            # Flush remaining buffer
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
            return  # success — done

        except ValueError:
            raise
        except Exception as e:
            raise ValueError(f"Streaming failed: {e}")

    # All models failed — fall back to blocking
    yield chat(api_key, system, user, max_tokens, model)


def parse_json_from_response(text: str) -> list:
    """Extract JSON array from Gemini response (handles markdown fences)."""
    if not text:
        raise ValueError("Empty response from Gemini")

    cleaned = re.sub(r"```(?:json)?", "", text).strip().rstrip("`").strip()

    # Try direct parse
    try:
        r = json.loads(cleaned)
        return r if isinstance(r, list) else [r]
    except json.JSONDecodeError:
        pass

    # Find outermost [ ... ]
    s, e = cleaned.find("["), cleaned.rfind("]")
    if s != -1 and e > s:
        try:
            r = json.loads(cleaned[s:e+1])
            return r if isinstance(r, list) else [r]
        except json.JSONDecodeError:
            pass

    # Find outermost { ... }
    s, e = cleaned.find("{"), cleaned.rfind("}")
    if s != -1 and e > s:
        try:
            return [json.loads(cleaned[s:e+1])]
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Could not parse JSON. Response start: {text[:300]}")
