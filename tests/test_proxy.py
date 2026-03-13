# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

from wechat_oa_reader.proxy import ProxyPool


class _Clock:
    def __init__(self, now: float) -> None:
        self.now = now

    def time(self) -> float:
        return self.now


def test_proxy_pool_empty() -> None:
    pool = ProxyPool([])
    assert pool.enabled is False
    assert pool.next() is None


def test_proxy_pool_single() -> None:
    pool = ProxyPool(["http://p1"])
    assert pool.next() == "http://p1"


def test_proxy_pool_rotation() -> None:
    pool = ProxyPool(["p1", "p2", "p3"])
    assert [pool.next(), pool.next(), pool.next(), pool.next()] == ["p1", "p2", "p3", "p1"]


def test_proxy_pool_mark_failed(monkeypatch) -> None:
    clock = _Clock(100)
    monkeypatch.setattr("wechat_oa_reader.proxy.time.time", clock.time)
    pool = ProxyPool(["p1", "p2"], fail_cooldown=120)
    pool.mark_failed("p1")
    assert pool.next() == "p2"


def test_proxy_pool_mark_ok(monkeypatch) -> None:
    clock = _Clock(100)
    monkeypatch.setattr("wechat_oa_reader.proxy.time.time", clock.time)
    pool = ProxyPool(["p1", "p2"], fail_cooldown=120)
    pool.mark_failed("p1")
    pool.mark_ok("p1")
    assert pool.next() == "p1"


def test_proxy_pool_all_failed(monkeypatch) -> None:
    clock = _Clock(100)
    monkeypatch.setattr("wechat_oa_reader.proxy.time.time", clock.time)
    pool = ProxyPool(["p1", "p2"], fail_cooldown=120)
    pool.mark_failed("p1")
    pool.mark_failed("p2")
    assert pool.next() is None


def test_proxy_pool_cooldown(monkeypatch) -> None:
    clock = _Clock(100)
    monkeypatch.setattr("wechat_oa_reader.proxy.time.time", clock.time)
    pool = ProxyPool(["p1"], fail_cooldown=10)
    pool.mark_failed("p1")
    assert pool.next() is None
    clock.now = 111
    assert pool.next() == "p1"


def test_proxy_pool_count() -> None:
    pool = ProxyPool(["p1", "p2", "p3"])
    assert pool.count == 3


def test_proxy_pool_get_status(monkeypatch) -> None:
    clock = _Clock(100)
    monkeypatch.setattr("wechat_oa_reader.proxy.time.time", clock.time)
    pool = ProxyPool(["p1", "p2"], fail_cooldown=120)
    pool.mark_failed("p2")
    status = pool.get_status()
    assert status == {
        "enabled": True,
        "total": 2,
        "healthy": 1,
        "failed": 1,
        "failed_proxies": ["p2"],
    }
