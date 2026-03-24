#!/usr/bin/env python3
"""Shared error classification for weibo skill scripts."""
import httpx


def classify_error(e: Exception) -> dict:
    """Return structured error dict with error_code and error message."""
    if isinstance(e, httpx.HTTPStatusError):
        status = e.response.status_code
        if status in (401, 403):
            return {"error": f"Authentication failed (HTTP {status}). Cookie may have expired.", "error_code": "auth_expired"}
        if status in (418, 429):
            return {"error": "Rate limit exceeded. Please wait and try again.", "error_code": "rate_limited"}
        return {"error": f"Weibo API returned HTTP {status}", "error_code": "api_error"}
    if isinstance(e, httpx.TimeoutException):
        return {"error": "Request timed out", "error_code": "network_timeout"}
    if isinstance(e, (httpx.ConnectError, ConnectionError, OSError)):
        return {"error": f"Network error: {type(e).__name__}", "error_code": "network_error"}
    return {"error": f"Unexpected error: {type(e).__name__}: {str(e)[:200]}", "error_code": "unknown_error"}


def classify_api_response(data: dict) -> dict | None:
    """Check Weibo API response for errors. Returns None if ok."""
    if data.get("ok") == 1:
        return None
    errno = data.get("errno")
    msg = data.get("msg", "Unknown Weibo API error")
    if errno == 20003:
        return {"error": f"Cookie expired (errno 20003): {msg}", "error_code": "auth_expired"}
    if errno == 20101:
        return {"error": f"User not found (errno 20101): {msg}", "error_code": "not_found"}
    if errno == 22009:
        return {"error": f"Content deleted (errno 22009): {msg}", "error_code": "deleted"}
    return {"error": msg, "error_code": "api_error"}
