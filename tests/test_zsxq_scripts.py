# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open
from uuid import uuid4

import httpx
import pytest


@pytest.fixture
def tmp_path() -> Path:
    root = Path.cwd() / "test_tmp"
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"case-{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def _load_script_module(script_name: str):
    """Load a zsxq script module by name (without .py extension)."""
    script_path = Path(__file__).resolve().parents[1] / "plugins" / "wechat-oa-reader" / "skills" / "zsxq-reader" / "scripts" / f"{script_name}.py"
    module_name = f"test_zsxq_{script_name}_{uuid4().hex}"
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _json_out(capsys) -> dict:
    return json.loads(capsys.readouterr().out.strip().splitlines()[-1])


def _mk_response(payload: dict) -> MagicMock:
    resp = MagicMock()
    resp.json.return_value = payload
    resp.raise_for_status = MagicMock()
    return resp


def _mk_http_status_error(code: int) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", "https://api.zsxq.com/v2/test")
    response = httpx.Response(code, request=request)
    return httpx.HTTPStatusError("boom", request=request, response=response)


def _query_contains(call, key: str, value: str) -> bool:
    args, kwargs = call
    url = args[0] if args else kwargs.get("url", "")
    if f"{key}={value}" in str(url):
        return True
    params = kwargs.get("params")
    if isinstance(params, dict):
        return str(params.get(key)) == value
    return False


# _errors.py tests

def test_classify_error_http_401() -> None:
    module = _load_script_module("_errors")
    out = module.classify_error(_mk_http_status_error(401))
    assert out["error_code"] == "auth_expired"


def test_classify_error_http_429() -> None:
    module = _load_script_module("_errors")
    out = module.classify_error(_mk_http_status_error(429))
    assert out["error_code"] == "rate_limited"


def test_classify_error_timeout() -> None:
    module = _load_script_module("_errors")
    out = module.classify_error(httpx.TimeoutException("timeout"))
    assert out["error_code"] == "network_timeout"


def test_classify_error_network() -> None:
    module = _load_script_module("_errors")
    out = module.classify_error(httpx.ConnectError("connect", request=httpx.Request("GET", "https://api.zsxq.com")))
    assert out["error_code"] == "network_error"


def test_classify_api_response_success() -> None:
    module = _load_script_module("_errors")
    assert module.classify_api_response({"succeeded": True}) is None


def test_classify_api_response_rate_limited() -> None:
    module = _load_script_module("_errors")
    out = module.classify_api_response({"succeeded": False, "resp_data": {"err_code": 1059, "err_msg": "too fast"}})
    assert out["error_code"] == "rate_limited"


def test_classify_api_response_membership_expired() -> None:
    module = _load_script_module("_errors")
    out = module.classify_api_response({"succeeded": False, "resp_data": {"err_code": 14210, "err_msg": "expired"}})
    assert out["error_code"] == "membership_expired"


# check_auth.py tests

def test_check_auth_missing_config(capsys, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_script_module("check_auth")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("ZSXQ_COOKIE", raising=False)

    try:
        module.main([])
    except SystemExit as exc:
        assert exc.code == 1

    out = _json_out(capsys)
    assert out["status"] == "missing"


def test_check_auth_valid(capsys, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_script_module("check_auth")
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text('ZSXQ_COOKIE="zsxq_access_token=test-cookie"', encoding="utf-8")
    mock_resp = _mk_response({"succeeded": True, "resp_data": {"user": {"name": "TestUser"}}})

    with patch.object(module.httpx, "get", return_value=mock_resp):
        module.main([])

    out = _json_out(capsys)
    assert out["status"] == "valid"
    assert out["user_name"] == "TestUser"


def test_check_auth_save_mode(capsys, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_script_module("check_auth")
    monkeypatch.chdir(tmp_path)
    mock_resp = _mk_response({"succeeded": True, "resp_data": {"user": {"name": "SavedUser"}}})

    with patch.object(module.httpx, "get", return_value=mock_resp):
        module.main(["--save", "--cookie", "zsxq_access_token=saved-cookie"])

    env_file = tmp_path / ".env"
    assert env_file.exists()
    env_content = env_file.read_text(encoding="utf-8")
    assert "ZSXQ_COOKIE" in env_content
    assert "saved-cookie" in env_content

    out = _json_out(capsys)
    assert out["status"] == "valid"


def test_check_auth_from_env(capsys, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_script_module("check_auth")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ZSXQ_COOKIE", "zsxq_access_token=env-cookie")
    mock_resp = _mk_response({"succeeded": True, "resp_data": {"user": {"name": "EnvUser"}}})

    with patch.object(module.httpx, "get", return_value=mock_resp) as mock_get:
        module.main([])

    args, kwargs = mock_get.call_args
    assert "env-cookie" in json.dumps({"args": args, "kwargs": kwargs}, ensure_ascii=False, default=str)
    out = _json_out(capsys)
    assert out["status"] == "valid"


# list_topics.py tests

def test_list_topics_basic(capsys, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_script_module("list_topics")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ZSXQ_COOKIE", "zsxq_access_token=test-cookie")

    payload = {
        "succeeded": True,
        "resp_data": {
            "topics": [
                {
                    "topic_id": 1,
                    "create_time": "2026-01-01T10:00:00+08:00",
                    "talk": {"text": "First topic text", "owner": {"name": "Alice"}},
                },
                {
                    "topic_id": 2,
                    "create_time": "2026-01-01T09:00:00+08:00",
                    "talk": {"text": "Second topic text", "owner": {"name": "Bob"}},
                },
                {
                    "topic_id": 3,
                    "create_time": "2026-01-01T08:00:00+08:00",
                    "question": {"text": "Q", "owner": {"name": "Carol"}},
                    "answer": {"text": "A"},
                },
            ],
            "has_more": False,
        },
    }

    with patch.object(module.httpx, "get", return_value=_mk_response(payload)):
        module.main(["123456"])

    out = _json_out(capsys)
    assert out["group_id"] == "123456"
    assert out["count"] == 3
    assert out["has_more"] is False
    assert len(out["topics"]) == 3
    assert all("preview" in t for t in out["topics"])


def test_list_topics_digests_scope(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_script_module("list_topics")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ZSXQ_COOKIE", "zsxq_access_token=test-cookie")

    with patch.object(module.httpx, "get", return_value=_mk_response({"succeeded": True, "resp_data": {"topics": [], "has_more": False}})) as mock_get:
        module.main(["123456", "--scope", "digests"])

    assert _query_contains(mock_get.call_args, "scope", "digests")


def test_list_topics_pagination(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_script_module("list_topics")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ZSXQ_COOKIE", "zsxq_access_token=test-cookie")

    with patch.object(module.httpx, "get", return_value=_mk_response({"succeeded": True, "resp_data": {"topics": [], "has_more": False}})) as mock_get:
        module.main(["123456", "--before", "2026-01-01T00:00:00+08:00"])

    assert _query_contains(mock_get.call_args, "end_time", "2026-01-01T00:00:00+08:00")


# fetch_topic.py tests

def test_fetch_topic_text_format(capsys, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_script_module("fetch_topic")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ZSXQ_COOKIE", "zsxq_access_token=test-cookie")

    topic_payload = {
        "succeeded": True,
        "resp_data": {
            "topic": {
                "topic_id": 777,
                "create_time": "2026-01-01T10:00:00+08:00",
                "talk": {
                    "owner": {"name": "AuthorA"},
                    "text": "Body content here.",
                    "images": [{"large": {"url": "https://img.example/a.jpg"}}],
                    "files": [{"name": "doc.pdf", "download_url": "https://file.example/doc.pdf"}],
                },
            }
        },
    }
    comments_payload = {
        "succeeded": True,
        "resp_data": {
            "comments": [
                {"owner": {"name": "User1"}, "text": "Nice post"},
                {"owner": {"name": "User2"}, "text": "Thanks"},
            ]
        },
    }

    with patch.object(module.httpx, "get", side_effect=[_mk_response(topic_payload), _mk_response(comments_payload)]):
        module.main(["777"])

    out = capsys.readouterr().out
    assert "#" in out
    assert "AuthorA" in out
    assert "Body content here." in out
    assert "Comments" in out
    assert "Nice post" in out


def test_fetch_topic_json_format(capsys, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_script_module("fetch_topic")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ZSXQ_COOKIE", "zsxq_access_token=test-cookie")

    topic_payload = {"succeeded": True, "resp_data": {"topic": {"topic_id": 888, "talk": {"text": "json body"}}}}
    comments_payload = {"succeeded": True, "resp_data": {"comments": [{"text": "c1"}]}}

    with patch.object(module.httpx, "get", side_effect=[_mk_response(topic_payload), _mk_response(comments_payload)]):
        module.main(["888", "--format", "json"])

    out = _json_out(capsys)
    assert "topic" in out
    assert "comments" in out


def test_fetch_topic_qa_type(capsys, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_script_module("fetch_topic")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ZSXQ_COOKIE", "zsxq_access_token=test-cookie")

    topic_payload = {
        "succeeded": True,
        "resp_data": {
            "topic": {
                "topic_id": 999,
                "question": {"owner": {"name": "AskUser"}, "text": "What is X?"},
                "answer": {"owner": {"name": "AnswerUser"}, "text": "X is Y."},
            }
        },
    }
    comments_payload = {"succeeded": True, "resp_data": {"comments": []}}

    with patch.object(module.httpx, "get", side_effect=[_mk_response(topic_payload), _mk_response(comments_payload)]):
        module.main(["999"])

    out = capsys.readouterr().out
    assert "What is X?" in out
    assert "X is Y." in out


# download_file.py tests

def test_download_single_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_script_module("download_file")
    monkeypatch.chdir(tmp_path)

    out_file = tmp_path / "single.bin"
    stream_resp = MagicMock()
    stream_resp.raise_for_status = MagicMock()
    stream_resp.iter_bytes.return_value = [b"abc", b"123"]
    stream_cm = MagicMock()
    stream_cm.__enter__.return_value = stream_resp
    stream_cm.__exit__.return_value = None

    with patch.object(module.httpx, "stream", return_value=stream_cm):
        module.main(["https://files.example/single.bin", "-o", str(out_file)])

    assert out_file.exists()
    assert out_file.read_bytes() == b"abc123"


def test_download_from_topic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_script_module("download_file")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ZSXQ_COOKIE", "zsxq_access_token=test-cookie")

    topic_payload = {
        "succeeded": True,
        "resp_data": {
            "topic": {
                "topic_id": 123,
                "talk": {
                    "files": [
                        {"name": "a.txt", "download_url": "https://files.example/a.txt"},
                        {"name": "b.txt", "download_url": "https://files.example/b.txt"},
                    ]
                },
            }
        },
    }

    file_streams = []
    for chunk in (b"A", b"B"):
        stream_resp = MagicMock()
        stream_resp.raise_for_status = MagicMock()
        stream_resp.iter_bytes.return_value = [chunk]
        stream_cm = MagicMock()
        stream_cm.__enter__.return_value = stream_resp
        stream_cm.__exit__.return_value = None
        file_streams.append(stream_cm)

    with patch.object(module.httpx, "get", return_value=_mk_response(topic_payload)), patch.object(
        module.httpx, "stream", side_effect=file_streams
    ):
        module.main(["--topic-id", "123"])

    assert (tmp_path / "a.txt").exists()
    assert (tmp_path / "b.txt").exists()
    assert (tmp_path / "a.txt").read_bytes() == b"A"
    assert (tmp_path / "b.txt").read_bytes() == b"B"


# list_groups.py tests

def test_list_groups_basic(capsys, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_script_module("list_groups")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ZSXQ_COOKIE", "zsxq_access_token=test-cookie")

    payload = {
        "succeeded": True,
        "resp_data": {
            "groups": [
                {
                    "group_id": 111,
                    "name": "Test Group 1",
                    "type": "pay",
                    "owner": {"name": "Owner1"},
                    "statistics": {"members_count": 100, "topics_count": 50},
                },
                {
                    "group_id": 222,
                    "name": "Test Group 2",
                    "type": "free",
                    "owner": {"name": "Owner2"},
                    "statistics": {"members_count": 200, "topics_count": 80},
                },
            ]
        },
    }

    with patch.object(module.httpx, "get", return_value=_mk_response(payload)):
        module.main([])

    out = _json_out(capsys)
    assert out["count"] == 2
    assert len(out["groups"]) == 2
    assert out["groups"][0]["name"] == "Test Group 1"
    assert out["groups"][0]["group_id"] == 111
    assert out["groups"][1]["owner"] == "Owner2"


def test_download_file_path_traversal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_script_module("download_file")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ZSXQ_COOKIE", "zsxq_access_token=test-cookie")

    topic_payload = {
        "succeeded": True,
        "resp_data": {
            "topic": {
                "topic_id": 999,
                "talk": {
                    "files": [
                        {"name": "../../../etc/malicious.txt", "download_url": "https://files.example/a.txt"},
                    ]
                },
            }
        },
    }

    stream_resp = MagicMock()
    stream_resp.raise_for_status = MagicMock()
    stream_resp.iter_bytes.return_value = [b"safe"]
    stream_cm = MagicMock()
    stream_cm.__enter__.return_value = stream_resp
    stream_cm.__exit__.return_value = None

    with patch.object(module.httpx, "get", return_value=_mk_response(topic_payload)), patch.object(
        module.httpx, "stream", return_value=stream_cm
    ):
        module.main(["--topic-id", "999"])

    # File should be saved with sanitized name in current directory, not traversed
    assert not (tmp_path / ".." / ".." / ".." / "etc" / "malicious.txt").exists()
    assert (tmp_path / "malicious.txt").exists()


def test_download_file_rejects_internal_url(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_script_module("download_file")
    monkeypatch.chdir(tmp_path)

    with pytest.raises(SystemExit):
        module.main(["http://169.254.169.254/latest/meta-data/", "-o", "meta.txt"])
