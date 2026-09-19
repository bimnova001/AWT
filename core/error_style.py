"""User-safe error messages for terminal runtime output."""

import os
import sys


def public_error_message(error: object) -> str:
    """Hide provider internals unless explicit debug output is enabled."""

    text = str(error)
    lowered = text.lower()

    if "tokens per minute" in lowered or "rate_limit_exceeded" in lowered or "error code: 413" in lowered:
        message = "Provider token limit reached. Try a shorter task or retry later."
    elif "tool_use_failed" in lowered or "called a tool" in lowered:
        message = "The model requested an unsupported tool. The task was stopped safely."
    elif "timeout" in lowered or "timed out" in lowered:
        message = "The task timed out before completion."
    elif "authentication" in lowered or "api key" in lowered:
        message = "The provider rejected authentication. Check the configured API key."
    else:
        message = "The task could not be completed safely."

    if os.getenv("AWT_DEBUG"):
        print(f"[debug] {text}", file=sys.stderr)
    return message
