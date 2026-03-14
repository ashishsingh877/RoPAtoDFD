"""
ai_client.py  —  Google Gemini API wrapper
Handles gemini-2.5-flash / gemini-2.5-pro thinking output + robust JSON parsing.
"""

import json, re, requests

BASE = "https://generativelanguage.googleapis.com/v1beta/models"

ALL_MODELS = ["gemini-2.5-flash", "gemini-2.5-pro"]

def _body(system: str, user: str, max_tokens: int) -> dict:
    return {
        "system_instruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": user}]}],
        "generationConfig": {
            "maxOutputTokens": max_tokens,
            "temperature": 0.2,
        }
    }

def _extract_text(data: dict) -> str:
    """Extract all text parts from response, skipping thought parts."""
    text_parts = []
    for cand in data.get("candidates", []):
        for part in cand.get("content", {}).get("parts", []):
            # Skip thinking/thought parts — only take regular text
            if part.get("thought"):
                continue
            txt = part.get("text", "")
            if txt:
                text_parts.append(txt)
    return "\n".join(text_parts)

def chat(api_key: str, system: str, user: str,
         max_tokens: int = 6000, model: str = "gemini-2.5-flash") -> str:
    payload = _body(system, user, max_tokens)
    models  = [model] + [m for m in ALL_MODELS if m != model]
    errors  = []
    for m in models:
        url = f"{BASE}/{m}:generateContent?key={api_key}"
        try:
            r = requests.post(url, json=payload, timeout=180)
            if r.status_code == 200:
                return _extract_text(r.json())
            if r.status_code == 401:
                raise ValueError("Invalid API key. Get one at https://aistudio.google.com/apikey")
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
    """Stream response, skipping thought chunks."""
    payload = _body(system, user, max_tokens)
    models  = [model] + [m for m in ALL_MODELS if m != model]

    for m in models:
        url = f"{BASE}/{m}:streamGenerateContent?key={api_key}"
        try:
            r = requests.post(url, json=payload, stream=True, timeout=300)
            if r.status_code == 401:
                raise ValueError("Invalid API key.")
            if r.status_code == 403:
                raise ValueError("Permission denied (403).")
            if r.status_code != 200:
                continue

            buffer, got_any = "", False
            for raw in r.iter_lines(decode_unicode=True):
                if not raw: continue
                line = raw.strip().lstrip("data:").strip()
                if not line or line == "[DONE]": continue
                buffer += line
                try:
                    obj = json.loads(buffer)
                    buffer = ""
                    for cand in obj.get("candidates", []):
                        for part in cand.get("content", {}).get("parts", []):
                            # Skip thought parts
                            if part.get("thought"): continue
                            txt = part.get("text", "")
                            if txt:
                                got_any = True
                                yield txt
                except json.JSONDecodeError:
                    pass

            if buffer:
                try:
                    obj = json.loads(buffer)
                    for cand in obj.get("candidates", []):
                        for part in cand.get("content", {}).get("parts", []):
                            if part.get("thought"): continue
                            txt = part.get("text", "")
                            if txt:
                                got_any = True
                                yield txt
                except Exception: pass

            if got_any: return

        except ValueError: raise
        except Exception: continue

    # Fallback to blocking
    yield chat(api_key, system, user, max_tokens, model)


def parse_json_from_response(text: str) -> list:
    """
    Robust JSON extractor. Handles:
    - Gemini 2.5 thinking preamble before JSON
    - Markdown code fences
    - Leading/trailing prose
    """
    if not text:
        raise ValueError("Empty response from Gemini")

    # 1. Strip markdown fences
    cleaned = re.sub(r"```(?:json)?", "", text).strip().rstrip("`").strip()

    # 2. Remove common Gemini 2.5 preamble patterns before JSON
    #    e.g. "Here is the JSON array:\n[..."  or  "Sure! Here's the output:\n[..."
    cleaned = re.sub(
        r"^.*?([\[\{])",
        r"\1",
        cleaned,
        flags=re.DOTALL
    )

    # 3. Try to parse from first [ to last ]
    s = cleaned.find("[")
    e = cleaned.rfind("]")
    if s != -1 and e > s:
        candidate = cleaned[s:e+1]
        try:
            r = json.loads(candidate)
            return r if isinstance(r, list) else [r]
        except json.JSONDecodeError:
            # Try to fix common issues: trailing commas
            fixed = re.sub(r",\s*([\]\}])", r"\1", candidate)
            try:
                r = json.loads(fixed)
                return r if isinstance(r, list) else [r]
            except Exception:
                pass

    # 4. Try first { to last }
    s = cleaned.find("{")
    e = cleaned.rfind("}")
    if s != -1 and e > s:
        try:
            return [json.loads(cleaned[s:e+1])]
        except Exception:
            pass

    # 5. Direct parse of whole cleaned text
    try:
        r = json.loads(cleaned)
        return r if isinstance(r, list) else [r]
    except Exception:
        pass

    raise ValueError(
        f"Could not extract JSON from Gemini response.\n"
        f"First 500 chars of response:\n{text[:500]}"
    )
