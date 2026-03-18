#!/usr/bin/env python3
"""Shared error classification for skill scripts."""
import httpx


def classify_error(e: Exception) -> dict:
    """Return structured error dict with error_code and error message."""
    if isinstance(e, RuntimeError) and "not authenticated" in str(e).lower():
        return {"error": str(e), "error_code": "auth_invalid"}
    if isinstance(e, httpx.HTTPStatusError):
        status = e.response.status_code
        if status in (401, 403):
            return {
                "error": f"Authentication failed (HTTP {status}). Token may have expired.",
                "error_code": "auth_expired",
            }
        if status == 429:
            return {"error": "Rate limit exceeded. Please wait and try again.", "error_code": "rate_limited"}
        return {"error": f"WeChat API returned HTTP {status}", "error_code": "api_error"}
    if isinstance(e, httpx.TimeoutException):
        return {"error": "Request timed out", "error_code": "network_timeout"}
    if isinstance(e, (httpx.ConnectError, ConnectionError, OSError)):
        return {"error": f"Network error: {e}", "error_code": "network_error"}
    return {"error": str(e), "error_code": "unknown_error"}
