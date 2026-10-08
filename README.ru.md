# Multifunction Tool

> 🇬🇧 [Read in English](README.md)

Три утилиты + локальный HTTP API-сервер:

- **Transcribe** — аудио → текст через Whisper.
- **Extract Audio** — извлечение аудиодорожки из видео.
- **Count Tokens** — подсчёт токенов через `tiktoken`.
- **Serve** — локальный REST API (FastAPI) для всего перечисленного.

## Установка через `uv`

Нужен [`uv`](https://docs.astral.sh/uv/) (есть в nix: `nix shell nixpkgs#uv`).
Версия Python зафиксирована в `.python-version` (3.12).

```bash
# лёгкая установка: CLI-справка, API-сервер, подсчёт токенов, тесты
# (без torch/whisper/moviepy -> быстро, подходит для ноутбука)
uv sync --group dev

# полная установка: + транскрибация и работа с видео (тяжёлая: torch, ffmpeg)
uv sync --group dev --extra whisper --extra video
# альтернативы: --extra all | системный ffmpeg: nix run nixpkgs#ffmpeg -- -version
```

Всё запускается через `uv run` (используется locked-окружение `.venv`, ничего
активировать не нужно):

```bash
uv run transcript --help
uv run pytest -q
```

## CLI

```bash
# Транскрибация (нужен --extra whisper)
uv run transcript transcribe my_audio.mp3 -o result.txt -l en -m small
uv run transcript transcribe my_audio.mp3 --task translate -l en -m turbo

# Извлечение аудио (нужен --extra video)
uv run transcript extract_audio my_video.mp4 -o extracted_audio.wav

# Подсчёт токенов (работает и на лёгкой установке)
uv run transcript count_tokens -m gpt-4o my_text.txt
uv run transcript count_tokens -m gpt-4o --text "hello world"

# Локальный сервер
uv run transcript serve --host 127.0.0.1 --port 8000
```

Коды выхода: `0` — ок, `2` — нет файла / неверное использование CLI,
`3` — нет опциональной зависимости или неверное значение, `1` — непредвиденная ошибка.

## Локальный API-сервер

> Полный справочник по запросам/ответам (curl + Python для каждого эндпоинта):
> [`docs/API.ru.md`](docs/API.ru.md) · машиночитаемый [`docs/openapi.json`](docs/openapi.json)

```bash
uv run transcript serve --port 8000
# документация: http://127.0.0.1:8000/docs
```

| Метод | Эндпоинт | Вход | Выход |
|---|---|---|---|
| GET | `/health` | — | `{"status":"ok"}` |
| GET | `/models` | — | модели whisper + задачи |
| POST | `/transcribe?lang=ru&model=medium&task=transcribe&response_format=json` | multipart `file` (аудио) | `{text, language, segments}` или plain text |
| POST | `/extract-audio?format=wav` | multipart `file` (видео) | скачивание аудиофайла |
| POST | `/count-tokens` | JSON `{model, text}` **или** multipart `{model, text?/file?}` | `{model, tokens}` |

Примеры:

```bash
curl -X POST "http://127.0.0.1:8000/transcribe?lang=en&model=tiny" \
  -F "file=@my_audio.mp3"

curl -X POST http://127.0.0.1:8000/count-tokens \
  -H "Content-Type: application/json" \
  -d '{"model":"gpt-4o","text":"hello world"}'

curl -X POST "http://127.0.0.1:8000/extract-audio?format=mp3" \
  -F "file=@my_video.mp4" -o audio.mp3
```

Заметки:

- Модели Whisper кэшируются в памяти после первой загрузки; первый вызов
  `/transcribe` скачивает веса (~75 МБ–3 ГБ в зависимости от модели).
- Без тяжёлых extras сервер всё равно запускается; `/transcribe` и
  `/extract-audio` отвечают `501` с инструкцией по установке, а не падают.
- `response_format=text` возвращает plain text (удобно для пайпов).

### Большие файлы и async

Все хендлеры `async` и рассчитаны на большое аудио/видео:

- Загрузки **стримятся во временный файл чанками** — сервер никогда не держит
  весь файл в RAM, каким бы большим он ни был.
- Скачивания стримятся через `FileResponse`; временные файлы удаляются
  автоматически после отправки ответа.
- Блокирующая работа (Whisper, moviepy/ffmpeg) выполняется в воркер-потоке
  (`asyncio.to_thread`), поэтому `/health` отвечает даже во время транскрибации.
- Размер загрузки ограничен (сверх лимита — `413`), а параллельные
  транскрибации ограничены семафором (Whisper легко съедает всю память при
  параллельной нагрузке).

| Переменная | По умолчанию | Смысл |
|---|---|---|
| `MAX_UPLOAD_BYTES` | `2147483648` (2 ГиБ) | макс. размер загрузки, сверх — `413` |
| `UPLOAD_CHUNK_BYTES` | `1048576` (1 МиБ) | размер чанка стриминга |
| `TRANSCRIBE_WORKERS` | `2` | макс. параллельных транскрибаций |

```bash
MAX_UPLOAD_BYTES=5368709120 TRANSCRIBE_WORKERS=1 uv run transcript serve --port 8000
```

## Удаление

```bash
uv run pip uninstall multifunction-tool   # или: rm -rf .venv dist build
```
