from app.api.routes.chat import sse_pack
from app.services.ollama import parse_json_response, parse_ollama_stream_line


def test_sse_pack_is_event_stream_frame() -> None:
    frame = sse_pack({"type": "token", "text": "Hello"})
    assert frame.startswith("data: ")
    assert frame.endswith("\n\n")
    assert '"Hello"' in frame


def test_parse_ollama_stream_token_and_done() -> None:
    token, done = parse_ollama_stream_line(
        '{"message":{"role":"assistant","content":"Hel"},"done":false}'
    )
    assert token == "Hel"
    assert done is False
    last, finished = parse_ollama_stream_line(
        '{"message":{"role":"assistant","content":""},"done":true}'
    )
    assert last == ""
    assert finished is True


def test_parse_json_repairs_trailing_comma_and_fences() -> None:
    payload = parse_json_response('```json\n{"passage":"ok","questions":[{"id":"q1"}],}\n```')
    assert payload["passage"] == "ok"
    assert payload["questions"][0]["id"] == "q1"


def test_sse_pack_is_event_stream_frame() -> None:
    frame = sse_pack({"type": "token", "text": "Hello"})
    assert frame.startswith("data: ")
    assert frame.endswith("\n\n")
    assert '"Hello"' in frame


def test_parse_ollama_stream_token_and_done() -> None:
    token, done = parse_ollama_stream_line(
        '{"message":{"role":"assistant","content":"Hel"},"done":false}'
    )
    assert token == "Hel"
    assert done is False
    last, finished = parse_ollama_stream_line(
        '{"message":{"role":"assistant","content":""},"done":true}'
    )
    assert last == ""
    assert finished is True
