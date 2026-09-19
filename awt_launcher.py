"""Console-script launcher with an environment-safe module name."""

import importlib.util
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    cli_path = Path(__file__).with_name("cli.py")
    spec = importlib.util.spec_from_file_location("awt_local_cli", cli_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load CLI: {cli_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.main(argv)
