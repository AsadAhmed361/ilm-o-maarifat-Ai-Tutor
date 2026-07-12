"""
gemini_client.py

Provides a single, reused genai.Client instance across the whole app,
via FastAPI's dependency injection. Also centralizes the model name --
change it here once, every service picks it up, instead of hardcoded
strings scattered across 5+ files.
"""

import os
from functools import lru_cache
from google import genai

MODEL_NAME = os.environ.get("GEMINI_MODEL_NAME", "gemini-2.5-flash")


@lru_cache
def get_gemini_client() -> genai.Client:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY environment variable not set")
    return genai.Client(api_key=api_key)