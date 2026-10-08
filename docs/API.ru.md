# API-справочник

> 🇬🇧 [Read in English](API.md) · Машиночитаемая спека: [openapi.json](openapi.json)
> Интерактивная документация (когда сервер запущен): `http://127.0.0.1:8000/docs`

Всего пять эндпоинтов, авторизации нет. Base URL ниже — локальный сервер по умолчанию.

## 0. Быстрый старт

```bash
uv run transcript serve --port 8000   # запуск; base URL = http://127.0.0.1:8000
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

## 1. Соглашения

- **Ошибки** всегда вида `{"detail": "<сообщение>"}` с соответствующим HTTP-статусом.
- **Загрузки** (`file`) — multipart-поля, стримятся чанками: размер файлов не важен
  (см. [лимиты](#4-лимиты--настройка)).
- **Авторизации нет.** Для локального доступа бинди на `127.0.0.1` (по умолчанию).

| Статус | Смысл | Когда |
|---|---|---|
| `200` | OK | запрос успешен (и скачивание файлов тоже) |
| `400` | Плохой запрос | неверный параметр, пустая загрузка, видео без аудио |
| `404` | Не найдено | неизвестный путь |
| `413` | Слишком большой | загрузка больше `MAX_UPLOAD_BYTES` |
| `422` | Необработаемо | отсутствует обязательное поле `file` |
| `500` | Ошибка сервера | whisper/ffmpeg упал на корректном входе |
| `501` | Не установлено | нет extra `openai-whisper` / `moviepy` |

## 2. Эндпоинты

### `GET /health` — проверка живости

```bash
curl -s http://127.0.0.1:8000/health
```

```json
{"status": "ok"}
```

Используй для ожидания старта или как пробу для балансировщика. Отвечает быстро всегда, даже посреди транскрибации.

---

### `GET /models` — доступные модели и задачи

```bash
curl -s http://127.0.0.1:8000/models
```

```json
{"models": ["tiny", "base", "small", "medium", "large", "turbo"], "tasks": ["transcribe", "translate"]}
```

---

### `POST /transcribe` — речь в текст

Требует extra `whisper`, иначе `501` с инструкцией по установке.

**Query-параметры:**

| Параметр | По умолч. | Допустимо | Смысл |
|---|---|---|---|
| `lang` | `ru` | любой код языка (`en`, `ru`, …) | язык аудио (неверный код ухудшает качество, но не ошибка) |
| `model` | `medium` | `tiny, base, small, medium, large, turbo` | модель whisper; больше = лучше + медленнее |
| `task` | `transcribe` | `transcribe, translate` | `translate` пересказывает всё по-английски |
| `response_format` | `json` | `json, text` | `text` отдаёт plain text (для пайпов) |

**Тело:** multipart с одним полем `file` = аудиофайл.

```bash
# JSON-ответ (по умолчанию)
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
# plain text — сразу в файл или следующей утилите
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
        timeout=600,  # длинные файлы распознаются минутами
    )
if r.status_code == 501:
    raise SystemExit("на сервере нет whisper extra: uv sync --extra whisper")
r.raise_for_status()
data = r.json()
print(data["text"], "| сегментов:", len(data["segments"]))
```

**Типичные ошибки:**

```bash
curl -s -X POST "http://127.0.0.1:8000/transcribe?model=nope" -F "file=@talk.mp3"
# {"detail":"Unknown model 'nope'"}   (400)
```

Заметки: первый вызов с новой `model` один раз скачивает веса (~75 МБ–3 ГБ) и
идёт долго; дальше модели лежат в RAM. Одновременно идут не более
`TRANSCRIBE_WORKERS` транскрибаций (остальные ждут).

---

### `POST /extract-audio` — аудио из видео

Требует extra `video`, иначе `501`.

| Параметр | По умолч. | Допустимо |
|---|---|---|
| `format` | `wav` | `wav, mp3` |

**Тело:** multipart, одно поле `file` = видео. **Ответ:** аудиофайл скачиванием
(`Content-Type: audio/wav` или `audio/mpeg`).

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

Если в видео нет аудиодорожки: `400 {"detail":"Video file has no audio track: ..."}`.

---

### `POST /count-tokens` — подсчёт токенов

Работает без extras. Два взаимозаменяемых способа ввода.

**Вариант A — JSON:**

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

**Вариант B — multipart-файл** (тот же результат, удобно для пайпов):

```bash
curl -s -X POST http://127.0.0.1:8000/count-tokens \
  -F "model=gpt-4o" -F "file=@doc.txt"
# {"model":"gpt-4o","tokens":2}
```

Неизвестные имена `model` — не ошибка: сервер молча считает по `cl100k_base`
(цифры могут отличаться от реальной модели).

## 3. Схемы ответов

```jsonc
// POST /transcribe (response_format=json)
{"text": "string", "language": "en | null", "segments": [{"id": 0, "start": 0.0, "end": 1.2, "text": "…"}]}

// POST /count-tokens
{"model": "gpt-4o", "tokens": 2}

// ошибки (любой эндпоинт)
{"detail": "сообщение человеческим языком"}
```

Полная машиночитаемая спека для кодогенерации/агентов: [`openapi.json`](openapi.json)
(также отдаётся живьём на `/openapi.json`).

## 4. Лимиты и настройка

| Переменная | По умолчанию | Смысл |
|---|---|---|
| `MAX_UPLOAD_BYTES` | `2147483648` (2 ГиБ) | загрузки больше → `413` |
| `UPLOAD_CHUNK_BYTES` | `1048576` (1 МиБ) | размер чанка стриминга |
| `TRANSCRIBE_WORKERS` | `2` | макс. параллельных транскрибаций |

```bash
MAX_UPLOAD_BYTES=5368709120 TRANSCRIBE_WORKERS=1 uv run transcript serve --port 8000
```
