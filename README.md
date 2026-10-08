# Multifunction Tool

> 🇷🇺 [Читать на русском](README.ru.md)

Three utilities + a local HTTP API server:

- **Transcribe** — audio → text via Whisper.
- **Extract Audio** — audio track from video.
- **Count Tokens** — token count via `tiktoken`.
- **Serve** — local REST API (FastAPI) for all of the above.

## Setup with `uv`

Requires [`uv`](https://docs.astral.sh/uv/) (available via nix: `nix shell nixpkgs#uv`).
Python version is pinned in `.python-version` (3.12).

```bash
# light install: CLI help, API server, token counting, tests
# (no torch/whisper/moviepy -> fast, laptop-friendly)
uv sync --group dev

# full install: + transcription and video support (heavy: torch, ffmpeg)
uv sync --group dev --extra whisper --extra video
# alternatives: --extra all | nix run nixpkgs#ffmpeg -- -version  (for system ffmpeg)
```

Run anything via `uv run` (uses the locked `.venv`, no activation needed):

```bash
uv run transcript --help
uv run pytest -q
```

## CLI

```bash
# Transcribe (needs --extra whisper)
uv run transcript transcribe my_audio.mp3 -o result.txt -l en -m small
uv run transcript transcribe my_audio.mp3 --task translate -l en -m turbo

# Extract audio (needs --extra video)
uv run transcript extract_audio my_video.mp4 -o extracted_audio.wav

# Count tokens (works in light install)
uv run transcript count_tokens -m gpt-4o my_text.txt
uv run transcript count_tokens -m gpt-4o --text "hello world"

# Local server
uv run transcript serve --host 127.0.0.1 --port 8000
```

Exit codes: `0` ok, `2` missing file / bad CLI usage, `3` missing optional
dependency or bad value, `1` unexpected failure.

## Local API server

> Full request/response reference (curl + Python for every endpoint):
> [`docs/API.md`](docs/API.md) · machine-readable [`docs/openapi.json`](docs/openapi.json)

```bash
uv run transcript serve --port 8000
# docs: http://127.0.0.1:8000/docs
```

| Method | Endpoint | Input | Output |
|---|---|---|---|
| GET | `/health` | — | `{"status":"ok"}` |
| GET | `/models` | — | whisper models + tasks |
| POST | `/transcribe?lang=ru&model=medium&task=transcribe&response_format=json` | multipart `file` (audio) | `{text, language, segments}` or plain text |
| POST | `/extract-audio?format=wav` | multipart `file` (video) | audio file download |
| POST | `/count-tokens` | JSON `{model, text}` **or** multipart `{model, text?/file?}` | `{model, tokens}` |

Examples:

```bash
curl -X POST "http://127.0.0.1:8000/transcribe?lang=en&model=tiny" \
  -F "file=@my_audio.mp3"

curl -X POST http://127.0.0.1:8000/count-tokens \
  -H "Content-Type: application/json" \
  -d '{"model":"gpt-4o","text":"hello world"}'

curl -X POST "http://127.0.0.1:8000/extract-audio?format=mp3" \
  -F "file=@my_video.mp4" -o audio.mp3
```

Notes:

- Whisper models are cached in memory after first load; first `/transcribe`
  call downloads weights (~75 MB–3 GB depending on model).
- Without the heavy extras the server still runs; `/transcribe` and
  `/extract-audio` answer `501` with install instructions instead of crashing.
- `response_format=text` returns plain text (handy for piping).

### Large files & async

All handlers are `async` and suitable for big audio/video:

- Uploads are **streamed to a temp file in chunks** — the server never holds
  the whole file in RAM, no matter the size.
- Downloads stream via `FileResponse`; temp files are deleted automatically
  after the response is sent.
- Blocking work (Whisper, moviepy/ffmpeg) runs in a worker thread
  (`asyncio.to_thread`), so `/health` stays responsive during transcription.
- Upload size is capped (`413` over the limit) and concurrent transcriptions
  are capped by a semaphore (Whisper OOMs easily under parallel load).

| Env var | Default | Meaning |
|---|---|---|
| `MAX_UPLOAD_BYTES` | `2147483648` (2 GiB) | max upload size, `413` if exceeded |
| `UPLOAD_CHUNK_BYTES` | `1048576` (1 MiB) | streaming chunk size |
| `TRANSCRIBE_WORKERS` | `2` | max parallel transcriptions |

```bash
MAX_UPLOAD_BYTES=5368709120 TRANSCRIBE_WORKERS=1 uv run transcript serve --port 8000
```

## Uninstallation

```bash
uv run pip uninstall multifunction-tool   # or: rm -rf .venv dist build
```
