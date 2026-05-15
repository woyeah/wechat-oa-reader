#!/usr/bin/env python3
"""Shared error classification for cninfo skill scripts."""
import httpx


def classify_error(e: Exception) -> dict:
    """Return a structured error dict with error_code and a human message."""
    if isinstance(e, httpx.HTTPStatusError):
        status = e.response.status_code
        if status in (403, 451):
            return {
                "error": f"Cninfo blocked the request (HTTP {status}). Try again later or change User-Agent.",
                "error_code": "blocked",
            }
        if status == 404:
            return {"error": "Resource not found (HTTP 404).", "error_code": "not_found"}
        if status == 429:
            return {"error": "Rate limit hit (HTTP 429). Slow down.", "error_code": "rate_limited"}
        return {"error": f"Cninfo returned HTTP {status}", "error_code": "api_error"}
    if isinstance(e, httpx.TimeoutException):
        return {"error": "Request timed out", "error_code": "network_timeout"}
    if isinstance(e, (httpx.ConnectError, ConnectionError, OSError)):
        return {"error": f"Network error: {type(e).__name__}", "error_code": "network_error"}
    if isinstance(e, ValueError):
        return {"error": str(e), "error_code": "invalid_argument"}
    return {"error": f"Unexpected error: {type(e).__name__}: {str(e)[:200]}", "error_code": "unknown_error"}
