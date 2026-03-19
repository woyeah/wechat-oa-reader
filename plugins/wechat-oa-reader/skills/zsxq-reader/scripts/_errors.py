#!/usr/bin/env python3
"""Shared error classification for zsxq skill scripts."""
import httpx


def classify_error(e: Exception) -> dict:
    """Return structured error dict with error_code and error message."""
    if isinstance(e, httpx.HTTPStatusError):
        status = e.response.status_code
        if status in (401, 403):
            return {
                "error": f"Authentication failed (HTTP {status}). Cookie may have expired.",
                "error_code": "auth_expired",
            }
        if status == 429:
            return {"error": "Rate limit exceeded. Please wait and try again.", "error_code": "rate_limited"}
        return {"error": f"zsxq API returned HTTP {status}", "error_code": "api_error"}
    if isinstance(e, httpx.TimeoutException):
        return {"error": "Request timed out", "error_code": "network_timeout"}
    if isinstance(e, (httpx.ConnectError, ConnectionError, OSError)):
        return {"error": f"Network error: {type(e).__name__}", "error_code": "network_error"}
    return {"error": f"Unexpected error: {type(e).__name__}: {str(e)[:200]}", "error_code": "unknown_error"}


def classify_api_response(data: dict) -> dict | None:
    """Check zsxq API response for errors. Returns None if succeeded."""
    if data.get("succeeded"):
        return None
    resp_data = data.get("resp_data", {})
    err_code = resp_data.get("err_code")
    err_msg = resp_data.get("err_msg", "Unknown API error")
    if err_code == 1059:
        return {"error": f"Rate limited by zsxq (code 1059): {err_msg}", "error_code": "rate_limited"}
    if err_code == 14210:
        return {"error": f"Membership expired (code 14210): {err_msg}", "error_code": "membership_expired"}
    return {"error": err_msg, "error_code": "api_error"}
