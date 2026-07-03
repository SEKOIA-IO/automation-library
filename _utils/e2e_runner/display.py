from __future__ import annotations
import sys


_COLOURS = {
    "reset":   "\033[0m",
    "bold":    "\033[1m",
    "blue":    "\033[34m",
    "cyan":    "\033[36m",
    "green":   "\033[32m",
    "yellow":  "\033[33m",
    "red":     "\033[31m",
    "grey":    "\033[90m",
    "magenta": "\033[35m",
}


def colorize(text: str, *styles: str) -> str:
    if not sys.stdout.isatty():
        return text
    codes = "".join(_COLOURS.get(style, "") for style in styles)
    return f"{codes}{text}{_COLOURS['reset']}"


def _banner(title: str) -> None:
    line = "─" * 60
    print(colorize(line, "blue"))
    print(colorize(f"  {title}", "bold", "blue"))
    print(colorize(line, "blue"))
