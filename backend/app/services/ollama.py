import json
from typing import Any

import httpx

from app.core.config import settings


class OllamaError(Exception):
    pass


async def embed_texts(texts: list[str]) -> list[list[float]]:
    vectors: list[list[float]] = []
    async with httpx.AsyncClient(base_url=settings.ollama_base_url, timeout=120.0) as client:
        for text in texts:
            response = await client.post(
                "/api/embeddings",
                json={"model": settings.ollama_embed_model, "prompt": text},
            )
            if response.status_code != 200:
                raise OllamaError(f"Embeddings échoués: {response.text}")
            data = response.json()
            vectors.append(data["embedding"])
    return vectors


async def chat_completion(
    messages: list[dict[str, str]],
    temperature: float = 0.2,
    format_json: bool = False,
) -> str:
    payload: dict[str, Any] = {
        "model": settings.ollama_llm_model,
        "messages": messages,
        "stream": False,
        "options": {"temperature": temperature},
    }
    if format_json:
        payload["format"] = "json"
    async with httpx.AsyncClient(base_url=settings.ollama_base_url, timeout=300.0) as client:
        response = await client.post("/api/chat", json=payload)
        if response.status_code != 200:
            raise OllamaError(f"Chat échoué: {response.text}")
        data = response.json()
        return data["message"]["content"]


def parse_ollama_stream_line(line: str) -> tuple[str, bool]:
    """Return (token, done) from one Ollama NDJSON chat line."""
    data = json.loads(line)
    token = str((data.get("message") or {}).get("content") or "")
    return token, bool(data.get("done"))


async def chat_completion_stream(
    messages: list[dict[str, str]],
    temperature: float = 0.2,
):
    payload: dict[str, Any] = {
        "model": settings.ollama_llm_model,
        "messages": messages,
        "stream": True,
        "options": {"temperature": temperature},
    }
    async with httpx.AsyncClient(base_url=settings.ollama_base_url, timeout=300.0) as client:
        async with client.stream("POST", "/api/chat", json=payload) as response:
            if response.status_code != 200:
                body = (await response.aread()).decode("utf-8", errors="replace")
                raise OllamaError(f"Chat échoué: {body}")
            async for line in response.aiter_lines():
                if not line.strip():
                    continue
                token, done = parse_ollama_stream_line(line)
                if token:
                    yield token
                if done:
                    break


def parse_json_response(content: str) -> Any:
    content = (content or "").strip()
    if content.startswith("```"):
        lines = content.split("\n")
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        content = "\n".join(lines).strip()
    candidates = [content]
    start = content.find("{")
    end = content.rfind("}")
    if start >= 0 and end > start:
        candidates.append(content[start : end + 1])
    last_error: Exception | None = None
    for raw in candidates:
        for variant in (raw, _repair_json(raw)):
            try:
                return json.loads(variant)
            except json.JSONDecodeError as exc:
                last_error = exc
                continue
    raise last_error or json.JSONDecodeError("JSON invalide", content, 0)


def _repair_json(raw: str) -> str:
    import re

    repaired = re.sub(r",\s*([}\]])", r"\1", raw)
    repaired = repaired.replace("\r\n", "\n")
    return repaired
