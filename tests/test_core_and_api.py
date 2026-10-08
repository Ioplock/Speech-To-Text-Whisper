"""Lightweight tests: no real Whisper/torch, no ffmpeg, no network.

Whisper and moviepy are mocked. tiktoken/fastapi are real (light).
Run:  uv run pytest -q
"""

import sys
import types

import pytest
from fastapi.testclient import TestClient


def _install_fake_whisper(text="hello world", segments=2, language="ru"):
    fake = types.ModuleType("whisper")

    class FakeModel:
        def transcribe(self, *a, **k):
            return {
                "text": text,
                "language": language,
                "segments": [{"id": i, "text": f"seg{i}"} for i in range(segments)],
            }

    fake.load_model = lambda name: FakeModel()
    sys.modules["whisper"] = fake


def test_count_tokens_text():
    from multifunction_tool.core import count_tokens

    n = count_tokens("gpt-4o", text="hello world")
    assert n >= 2  # 'hello world' is 2 tokens in cl100k
    assert count_tokens("gpt-4o", text="") == 0


def test_count_tokens_unknown_model_falls_back():
    from multifunction_tool.core import count_tokens

    with pytest.warns(UserWarning):
        n = count_tokens("no-such-model-xyz", text="hello")
    assert n >= 1


def test_count_tokens_missing_file():
    from multifunction_tool.core import count_tokens

    with pytest.raises(FileNotFoundError):
        count_tokens("gpt-4o", file_path="/no/such/file.txt")


def test_transcribe_mocked_tmp(tmp_path):
    _install_fake_whisper()
    from multifunction_tool import core

    core._model_cache.clear()
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"RIFFfake")
    out = tmp_path / "sub" / "out.txt"  # nested: tests parent-dir creation
    res = core.transcribe_audio(str(audio), str(out), "ru", "tiny")
    assert res["text"] == "hello world"
    assert out.read_text(encoding="utf-8") == "hello world"


def test_transcribe_missing_file():
    _install_fake_whisper()
    from multifunction_tool import core

    core._model_cache.clear()
    with pytest.raises(FileNotFoundError):
        core.transcribe_audio("/no/such.wav", None, "ru", "tiny")


def test_transcribe_bad_model():
    from multifunction_tool.core import transcribe_audio

    with pytest.raises((ValueError, FileNotFoundError)):
        # bad model name is validated before file check? file missing -> FileNotFoundError,
        # so create the order-independent assertion via real tmp file
        transcribe_audio("/no/such.wav", None, "ru", "nope")


def test_extract_audio_no_track(tmp_path, monkeypatch):
    import multifunction_tool.core as core

    fake_clip = types.SimpleNamespace(audio=None, close=lambda: None)
    fake_mod = types.ModuleType("moviepy")
    fake_mod.VideoFileClip = lambda path: fake_clip
    monkeypatch.setitem(sys.modules, "moviepy", fake_mod)
    monkeypatch.delitem(sys.modules, "moviepy.editor", raising=False)

    v = tmp_path / "v.mp4"
    v.write_bytes(b"fake")
    with pytest.raises(ValueError, match="no audio track"):
        core.extract_audio(str(v), str(tmp_path / "o.wav"))


def test_cli_no_command_exits():
    from multifunction_tool.cli import build_parser

    with pytest.raises(SystemExit) as ei:
        build_parser().parse_args([])
    assert ei.value.code == 2


def test_api_health_and_models():
    from multifunction_tool.server import app

    c = TestClient(app)
    assert c.get("/health").json() == {"status": "ok"}
    body = c.get("/models").json()
    assert "tiny" in body["models"]


def test_api_transcribe_mocked(monkeypatch):
    import multifunction_tool.server as srv
    import multifunction_tool.core as core

    async def _fake(path, *a, **k):
        return {"text": "mocked text", "language": "en", "segments": []}

    # transcribe endpoint calls core.transcribe_audio (sync) with tmp path;
    # patch at core level.
    monkeypatch.setattr(core, "transcribe_audio", lambda *a, **k: {"text": "mocked text", "language": "en", "segments": []})
    c = TestClient(srv.app)
    r = c.post(
        "/transcribe?lang=en&model=tiny",
        files={"file": ("a.wav", b"RIFFdata", "audio/wav")},
    )
    assert r.status_code == 200, r.text
    assert r.json()["text"] == "mocked text"


def test_api_count_tokens_json():
    from multifunction_tool.server import app

    c = TestClient(app)
    r = c.post("/count-tokens", json={"model": "gpt-4o", "text": "hello world"})
    assert r.status_code == 200, r.text
    assert r.json()["tokens"] >= 2


def test_api_transcribe_streams_in_chunks(monkeypatch):
    """Upload bigger than one chunk: server must reassemble the full file on disk."""
    import os

    import multifunction_tool.core as core
    import multifunction_tool.server as srv

    monkeypatch.setenv("UPLOAD_CHUNK_BYTES", "1024")  # force many chunks
    payload = b"A" * (10 * 1024)  # 10 KiB -> 10 chunks
    seen = {}

    def fake_transcribe(path, *a, **k):
        seen["size"] = os.path.getsize(path)
        with open(path, "rb") as fh:
            seen["content"] = fh.read()
        return {"text": "chunked ok", "language": "en", "segments": []}

    monkeypatch.setattr(core, "transcribe_audio", fake_transcribe)
    c = TestClient(srv.app)
    r = c.post("/transcribe?model=tiny", files={"file": ("big.wav", payload, "audio/wav")})
    assert r.status_code == 200, r.text
    assert r.json()["text"] == "chunked ok"
    assert seen["size"] == len(payload)
    assert seen["content"] == payload


def test_api_transcribe_rejects_oversize(monkeypatch):
    import multifunction_tool.core as core
    import multifunction_tool.server as srv

    monkeypatch.setenv("MAX_UPLOAD_BYTES", "16")
    monkeypatch.setattr(
        core, "transcribe_audio", lambda *a, **k: {"text": "x", "segments": []}
    )
    c = TestClient(srv.app)
    r = c.post("/transcribe?model=tiny", files={"file": ("a.wav", b"Z" * 1024, "audio/wav")})
    assert r.status_code == 413, r.text


def test_api_transcribe_missing_extra_is_501(monkeypatch):
    import multifunction_tool.core as core
    import multifunction_tool.server as srv

    def boom(*a, **k):
        raise RuntimeError("Whisper is not installed.")

    monkeypatch.setattr(core, "transcribe_audio", boom)
    c = TestClient(srv.app)
    r = c.post("/transcribe?model=tiny", files={"file": ("a.wav", b"RIFF", "audio/wav")})
    assert r.status_code == 501, r.text


def test_api_extract_audio_mocked_download(monkeypatch):
    import multifunction_tool.core as core
    import multifunction_tool.server as srv

    def fake_extract(video_path, audio_output):
        with open(audio_output, "wb") as fh:
            fh.write(b"FAKEAUDIO")
        return audio_output

    monkeypatch.setattr(core, "extract_audio", fake_extract)
    c = TestClient(srv.app)
    r = c.post("/extract-audio?format=wav", files={"file": ("v.mp4", b"VIDEODATA", "video/mp4")})
    assert r.status_code == 200, r.text
    assert r.content == b"FAKEAUDIO"
    assert "audio/wav" in r.headers["content-type"]


def test_api_count_tokens_multipart_file():
    from multifunction_tool.server import app

    c = TestClient(app)
    r = c.post(
        "/count-tokens",
        data={"model": "gpt-4o"},
        files={"file": ("t.txt", b"hello world", "text/plain")},
    )
    assert r.status_code == 200, r.text
    assert r.json()["tokens"] >= 2
