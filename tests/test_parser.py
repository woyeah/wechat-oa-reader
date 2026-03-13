# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

from wechat_oa_reader.parser import (
    extract_article_info,
    extract_content,
    extract_images,
    html_to_text,
    is_article_deleted,
    is_valid_image_url,
    parse_article_url,
    process_article_content,
)


def test_extract_content_js_content(sample_article_html: str) -> None:
    content = extract_content(sample_article_html)
    assert "First paragraph" in content


def test_extract_content_rich_media(sample_rich_media_html: str) -> None:
    content = extract_content(sample_rich_media_html)
    assert "Article content here" in content


def test_extract_content_empty(sample_empty_html: str) -> None:
    assert extract_content(sample_empty_html) == ""


def test_extract_images_order(sample_article_html: str) -> None:
    images = extract_images(extract_content(sample_article_html))
    assert images == [
        "https://mmbiz.qpic.cn/image1.jpg",
        "https://mmbiz.qpic.cn/image2.jpg",
    ]


def test_extract_images_data_src_priority() -> None:
    html = '<img data-src="https://mmbiz.qpic.cn/data.jpg" src="https://mmbiz.qpic.cn/src.jpg" />'
    assert extract_images(html) == ["https://mmbiz.qpic.cn/data.jpg"]


def test_extract_images_dedup() -> None:
    html = (
        '<img data-src="https://mmbiz.qpic.cn/same.jpg" src="https://mmbiz.qpic.cn/same.jpg" />'
        '<img src="https://mmbiz.qpic.cn/same.jpg" />'
    )
    assert extract_images(html) == ["https://mmbiz.qpic.cn/same.jpg"]


def test_extract_images_no_base64() -> None:
    html = '<img data-src="data:image/jpeg;base64,abc" />'
    assert extract_images(html) == []


def test_extract_images_only_wechat_cdn() -> None:
    html = '<img src="https://example.com/a.jpg" /><img src="https://mmbiz.qpic.cn/a.jpg" />'
    assert extract_images(html) == ["https://mmbiz.qpic.cn/a.jpg"]


def test_is_valid_image_url_valid() -> None:
    assert is_valid_image_url("https://mmbiz.qpic.cn/a.jpg") is True


def test_is_valid_image_url_invalid() -> None:
    assert is_valid_image_url("https://example.com/a.jpg") is False


def test_is_valid_image_url_base64() -> None:
    assert is_valid_image_url("data:image/png;base64,abc") is False


def test_is_valid_image_url_empty() -> None:
    assert is_valid_image_url("") is False


def test_html_to_text(sample_article_html: str) -> None:
    text = html_to_text(sample_article_html)
    assert "First paragraph" in text
    assert "Second paragraph" in text


def test_html_to_text_preserves_breaks() -> None:
    html = "<p>A</p><p>B<br>C</p>"
    assert html_to_text(html) == "A\nB\nC"


def test_process_article_content(sample_article_html: str) -> None:
    result = process_article_content(sample_article_html)
    assert set(result.keys()) == {"html", "plain_text", "images", "has_images"}
    assert result["has_images"] is True


def test_process_article_content_empty(sample_empty_html: str) -> None:
    result = process_article_content(sample_empty_html)
    assert result == {"html": "", "plain_text": "", "images": [], "has_images": False}


def test_parse_article_url_valid() -> None:
    url = "https://mp.weixin.qq.com/s?__biz=MjM5&mid=123&idx=1&sn=abc"
    assert parse_article_url(url) == {"__biz": "MjM5", "mid": "123", "idx": "1", "sn": "abc"}


def test_parse_article_url_invalid() -> None:
    assert parse_article_url("https://example.com/s?x=1") is None


def test_parse_article_url_missing_params() -> None:
    url = "https://mp.weixin.qq.com/s?__biz=MjM5&mid=123"
    assert parse_article_url(url) is None


def test_is_article_deleted() -> None:
    assert is_article_deleted("This article has been deleted") is True


def test_extract_article_info(sample_full_article_html: str) -> None:
    info = extract_article_info(sample_full_article_html)
    assert info["title"] == "Test Article Title"
    assert info["author"] == "Test Author"
    assert info["publish_time"] == 1700000000
    assert "Content paragraph" in info["plain_content"]
    assert info["images"] == ["https://mmbiz.qpic.cn/img1.jpg"]
