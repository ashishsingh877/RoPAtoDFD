"""
ai_client.py
============
Thin wrapper around the Groq REST API.
Uses llama-3.3-70b-versatile (free tier) by default.
Falls back to llama3-70b-8192 if the primary model is unavailable.
"""

import json
import re
import requests
from typing import Generator


GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

PRIMARY_MODEL  = "llama-3.3-70b-versatile"
FALLBACK_MODEL = "llama3-70b-8192"


def _headers(api_key: str) -> dict:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type":  "application/json",
    }


def chat(
    api_key:    str,
    system:     str,
    user:       str,
    max_tokens: int = 4096,
    model:      str = PRIMARY_MODEL,
) -> str:
    """Blocking single-shot call. Returns full response text."""
    payload = {
        "model":      model,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system",  "content": system},
            {"role": "user",    "content": user},
        ],
    }
    resp = requests.post(GROQ_API_URL, headers=_headers(api_key), json=payload, timeout=120)

    if resp.status_code == 404 and model == PRIMARY_MODEL:
        # Retry with fallback model
        payload["model"] = FALLBACK_MODEL
        resp = requests.post(GROQ_API_URL, headers=_headers(api_key), json=payload, timeout=120)

    if resp.status_code != 200:
        raise RuntimeError(f"Groq API error {resp.status_code}: {resp.text[:400]}")

    data = resp.json()
    return data["choices"][0]["message"]["content"]


def stream_chat(
    api_key:    str,
    system:     str,
    user:       str,
    max_tokens: int = 4096,
    model:      str = PRIMARY_MODEL,
) -> Generator[str, None, None]:
    """Server-sent-events streaming. Yields text chunks."""
    payload = {
        "model":      model,
        "max_tokens": max_tokens,
        "stream":     True,
        "messages": [
            {"role": "system",  "content": system},
            {"role": "user",    "content": user},
        ],
    }
    with requests.post(
        GROQ_API_URL,
        headers=_headers(api_key),
        json=payload,
        stream=True,
        timeout=120,
    ) as resp:
        if resp.status_code != 200:
            raise RuntimeError(f"Groq API error {resp.status_code}: {resp.text[:400]}")
        for line in resp.iter_lines():
            if not line:
                continue
            text = line.decode("utf-8")
            if text.startswith("data: "):
                text = text[6:]
            if text == "[DONE]":
                break
            try:
                chunk = json.loads(text)
                delta = chunk["choices"][0]["delta"].get("content", "")
                if delta:
                    yield delta
            except Exception:
                continue


def parse_json_from_response(text: str):
    """Extract JSON array or object from a model response."""
    # Try to find ```json ... ``` block
    match = re.search(r"```(?:json)?\s*([\s\S]+?)```", text)
    raw = match.group(1).strip() if match else text.strip()
    # Strip any trailing commentary after the last ] or }
    last_bracket = max(raw.rfind("]"), raw.rfind("}"))
    if last_bracket != -1:
        raw = raw[: last_bracket + 1]
    return json.loads(raw)
