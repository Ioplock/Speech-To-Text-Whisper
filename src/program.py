"""Backward-compat shim: the old flat module was `src/program.py`.

New code lives in `multifunction_tool.{core,cli,server}`.
This keeps `import program` / `transcript` entry working.
"""

from multifunction_tool.cli import build_parser, main  # noqa: F401
from multifunction_tool.core import (  # noqa: F401
    VALID_TASKS,
    VALID_WHISPER_MODELS,
    count_tokens,
    extract_audio,
    transcribe_audio,
)

if __name__ == "__main__":
    raise SystemExit(main())
