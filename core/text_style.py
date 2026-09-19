"""Small terminal styling helpers for readable runtime events."""

import os
import sys


RESET = "\033[0m"
BOLD = "\033[1m"
COLORS = {
    "blue": "\033[94m",
    "cyan": "\033[96m",
    "green": "\033[92m",
    "magenta": "\033[95m",
    "red": "\033[91m",
    "yellow": "\033[93m",
}


def style(text: object, color: str | None = None, *, bold: bool = False) -> str:
    value = str(text)
    if os.getenv("NO_COLOR") or not sys.stdout.isatty():
        return value
    prefix = COLORS.get(color, "") + (BOLD if bold else "")
    return f"{prefix}{value}{RESET}" if prefix else value


def event(label: str, message: str, color: str = "cyan") -> str:
    return f"{style(f'[{label}]', color, bold=True)} {message}"


def block(title: str, content: object, color: str = "green") -> str:
    line = "=" * 68
    return "\n".join(
        (
            style(line, color),
            style(title, color, bold=True),
            style(line, color),
            str(content),
            style(line, color),
        )
    )
