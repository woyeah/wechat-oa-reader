# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

from datetime import datetime
from typing import Literal

import pytest
from pydantic import ValidationError

from wechat_oa_reader.models import WeComUser, WeComMessage


def test_wecom_user_minimal():
    user = WeComUser(userid="zhangsan", name="张三")
    assert user.userid == "zhangsan"
    assert user.name == "张三"
    assert user.department is None
    assert user.avatar is None


def test_wecom_user_full():
    user = WeComUser(userid="zhangsan", name="张三", department="技术部", avatar="https://example.com/avatar.jpg")
    assert user.model_dump() == {
        "userid": "zhangsan",
        "name": "张三",
        "department": "技术部",
        "avatar": "https://example.com/avatar.jpg",
    }


def test_wecom_user_missing_required():
    with pytest.raises(ValidationError):
        WeComUser(userid="zhangsan")  # missing name


def test_wecom_message_minimal():
    msg = WeComMessage(
        msg_id="msg-1",
        msg_type="text",
        from_user="zhangsan",
        to_user="lisi",
        content="hello",
        create_time=1700000000,
        direction="sent",
    )
    assert msg.msg_id == "msg-1"
    assert msg.msg_type == "text"
    assert msg.from_user == "zhangsan"
    assert msg.to_user == "lisi"
    assert msg.content == "hello"
    assert msg.create_time == 1700000000
    assert msg.direction == "sent"


def test_wecom_message_received():
    msg = WeComMessage(
        msg_id="msg-2",
        msg_type="text",
        from_user="lisi",
        to_user="zhangsan",
        content="hi",
        create_time=1700000001,
        direction="received",
    )
    assert msg.direction == "received"


def test_wecom_message_invalid_direction():
    with pytest.raises(ValidationError):
        WeComMessage(
            msg_id="msg-3",
            msg_type="text",
            from_user="a",
            to_user="b",
            content="x",
            create_time=0,
            direction="unknown",
        )


def test_wecom_message_missing_required():
    with pytest.raises(ValidationError):
        WeComMessage(msg_id="msg-1", msg_type="text")
