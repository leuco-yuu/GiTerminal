from __future__ import annotations

import locale
import os
import subprocess

def decode_command_output(data: bytes | str | None) -> str:
    """Decode subprocess output without corrupting Windows GBK/CP936 text.

    The app stores and renders Python strings internally. Subprocess output may
    be UTF-8, the active locale encoding, or GBK/CP936 on Chinese Windows even
    after requesting UTF-8 from the shell. Try strict UTF-8 first, then common
    local encodings, and only replace undecodable bytes as the final fallback.
    """
    if data is None:
        return ""
    if isinstance(data, str):
        return data
    encodings: list[str] = ["utf-8", "utf-8-sig"]
    preferred = locale.getpreferredencoding(False)
    for enc in (preferred, "gb18030", "gbk", "cp936", "mbcs" if os.name == "nt" else ""):
        if enc and enc.lower() not in {e.lower() for e in encodings}:
            encodings.append(enc)
    for enc in encodings:
        try:
            return data.decode(enc)
        except (LookupError, UnicodeDecodeError):
            continue
    return data.decode("utf-8", errors="replace")


def utf8_subprocess_env() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["LESSCHARSET"] = "utf-8"
    env.setdefault("GIT_TERMINAL_PROMPT", "0")
    if os.name == "nt":
        env.setdefault("PYTHONUTF8", "1")
    else:
        env["LC_ALL"] = env.get("LC_ALL", "C.UTF-8")
        env["LANG"] = env.get("LANG", "C.UTF-8")
    return env


def completed_process_text(proc: subprocess.CompletedProcess) -> tuple[str, str]:
    return decode_command_output(proc.stdout), decode_command_output(proc.stderr)


def timeout_output_text(exc: subprocess.TimeoutExpired) -> tuple[str, str]:
    return decode_command_output(exc.stdout), decode_command_output(exc.stderr)
