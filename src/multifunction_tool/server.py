"""Local HTTP API server (FastAPI) for the multifunction tool.

Run with:  transcript serve [--host 127.0.0.1 --port 8000]
or:        uv run uvicorn multifunction_tool.server:app --host 127.0.0.1 --port 8000

Endpoints:
  GET  /health
  GET  /models
  POST /transcribe      (multipart: file, query: lang, model, task, response_format)
  POST /extract-audio   (multipart: file, query: format=wav|mp3)
  POST /count-tokens    (JSON {model, text} OR multipart {model + text/file})

Large-file design (all handlers are async and never hold a whole upload in RAM):

  * Uploads are streamed to a temp file in 1 MiB chunks (bounded memory no
    matter how big the audio/video is). Downloads stream via FileResponse.
  * Blocking CPU work (Whisper, moviepy/ffmpeg) runs in a worker thread via
    ``asyncio.to_thread`` so the event loop stays responsive for /health etc.
  * Upload size is capped (413 over the limit) and concurrent transcriptions
    are capped by a semaphore (Whisper easily OOMs otherwise).

Tuning via environment:

  * MAX_UPLOAD_BYTES   (default 2 GiB)
  * UPLOAD_CHUNK_BYTES (default 1 MiB)
  * TRANSCRIBE_WORKERS (default 2)
"""

from __future__ import annotations

import asyncio
import os
import tempfile

from fastapi import FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel
from starlette.background import BackgroundTask

from multifunction_tool.core import VALID_TASKS, VALID_WHISPER_MODELS

app = FastAPI(title="multifunction-tool", version="1.1.0")


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def max_upload_bytes() -> int:
    return _env_int("MAX_UPLOAD_BYTES", 2 * 1024**3)


def chunk_bytes() -> int:
    return _env_int("UPLOAD_CHUNK_BYTES", 1024**2)


def _transcribe_workers() -> int:
    return max(1, _env_int("TRANSCRIBE_WORKERS", 2))


_transcribe_sem = asyncio.Semaphore(_transcribe_workers())


class TokenCountResponse(BaseModel):
    model: str
    tokens: int


class TranscribeResponse(BaseModel):
    text: str
    language: str | None = None
    segments: list = []


async def save_upload_stream(file: UploadFile, dst_path: str) -> int:
    """Stream an upload to disk in chunks. Returns total bytes.

    Raises 400 on empty upload, 413 over MAX_UPLOAD_BYTES (partial file removed).
    """
    limit = max_upload_bytes()
    step = chunk_bytes()
    total = 0
    try:
        with open(dst_path, "wb") as fh:
            while True:
                chunk = await file.read(step)
                if not chunk:
                    break
                total += len(chunk)
                if total > limit:
                    raise HTTPException(
                        status_code=413,
                        detail=f"Upload exceeds limit of {limit} bytes",
                    )
                fh.write(chunk)
    except BaseException:
        if os.path.exists(dst_path):
            os.unlink(dst_path)
        raise
    if total == 0:
        if os.path.exists(dst_path):
            os.unlink(dst_path)
        raise HTTPException(status_code=400, detail="Empty upload")
    return total


def _remove_quietly(*paths: str) -> None:
    for p in paths:
        try:
            if p and os.path.exists(p):
                os.unlink(p)
        except OSError:
            pass


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/models")
async def list_models() -> dict:
    return {"models": list(VALID_WHISPER_MODELS), "tasks": list(VALID_TASKS)}


@app.post("/transcribe")
async def transcribe(
    file: UploadFile = File(...),
    lang: str = Query("ru", description="Audio language code"),
    model: str = Query("medium", description="Whisper model name"),
    task: str = Query("transcribe", description="transcribe | translate"),
    response_format: str = Query("json", description="json | text"),
):
    from multifunction_tool.core import transcribe_audio

    if task not in VALID_TASKS:
        raise HTTPException(status_code=400, detail=f"Unknown task {task!r}")
    if model not in VALID_WHISPER_MODELS:
        raise HTTPException(status_code=400, detail=f"Unknown model {model!r}")

    suffix = os.path.splitext(file.filename or "")[1] or ".bin"
    tmp_in = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp_in.close()
    try:
        await save_upload_stream(file, tmp_in.name)
        # Whisper is blocking/CPU-heavy: run off the event loop, max N at a time.
        async with _transcribe_sem:
            try:
                result = await asyncio.to_thread(
                    transcribe_audio, tmp_in.name, None, lang, model, task
                )
            except FileNotFoundError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            except RuntimeError as exc:  # whisper extra not installed
                raise HTTPException(status_code=501, detail=str(exc)) from exc
            except Exception as exc:  # noqa: BLE001 - surface as 500 with message
                raise HTTPException(status_code=500, detail=f"Transcription failed: {exc}") from exc
    finally:
        _remove_quietly(tmp_in.name)

    text = result.get("text", "")
    if response_format == "text":
        return PlainTextResponse(text)
    return TranscribeResponse(
        text=text,
        language=result.get("language"),
        segments=result.get("segments", []),
    )


@app.post("/extract-audio")
async def extract_audio_endpoint(
    file: UploadFile = File(...),
    format: str = Query("wav", description="Output audio format: wav | mp3"),
):
    from multifunction_tool.core import extract_audio

    if format not in ("wav", "mp3"):
        raise HTTPException(status_code=400, detail="format must be 'wav' or 'mp3'")

    suffix_in = os.path.splitext(file.filename or "")[1] or ".mp4"
    tmp_in = tempfile.NamedTemporaryFile(delete=False, suffix=suffix_in)
    tmp_in.close()
    # FileResponse streams the download; BackgroundTask deletes it after send.
    tmp_out = tempfile.NamedTemporaryFile(delete=False, suffix=f".{format}")
    tmp_out.close()
    try:
        await save_upload_stream(file, tmp_in.name)
        try:
            await asyncio.to_thread(extract_audio, tmp_in.name, tmp_out.name)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:  # moviepy extra not installed
            raise HTTPException(status_code=501, detail=str(exc)) from exc
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=500, detail=f"Extraction failed: {exc}") from exc
    except BaseException:
        _remove_quietly(tmp_in.name, tmp_out.name)
        raise
    _remove_quietly(tmp_in.name)

    media = "audio/wav" if format == "wav" else "audio/mpeg"
    return FileResponse(
        tmp_out.name,
        media_type=media,
        filename=f"audio.{format}",
        background=BackgroundTask(_remove_quietly, tmp_out.name),
    )


@app.post("/count-tokens", response_model=TokenCountResponse)
async def count_tokens_endpoint(request: Request):
    """Accepts either JSON {model, text} or multipart form {model, text?, file?}."""
    from multifunction_tool.core import count_tokens

    content_type = request.headers.get("content-type", "")
    model: str | None = None
    text: str | None = None
    file_path: str | None = None

    try:
        if "multipart/form-data" in content_type:
            form = await request.form()
            model = str(form.get("model") or "")
            raw_text = form.get("text")
            text = str(raw_text) if raw_text is not None else None
            upload = form.get("file")
            # NOTE: request.form() yields starlette UploadFile, which is a different
            # class from fastapi.UploadFile -> duck-type instead of isinstance.
            if upload is not None and hasattr(upload, "read") and hasattr(upload, "filename"):
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".txt")
                tmp.close()
                await save_upload_stream(upload, tmp.name)  # type: ignore[arg-type]
                file_path = tmp.name
        else:
            try:
                body = await request.json()
            except Exception as exc:
                raise HTTPException(status_code=400, detail="Expected JSON {model, text}") from exc
            model = body.get("model")
            text = body.get("text")

        if not model:
            raise HTTPException(status_code=400, detail="Field 'model' is required")
        if text is None and file_path is None:
            raise HTTPException(status_code=400, detail="Provide 'text' or upload 'file'")

        try:
            # tiktoken encode is fast, but on huge files don't block the loop.
            n = await asyncio.to_thread(count_tokens, model, file_path, text)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=501, detail=str(exc)) from exc
        return TokenCountResponse(model=model, tokens=n)
    finally:
        if file_path:
            _remove_quietly(file_path)


__all__ = ["app"]
