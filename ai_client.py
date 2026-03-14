"""
ai_client.py  —  Google Gemini API wrapper
Models confirmed from user's API key: gemini-2.5-flash, gemini-2.5-pro
"""

import json, re, requests

BASE = "https://generativelanguage.googleapis.com/v1beta/models"

# Exact model IDs confirmed available on this key
ALL_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.5-pro",
]

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
    return data["candidates"][0]["content"]["parts"][0]["text"]

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
                raise ValueError("Invalid API key (401). Get a key at https://aistudio.google.com/apikey")
            if r.status_code == 403:
                raise ValueError("Permission denied (403). Enable Generative Language API in Google Cloud Console.")
            try:
                msg = r.json().get("error", {}).get("message", r.text[:300])
            except Exception:
                msg = r.text[:300]
            errors.append(f"[{m}] {r.status_code}: {msg}")
        except ValueError:
            raise
        except Exception as e:
            errors.append(f"[{m}] connection error: {e}")

    raise ValueError("Gemini call failed:\n" + "\n".join(errors))


def stream_chat(api_key: str, system: str, user: str,
                max_tokens: int = 6000, model: str = "gemini-2.5-flash"):
    payload = _body(system, user, max_tokens)
    models  = [model] + [m for m in ALL_MODELS if m != model]

    for m in models:
        url = f"{BASE}/{m}:streamGenerateContent?key={api_key}"
        try:
            r = requests.post(url, json=payload, stream=True, timeout=180)
            if r.status_code == 401:
                raise ValueError("Invalid API key (401).")
            if r.status_code == 403:
                raise ValueError("Permission denied (403).")
            if r.status_code != 200:
                continue

            buffer, got_any = "", False
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
                                got_any = True
                                yield txt
                except json.JSONDecodeError:
                    pass

            if buffer:
                try:
                    obj = json.loads(buffer)
                    for cand in obj.get("candidates", []):
                        for part in cand.get("content", {}).get("parts", []):
                            txt = part.get("text", "")
                            if txt:
                                got_any = True
                                yield txt
                except Exception:
                    pass

            if got_any:
                return

        except ValueError:
            raise
        except Exception:
            continue

    # Fallback to blocking
    yield chat(api_key, system, user, max_tokens, model)


def parse_json_from_response(text: str) -> list:
    if not text:
        raise ValueError("Empty response from Gemini")
    cleaned = re.sub(r"```(?:json)?", "", text).strip().rstrip("`").strip()
    for parser in [
        lambda t: json.loads(t),
        lambda t: json.loads(t[t.find("["):t.rfind("]")+1]),
        lambda t: [json.loads(t[t.find("{"):t.rfind("}")+1])],
    ]:
        try:
            r = parser(cleaned)
            return r if isinstance(r, list) else [r]
        except Exception:
            pass
    raise ValueError(f"Could not parse JSON:\n{text[:400]}")
