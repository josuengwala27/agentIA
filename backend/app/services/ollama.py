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


def parse_json_response(content: str) -> Any:
    content = content.strip()
    if content.startswith("```"):
        lines = content.split("\n")
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        content = "\n".join(lines)
    return json.loads(content)
