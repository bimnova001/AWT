"""Compatibility entry point for ``python main.py``."""

from cli import main


if __name__ == "__main__":
    raise SystemExit(main(["tui"]))
