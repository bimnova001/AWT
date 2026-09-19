import os
from dotenv import load_dotenv

load_dotenv()


def get_groq_keys() -> list[str]:

    keys = []

    for i in range(1, 10):

        key = os.getenv(f"GROQ_API_KEY_{i}")

        if key:
            keys.append(key)

    return keys


GROQ_KEYS = get_groq_keys()

GROQ_MODEL = os.getenv(
    "GROQ_MODEL",
    "openai/gpt-oss-20b"
)

MAX_TASKS = int(
    os.getenv("MAX_TASKS", "30")
)

MAX_DEPTH = int(
    os.getenv("MAX_DEPTH", "4")
)

MAX_REVIEW_ROUNDS = int(
    os.getenv("MAX_REVIEW_ROUNDS", "2")
)

MAX_CONTEXT_CHARS = int(
    os.getenv("MAX_CONTEXT_CHARS", "12000")
)

MAX_RESULT_CHARS = int(
    os.getenv("MAX_RESULT_CHARS", "12000")
)

MAX_OUTPUT_TOKENS = int(
    os.getenv("MAX_OUTPUT_TOKENS", "1800")
)