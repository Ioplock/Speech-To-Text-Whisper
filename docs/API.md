# API Reference

> 🇷🇺 [Читать на русском](API.ru.md) · Machine-readable spec: [openapi.json](openapi.json)
> Interactive docs (when server runs): `http://127.0.0.1:8000/docs`

Five endpoints, no auth. Base URL below is the default local server.

## 0. Quickstart

```bash
uv run transcript serve --port 8000   # start; base URL = http://127.0.0.1:8000
```

```bash
BASE=http://127.0.0.1:8000

curl -s $BASE/health
# {"status":"ok"}

curl -s -X POST "$BASE/transcribe?lang=en&model=tiny" -F "file=@talk.mp3"
# {"text":"...","language":"en","segments":[...]}

curl -s -X POST $BASE/count-tokens \
  -H 'Content-Type: application/json' -d '{"model":"gpt-4o","text":"hello world"}'
# {"model":"gpt-4o","tokens":2}
```

Python (httpx):

```python
import httpx

BASE = "http://127.0.0.1:8000"

with open("talk.mp3", "rb") as f:
    r = httpx.post(
        f"{BASE}/transcribe",
        params={"lang": "en", "model": "tiny"},
        files={"file": ("talk.mp3", f, "audio/mpeg")},
        timeout=600,
    )
r.raise_for_status()
print(r.json()["text"])
```

## 1. Conventions

- **Errors** always look like `{"detail": "<message>"}` with a matching HTTP status.
- **Uploads** (`file`) are multipart form fields, streamed in chunks — files of any
  size are fine (see [limits](#4-limits--tuning)).
- **No auth.** Bind to `127.0.0.1` (default) for local-only access.

| Status | Meaning | When |
|---|---|---|
| `200` | OK | request succeeded (file downloads too) |
| `400` | Bad request | bad param, empty upload, video without audio |
| `404` | Not found | unknown path |
| `413` | Too large | upload over `MAX_UPLOAD_BYTES` |
| `422` | Unprocessable | required multipart `file` missing |
| `500` | Server error | whisper/ffmpeg failed on valid input |
| `501` | Not installed | `openai-whisper` / `moviepy` extra missing |

## 2. Endpoints

### `GET /health` — liveness check

```bash
curl -s http://127.0.0.1:8000/health
```

```json
{"status": "ok"}
```

Use it to wait for startup or as a load-balancer probe. Always fast, even mid-transcription.

---

### `GET /models` — available models & tasks

```bash
curl -s http://127.0.0.1:8000/models
```

```json
{"models": ["tiny", "base", "small", "medium", "large", "turbo"], "tasks": ["transcribe", "translate"]}
```

---

### `POST /transcribe` — speech to text

Requires the `whisper` extra, otherwise `501` with install instructions.

**Query params:**

| Param | Default | Allowed | Meaning |
|---|---|---|---|
| `lang` | `ru` | any language code (`en`, `ru`, …) | audio language (wrong code degrades quality, doesn't error) |
| `model` | `medium` | `tiny, base, small, medium, large, turbo` | whisper model; bigger = better + slower |
| `task` | `transcribe` | `transcribe, translate` | `translate` renders everything in English |
| `response_format` | `json` | `json, text` | `text` returns plain text (for piping) |

**Body:** multipart with one field `file` = the audio file.

```bash
# JSON response (default)
curl -s -X POST "http://127.0.0.1:8000/transcribe?lang=en&model=tiny" \
  -F "file=@talk.mp3"
```

```json
{
  "text": "hello, this is a test",
  "language": "en",
  "segments": [
    {"id": 0, "start": 0.0, "end": 2.5, "text": "hello, this is a test"}
  ]
}
```

```bash
# plain text response — pipe straight into a file or next tool
curl -s -X POST "http://127.0.0.1:8000/transcribe?lang=en&model=tiny&response_format=text" \
  -F "file=@talk.mp3" -o talk.txt
```

```python
import httpx

with open("talk.mp3", "rb") as f:
    r = httpx.post(
        "http://127.0.0.1:8000/transcribe",
        params={"lang": "en", "model": "tiny", "task": "transcribe"},
        files={"file": ("talk.mp3", f, "audio/mpeg")},
        timeout=600,  # transcription of long files takes minutes
    )
if r.status_code == 501:
    raise SystemExit("server lacks whisper extra: uv sync --extra whisper")
r.raise_for_status()
data = r.json()
print(data["text"], "| segments:", len(data["segments"]))
```

**Typical errors:**

```bash
curl -s -X POST "http://127.0.0.1:8000/transcribe?model=nope" -F "file=@talk.mp3"
# {"detail":"Unknown model 'nope'"}   (400)
```

Notes: first call with a new `model` downloads weights once (~75 MB–3 GB) and
is slow; models stay cached in RAM afterwards. At most `TRANSCRIBE_WORKERS`
transcriptions run at once (rest wait).

---

### `POST /extract-audio` — audio track out of video

Requires the `video` extra, otherwise `501`.

| Param | Default | Allowed |
|---|---|---|
| `format` | `wav` | `wav, mp3` |

**Body:** multipart, one field `file` = the video. **Response:** the audio file
as a download (`Content-Type: audio/wav` or `audio/mpeg`).

```bash
curl -s -X POST "http://127.0.0.1:8000/extract-audio?format=mp3" \
  -F "file=@clip.mp4" -o audio.mp3
```

```python
import httpx

with open("clip.mp4", "rb") as f:
    r = httpx.post(
        "http://127.0.0.1:8000/extract-audio",
        params={"format": "wav"},
        files={"file": ("clip.mp4", f, "video/mp4")},
        timeout=600,
    )
r.raise_for_status()
open("audio.wav", "wb").write(r.content)
```

Error if the video has no audio track: `400 {"detail":"Video file has no audio track: ..."}`.

---

### `POST /count-tokens` — token count

Works without any extras. Two interchangeable input styles.

**Option A — JSON:**

```bash
curl -s -X POST http://127.0.0.1:8000/count-tokens \
  -H 'Content-Type: application/json' \
  -d '{"model":"gpt-4o","text":"hello world"}'
# {"model":"gpt-4o","tokens":2}
```

```python
import httpx

r = httpx.post(
    "http://127.0.0.1:8000/count-tokens",
    json={"model": "gpt-4o", "text": open("doc.txt").read()},
    timeout=60,
)
r.raise_for_status()
print(r.json()["tokens"])
```

**Option B — multipart file** (same result, for piping files):

```bash
curl -s -X POST http://127.0.0.1:8000/count-tokens \
  -F "model=gpt-4o" -F "file=@doc.txt"
# {"model":"gpt-4o","tokens":2}
```

Unknown `model` names don't error — the server falls back to `cl100k_base`
counting (counts may differ from the real model).

## 3. Response schemas

```jsonc
// POST /transcribe (response_format=json)
{"text": "string", "language": "en | null", "segments": [{"id": 0, "start": 0.0, "end": 1.2, "text": "…"}]}

// POST /count-tokens
{"model": "gpt-4o", "tokens": 2}

// errors (any endpoint)
{"detail": "human-readable message"}
```

Full machine-readable spec for codegen/agents: [`openapi.json`](openapi.json)
(also served live at `/openapi.json`).

## 4. Limits & tuning

| Env var | Default | Meaning |
|---|---|---|
| `MAX_UPLOAD_BYTES` | `2147483648` (2 GiB) | uploads above → `413` |
| `UPLOAD_CHUNK_BYTES` | `1048576` (1 MiB) | streaming chunk size |
| `TRANSCRIBE_WORKERS` | `2` | max parallel transcriptions |

```bash
MAX_UPLOAD_BYTES=5368709120 TRANSCRIBE_WORKERS=1 uv run transcript serve --port 8000
```
