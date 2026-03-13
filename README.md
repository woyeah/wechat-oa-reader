# wechat-oa-reader

**微信公众号文章读取 Python 异步库**

[![Tests](https://github.com/woyeah/wechat-oa-reader/actions/workflows/test.yml/badge.svg)](https://github.com/woyeah/wechat-oa-reader/actions/workflows/test.yml)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://python.org)
[![License](https://img.shields.io/badge/license-AGPL--3.0-green)](LICENSE)

[English](#english) | 中文

扫码登录微信公众号后台，搜索公众号、获取文章列表、抓取完整内容 — 通过 **async API** 和 **CLI** 两种方式使用。基于 **curl_cffi** Chrome TLS 指纹模拟、**Pydantic v2** 数据模型、**httpx** 降级兜底。

## 安装

```bash
pip install wechat-oa-reader
```

## 快速上手

```python
import asyncio
from wechat_oa_reader import WeChatClient, load_credentials

async def main():
    creds = load_credentials()          # 从 .env 读取 token/cookie
    client = await WeChatClient.from_credentials(creds)

    # 搜索公众号
    accounts = await client.search_accounts("公众号名称")
    fakeid = accounts[0].fakeid

    # 获取最近文章
    articles = await client.get_articles(fakeid, count=5)

    # 抓取文章内容
    article = await client.fetch_article(articles.items[0].link)
    print(article.title)
    print(article.plain_text[:200])

asyncio.run(main())
```

## 命令行

```bash
wechat-oa login                          # 扫码登录
wechat-oa login --manual --token X --cookie Y  # 手动输入凭证
wechat-oa search "公众号名称"              # 搜索公众号
wechat-oa articles FAKEID -n 10          # 文章列表
wechat-oa fetch URL                      # 抓取单篇文章
wechat-oa fetch --batch urls.txt -o out.json   # 批量抓取
wechat-oa status                         # 查看凭证状态
```

## 核心特性

- **扫码登录** — 微信扫码认证，凭证自动存入 `.env`
- **公众号搜索** — 按名称查找公众号，获取 fakeid
- **文章列表** — 分页获取 + 关键词搜索
- **内容提取** — 正文 HTML、纯文本、图片列表
- **Chrome TLS 指纹** — curl_cffi `chrome120` 模拟，httpx 降级兜底
- **代理轮转** — SOCKS5/HTTP 代理池，失败自动冷却
- **异步限频** — 滑动窗口 + 文章间隔控制
- **SQLite 缓存** — 可选 `ArticleStore` 持久化文章
- **Token 管理** — 4 天有效期追踪，凭证存取

## 配置

凭证存储在 `.env` 文件中：

| 变量 | 说明 |
|------|------|
| `WECHAT_TOKEN` | 公众号后台 token |
| `WECHAT_COOKIE` | 会话 cookie |
| `WECHAT_FAKEID` | 当前账号 fakeid |
| `WECHAT_NICKNAME` | 账号昵称 |
| `WECHAT_EXPIRE_TIME` | Token 过期时间戳（毫秒） |

构造函数运行时配置：

```python
client = WeChatClient(
    token="...",
    cookie="...",
    proxies=["socks5://127.0.0.1:1080"],
    rate_limit=RateLimitConfig(requests_per_minute=30),
)
```

## Claude Code Plugin

本项目同时是一个标准 [Claude Code Plugin](https://code.claude.com/docs/en/plugins)，可在 Claude Code 中直接操作微信公众号。

**安装：**

```bash
# 开发/测试
claude --plugin-dir /path/to/wechat-oa-reader

# 或通过 marketplace 安装（如已发布）
/plugin install wechat-oa-reader
```

**使用 — 对 Claude 说：**

- "帮我搜索 XX 公众号"
- "列出 XX 公众号最近的文章"
- "抓取这篇微信文章的内容：URL"
- "批量下载某公众号的文章"

**工作流：** `check_install → check_auth → login（如需） → 执行操作`

每次操作自动完成：安装检测 → 凭证验证（4 天有效期） → 登录（扫码 / 手动） → 搜索 / 列表 / 抓取。所有脚本返回结构化 JSON 错误（`error_code`：`auth_missing` · `auth_expired` · `rate_limited` · `fetch_failed` 等）。

> 完整工作流、脚本参数和错误码详见 [`skills/wechat-oa-reader/SKILL.md`](skills/wechat-oa-reader/SKILL.md)

## 开发

```bash
pip install -e ".[dev]"
python -m pytest tests/ -v    # 67 tests
```

## 许可证

AGPL-3.0-only — 继承自上游 [wechat-download-api](https://github.com/tmwgsicp/wechat-download-api)。

## 致谢

基于 [wechat-download-api](https://github.com/tmwgsicp/wechat-download-api)（tmwgsicp）构建。

---

<a id="english"></a>

# wechat-oa-reader

**Async Python library for reading WeChat Official Account articles.**

[中文](#wechat-oa-reader) | English

Scan QR code to log in, search accounts, list articles, and fetch full content — via **async API** and **CLI**. Built with **curl_cffi** for Chrome TLS fingerprinting, **Pydantic v2** for data models, and **httpx** as fallback.

## Install

```bash
pip install wechat-oa-reader
```

## Quick Start

```python
import asyncio
from wechat_oa_reader import WeChatClient, load_credentials

async def main():
    creds = load_credentials()          # reads token/cookie from .env
    client = await WeChatClient.from_credentials(creds)

    # Search for an account
    accounts = await client.search_accounts("account-name")
    fakeid = accounts[0].fakeid

    # List recent articles
    articles = await client.get_articles(fakeid, count=5)

    # Fetch full content
    article = await client.fetch_article(articles.items[0].link)
    print(article.title)
    print(article.plain_text[:200])

asyncio.run(main())
```

## CLI

```bash
wechat-oa login                          # QR code login
wechat-oa login --manual --token X --cookie Y  # manual credentials
wechat-oa search "account-name"          # search accounts
wechat-oa articles FAKEID -n 10          # list articles
wechat-oa fetch URL                      # fetch single article
wechat-oa fetch --batch urls.txt -o out.json   # batch fetch
wechat-oa status                         # show credential status
```

## Features

- **QR code login** — scan with WeChat to authenticate, credentials saved to `.env`
- **Account search** — find Official Accounts by name, get fakeid
- **Article listing** — paginated article list with keyword search
- **Content extraction** — HTML, plain text, and image list from any article
- **Chrome TLS fingerprinting** — curl_cffi with `chrome120` impersonation, httpx fallback
- **Proxy rotation** — SOCKS5/HTTP proxy pool with failure cooldown
- **Async rate limiting** — sliding window + per-article interval
- **SQLite cache** — optional `ArticleStore` for article persistence
- **Token management** — 4-day expiry tracking, credential save/load

## Configuration

Credentials stored in `.env`:

| Variable | Description |
|----------|-------------|
| `WECHAT_TOKEN` | MP backend token |
| `WECHAT_COOKIE` | Session cookie |
| `WECHAT_FAKEID` | Your account's fakeid |
| `WECHAT_NICKNAME` | Account nickname |
| `WECHAT_EXPIRE_TIME` | Token expiry timestamp (ms) |

Runtime options via constructor:

```python
client = WeChatClient(
    token="...",
    cookie="...",
    proxies=["socks5://127.0.0.1:1080"],
    rate_limit=RateLimitConfig(requests_per_minute=30),
)
```

## Claude Code Plugin

This project doubles as a standard [Claude Code Plugin](https://code.claude.com/docs/en/plugins) for operating WeChat Official Accounts directly from Claude Code.

**Installation:**

```bash
# Development / testing
claude --plugin-dir /path/to/wechat-oa-reader

# Or via marketplace (if published)
/plugin install wechat-oa-reader
```

**Usage — just tell Claude:**

- "Search for XX official account"
- "List recent articles from XX account"
- "Fetch this WeChat article: URL"
- "Batch download articles from an account"

**Workflow:** `check_install → check_auth → login (if needed) → execute`

Auto-detects installation → validates credentials (4-day expiry) → login (QR / manual) → search / list / fetch. All scripts return structured JSON errors (`error_code`: `auth_missing` · `auth_expired` · `rate_limited` · `fetch_failed`, etc.).

> Full workflow, script parameters, and error codes in [`skills/wechat-oa-reader/SKILL.md`](skills/wechat-oa-reader/SKILL.md)

## Development

```bash
pip install -e ".[dev]"
python -m pytest tests/ -v    # 67 tests
```

## License

AGPL-3.0-only — inherited from upstream [wechat-download-api](https://github.com/tmwgsicp/wechat-download-api).

## Credits

Built on [wechat-download-api](https://github.com/tmwgsicp/wechat-download-api) by tmwgsicp.
