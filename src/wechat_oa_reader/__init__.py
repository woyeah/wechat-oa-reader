# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

from .auth import load_credentials, login_with_qrcode, save_credentials
from .client import WeChatClient
from .models import (
    Account,
    ArticleContent,
    ArticleList,
    ArticleSummary,
    Credentials,
    ProxyConfig,
    RateLimitConfig,
)
from .parser import extract_article_info, process_article_content
from .store import ArticleStore

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "WeChatClient",
    "Credentials",
    "Account",
    "ArticleSummary",
    "ArticleList",
    "ArticleContent",
    "ProxyConfig",
    "RateLimitConfig",
    "login_with_qrcode",
    "save_credentials",
    "load_credentials",
    "ArticleStore",
    "process_article_content",
    "extract_article_info",
]
