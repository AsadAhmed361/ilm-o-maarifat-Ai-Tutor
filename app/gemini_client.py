"""
gemini_client.py

Provides a single, reused genai.Client instance across the whole app,
via FastAPI's dependency injection. @lru_cache ensures the client is
built ONCE (on first call), then the same object is returned on every
subsequent request -- no per-request client creation, no duplicate
API-key checks.
"""

import os
from functools import lru_cache
from google import genai


@lru_cache
def get_gemini_client() -> genai.Client:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY environment variable not set")
    return genai.Client(api_key=api_key)
