# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

import html as html_module
import re
from urllib.parse import parse_qs, urlparse


def process_article_content(html: str) -> dict:
    content = extract_content(html)
    if not content:
        return {"html": "", "plain_text": "", "images": [], "has_images": False}

    images = extract_images(content)
    cleaned = clean_html(content)
    plain = html_to_text(cleaned)
    return {
        "html": cleaned,
        "plain_text": plain,
        "images": images,
        "has_images": bool(images),
    }


def extract_content(html: str) -> str:
    # Find the start of js_content div
    match = re.search(r'<div[^>]*\bid=["\']js_content["\'][^>]*>', html, re.IGNORECASE)
    if not match:
        match = re.search(r'<div[^>]*\bclass=["\'][^"\']*rich_media_content[^"\']*["\'][^>]*>', html, re.IGNORECASE)
    if not match:
        return ""

    start = match.end()
    depth = 1
    pos = start
    while pos < len(html) and depth > 0:
        open_match = re.search(r"<div[\s>]", html[pos:], re.IGNORECASE)
        close_match = re.search(r"</div\s*>", html[pos:], re.IGNORECASE)
        if close_match is None:
            break
        if open_match and open_match.start() < close_match.start():
            depth += 1
            pos += open_match.end()
        else:
            depth -= 1
            if depth == 0:
                return html[start : pos + close_match.start()].strip()
            pos += close_match.end()
    return html[start:].strip()


def extract_images(html: str) -> list[str]:
    images: list[str] = []
    for img_tag in re.finditer(r"<img[^>]*>", html, re.IGNORECASE):
        tag = img_tag.group(0)
        data_src = re.search(r"\bdata-src=[\"']([^\"']+)[\"']", tag, re.IGNORECASE)
        if data_src:
            url = data_src.group(1)
            if is_valid_image_url(url) and url not in images:
                images.append(url)
            continue

        src = re.search(r"\bsrc=[\"']([^\"']+)[\"']", tag, re.IGNORECASE)
        if src:
            url = src.group(1)
            if is_valid_image_url(url) and url not in images:
                images.append(url)
    return images


def clean_html(html: str) -> str:
    cleaned = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.IGNORECASE | re.DOTALL)
    cleaned = re.sub(r"<p[^>]*>\s*</p>", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\n\s*\n", "\n", cleaned)
    return cleaned.strip()


def html_to_text(html: str) -> str:
    text = re.sub(r"<img[^>]*>", "", html, flags=re.IGNORECASE)
    text = re.sub(r"<br\s*/?\s*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(
        r"</(?:p|div|section|h[1-6]|tr|li|blockquote)>",
        "\n",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"<hr[^>]*>", "\n---\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = html_module.unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_article_info(html: str) -> dict:
    title = ""
    title_match = (
        re.search(r"<h1[^>]*class=[^>]*rich_media_title[^>]*>([\s\S]*?)</h1>", html, re.IGNORECASE)
        or re.search(r"<h2[^>]*class=[^>]*rich_media_title[^>]*>([\s\S]*?)</h2>", html, re.IGNORECASE)
        or re.search(r"var\s+msg_title\s*=\s*'([^']+)'\.html\(false\)", html)
        or re.search(r"<meta\s+property=[\"']og:title[\"']\s+content=[\"']([^\"']+)[\"']", html, re.IGNORECASE)
    )
    if title_match:
        title = re.sub(r"<[^>]+>", "", title_match.group(1)).strip()

    author = ""
    author_match = (
        re.search(r"<a[^>]*id=[\"']js_name[\"'][^>]*>([\s\S]*?)</a>", html, re.IGNORECASE)
        or re.search(r"var\s+nickname\s*=\s*[\"']([^\"']+)[\"']", html)
        or re.search(
            r"<meta\s+property=[\"']og:article:author[\"']\s+content=[\"']([^\"']+)[\"']",
            html,
            re.IGNORECASE,
        )
        or re.search(
            r"<a[^>]*class=[^>]*rich_media_meta_nickname[^>]*>([^<]+)</a>",
            html,
            re.IGNORECASE,
        )
    )
    if author_match:
        author = re.sub(r"<[^>]+>", "", author_match.group(1)).strip()

    publish_time = 0
    time_match = (
        re.search(r"var\s+publish_time\s*=\s*[\"'](\d+)[\"']", html)
        or re.search(r"var\s+ct\s*=\s*[\"'](\d+)[\"']", html)
        or re.search(r"<em[^>]*id=[\"']publish_time[\"'][^>]*>([^<]+)</em>", html, re.IGNORECASE)
    )
    if time_match:
        try:
            publish_time = int(time_match.group(1))
        except (TypeError, ValueError):
            publish_time = 0

    content = extract_content(html)
    images = extract_images(content)
    content = clean_html(content)
    plain_content = html_to_text(content) if content else ""

    return {
        "title": title,
        "author": author,
        "publish_time": publish_time,
        "content": content,
        "plain_content": plain_content,
        "images": images,
    }


def parse_article_url(url: str) -> dict | None:
    if not url or "mp.weixin.qq.com/s" not in url:
        return None

    try:
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        biz = params.get("__biz", [""])[0]
        mid = params.get("mid", [""])[0]
        idx = params.get("idx", [""])[0]
        sn = params.get("sn", [""])[0]
    except Exception:
        return None

    if not all([biz, mid, idx, sn]):
        return None
    return {"__biz": biz, "mid": mid, "idx": idx, "sn": sn}


def is_valid_image_url(url: str) -> bool:
    if not url or url.startswith("data:"):
        return False
    return any(
        domain in url
        for domain in ("mmbiz.qpic.cn", "mmbiz.qlogo.cn", "wx.qlogo.cn")
    )


def is_article_deleted(html: str) -> bool:
    return "已删除" in html or "deleted" in html.lower()


def is_need_verification(html: str) -> bool:
    lowered = html.lower()
    return "verify" in lowered or "验证" in html or "环境异常" in html
