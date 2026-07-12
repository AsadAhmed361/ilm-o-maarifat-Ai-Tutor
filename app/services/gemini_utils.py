"""
gemini_utils.py

Shared retry wrapper for Gemini API calls. Used by both QuestionGenerator
and ReportGenerator so failure handling lives in ONE place, not duplicated.

Handles transient failures: network errors, rate limits (429), server
errors (5xx), timeouts. Does NOT retry on things that won't fix themselves
on retry (e.g. invalid API key, malformed request) -- those fail immediately.
"""

import time


def call_gemini_with_retry(api_call, max_retries: int = 3, base_delay: float = 1.0):
    """
    Wraps a Gemini API call (passed as a zero-arg callable) with retry +
    exponential backoff. Retries on any exception except auth-related ones
    that won't fix themselves.

    Usage:
        response = call_gemini_with_retry(
            lambda: client.models.generate_content(...)
        )
    """
    last_exception = None

    for attempt in range(1, max_retries + 1):
        try:
            return api_call()
        except Exception as e:
            last_exception = e
            error_str = str(e).lower()

            # Don't retry on auth/permission errors -- retrying won't help.
            if "api key" in error_str or "permission" in error_str or "unauthorized" in error_str:
                raise RuntimeError(f"Gemini API authentication failed: {e}") from e

            # Don't waste short retries on quota exhaustion -- the server
            # tells us to wait much longer (e.g. 59s) than our backoff
            # (max 4s), so retrying immediately will just fail again.
            if "resource_exhausted" in error_str or "quota" in error_str:
                raise RuntimeError(
                    f"Gemini API quota exceeded. Please wait a minute and try again, "
                    f"or check your plan at https://ai.google.dev/gemini-api/docs/rate-limits. Details: {e}"
                ) from e

            if attempt < max_retries:
                delay = base_delay * (2 ** (attempt - 1))  # 1s, 2s, 4s...
                print(f"Gemini call failed (attempt {attempt}/{max_retries}): {e}. Retrying in {delay}s...")
                time.sleep(delay)
            else:
                break

    raise RuntimeError(
        f"Gemini API call failed after {max_retries} attempts. Last error: {last_exception}"
    ) from last_exception
