"""Command-line interface: transcript {transcribe, extract_audio, count_tokens, serve}."""

from __future__ import annotations

import argparse
import sys

from multifunction_tool.core import VALID_TASKS, VALID_WHISPER_MODELS


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="transcript",
        description="Transcription (Whisper), audio extraction, token counting, local API server.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_tr = sub.add_parser("transcribe", help="Transcribe an audio file.")
    p_tr.add_argument("audio_file", help="Path to the audio file for transcription")
    p_tr.add_argument("-o", "--output", default="transcription.txt", help="Output text file")
    p_tr.add_argument("-l", "--lang", default="ru", help="Audio language code (default: ru)")
    p_tr.add_argument(
        "-m", "--model", default="medium", choices=VALID_WHISPER_MODELS, help="Whisper model"
    )
    p_tr.add_argument(
        "--task", default="transcribe", choices=VALID_TASKS, help="transcribe | translate"
    )

    p_ex = sub.add_parser("extract_audio", help="Extract audio from a video file.")
    p_ex.add_argument("video_file", help="Path to the input video file")
    p_ex.add_argument("-o", "--output", default="output.wav", help="Output audio file")

    p_tok = sub.add_parser("count_tokens", help="Count tokens in a text file or literal text.")
    p_tok.add_argument("-m", "--model", required=True, help="Model name (e.g. gpt-4o)")
    p_tok.add_argument("input_file", nargs="?", default=None, help="Path to the input text file")
    p_tok.add_argument("--text", default=None, help="Literal text instead of a file")

    p_srv = sub.add_parser("serve", help="Run a local HTTP API server.")
    p_srv.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    p_srv.add_argument("--port", type=int, default=8000, help="Bind port (default: 8000)")
    p_srv.add_argument("--reload", action="store_true", help="Auto-reload on code changes")
    return parser


def _cmd_transcribe(args: argparse.Namespace) -> int:
    from multifunction_tool.core import transcribe_audio

    try:
        transcribe_audio(args.audio_file, args.output, args.lang, args.model, args.task)
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    except (ValueError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 3
    except Exception as exc:  # noqa: BLE001
        print(f"Transcription failed: {exc}", file=sys.stderr)
        return 1
    return 0


def _cmd_extract(args: argparse.Namespace) -> int:
    from multifunction_tool.core import extract_audio

    try:
        extract_audio(args.video_file, args.output)
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    except (ValueError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 3
    except Exception as exc:  # noqa: BLE001
        print(f"Audio extraction failed: {exc}", file=sys.stderr)
        return 1
    print(f"Audio saved to {args.output!r}")
    return 0


def _cmd_tokens(args: argparse.Namespace) -> int:
    from multifunction_tool.core import count_tokens

    if args.input_file is None and args.text is None:
        print("Error: provide input_file or --text", file=sys.stderr)
        return 2
    try:
        n = count_tokens(args.model, file_path=args.input_file, text=args.text)
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    except (ValueError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 3
    except Exception as exc:  # noqa: BLE001
        print(f"Token counting failed: {exc}", file=sys.stderr)
        return 1
    src = args.input_file if args.input_file else "<text>"
    print(f'Token count for model "{args.model}" in {src}: {n}')
    return 0


def _cmd_serve(args: argparse.Namespace) -> int:
    try:
        import uvicorn
    except ImportError:
        print("Error: uvicorn is not installed. Run `uv sync` first.", file=sys.stderr)
        return 3
    print(f"Serving API on http://{args.host}:{args.port}  (docs: /docs)")
    uvicorn.run("multifunction_tool.server:app", host=args.host, port=args.port, reload=args.reload)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "transcribe":
        return _cmd_transcribe(args)
    if args.command == "extract_audio":
        return _cmd_extract(args)
    if args.command == "count_tokens":
        return _cmd_tokens(args)
    if args.command == "serve":
        return _cmd_serve(args)
    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
