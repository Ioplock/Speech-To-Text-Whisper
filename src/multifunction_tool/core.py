"""Core logic: transcription, audio extraction, token counting.

Heavy dependencies (whisper/torch, moviepy) are imported lazily so that
the package, CLI help and API server stay usable on machines without them
(e.g. a laptop used only for tests). Missing extras surface as a clear
RuntimeError (CLI -> exit code 3, API -> HTTP 501).
"""

from __future__ import annotations

import os
import warnings

VALID_WHISPER_MODELS = ("tiny", "base", "small", "medium", "large", "turbo")
VALID_TASKS = ("transcribe", "translate")

_model_cache: dict[str, object] = {}


def _ensure_parent_dir(path: str) -> None:
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)


def load_whisper_model(name: str):
    """Load (and cache) a Whisper model. Raises RuntimeError if extra missing."""
    if name not in VALID_WHISPER_MODELS:
        raise ValueError(
            f"Unknown Whisper model {name!r}. Valid options: {', '.join(VALID_WHISPER_MODELS)}"
        )
    if name in _model_cache:
        return _model_cache[name]
    try:
        import whisper
    except ImportError as exc:
        raise RuntimeError(
            "Whisper is not installed. Install the extra with: "
            "`uv sync --extra whisper` or `uv pip install 'openai-whisper'`."
        ) from exc
    model = whisper.load_model(name)
    _model_cache[name] = model
    return model


def transcribe_audio(
    input_file: str,
    output_file: str | None = None,
    lang: str = "ru",
    model_name: str = "medium",
    task: str = "transcribe",
) -> dict:
    """Transcribe an audio file with Whisper.

    Returns the raw Whisper result dict (keys: text, segments, language, ...).
    If output_file is given, the plain text is written there (parent dirs created).
    """
    if not os.path.isfile(input_file):
        raise FileNotFoundError(f"Audio file not found: {input_file!r}")
    if task not in VALID_TASKS:
        raise ValueError(f"Unknown task {task!r}. Valid: {', '.join(VALID_TASKS)}")

    model = load_whisper_model(model_name)

    # NOTE: Whisper does the whole transcription in one blocking call.
    # The old code showed a tqdm bar *after* transcription finished, which was
    # misleading. We keep an honest single-step progress indicator instead.
    print(f"Transcribing {input_file!r} (model={model_name}, lang={lang}, task={task}) ...")
    result = model.transcribe(input_file, language=lang, task=task, verbose=False)

    text = result.get("text", "") if isinstance(result, dict) else ""
    segments = result.get("segments", []) if isinstance(result, dict) else []
    print(f"Done: {len(segments)} segments.")

    if output_file:
        _ensure_parent_dir(output_file)
        with open(output_file, "w", encoding="utf-8") as fh:
            fh.write(text)
        print(f"Transcription saved to {output_file!r}")

    return result if isinstance(result, dict) else {"text": text, "segments": []}


def extract_audio(video_file: str, audio_output: str) -> str:
    """Extract the audio track from a video file.

    Returns the output path. Raises ValueError if the video has no audio track.
    """
    if not os.path.isfile(video_file):
        raise FileNotFoundError(f"Video file not found: {video_file!r}")

    try:
        try:
            # moviepy >= 2.0 (the `editor` submodule was removed)
            from moviepy import VideoFileClip
        except ImportError:
            # moviepy 1.x fallback
            from moviepy.editor import VideoFileClip  # type: ignore[no-redef]
    except ImportError as exc:
        raise RuntimeError(
            "moviepy is not installed. Install the extra with: "
            "`uv sync --extra video` or `uv pip install 'moviepy>=2.0' imageio-ffmpeg`."
        ) from exc

    _ensure_parent_dir(audio_output)
    clip = VideoFileClip(video_file)
    try:
        if clip.audio is None:
            raise ValueError(f"Video file has no audio track: {video_file!r}")
        # Suppress moviepy's own progress bar - caller owns UX.
        clip.audio.write_audiofile(audio_output, logger=None)
    finally:
        clip.close()
    return audio_output


def _encoding_for_model(model_name: str):
    try:
        import tiktoken
    except ImportError as exc:
        raise RuntimeError(
            "tiktoken is not installed. Run `uv sync` to install base dependencies."
        ) from exc
    try:
        return tiktoken.encoding_for_model(model_name)
    except KeyError:
        warnings.warn(
            f"Unknown model {model_name!r} for tiktoken, falling back to 'cl100k_base'. "
            "Token counts may differ from the real model.",
            UserWarning,
            stacklevel=3,
        )
        return tiktoken.get_encoding("cl100k_base")


def count_tokens(model_name: str, file_path: str | None = None, text: str | None = None) -> int:
    """Count tokens for a model. Provide either file_path or text."""
    if file_path is None and text is None:
        raise ValueError("Provide either file_path or text.")
    if file_path is not None:
        if not os.path.isfile(file_path):
            raise FileNotFoundError(f"Input file not found: {file_path!r}")
        with open(file_path, encoding="utf-8") as fh:
            text = fh.read()
    assert text is not None
    encoding = _encoding_for_model(model_name)
    return len(encoding.encode(text))
