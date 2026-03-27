# wechat-oa-reader

**Async Python library for reading WeChat Official Account articles and Knowledge Planet (知识星球/zsxq) content.**

[![Tests](https://github.com/woyeah/wechat-oa-reader/actions/workflows/test.yml/badge.svg)](https://github.com/woyeah/wechat-oa-reader/actions/workflows/test.yml)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://python.org)
[![License](https://img.shields.io/badge/license-AGPL--3.0-green)](LICENSE)

[中文](docs/README_zh.md) | English

Scan QR code to log in, search accounts, list articles, and fetch full content — via **async API** and **CLI**. Also supports browsing Knowledge Planet (zsxq.com) groups, topics, and attachments. Built with **curl_cffi** for Chrome TLS fingerprinting, **Pydantic v2** for data models, and **httpx** as fallback.

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
- **Knowledge Planet (zsxq)** — browse groups, list topics, fetch content, download attachments (cookie auth via `.env`)
- **WeCom (企业微信)** — `WeComClient` for sending text and image messages via WeCom API, with automatic token caching

## Configuration

Credentials stored in `.env`:

| Variable | Description |
|----------|-------------|
| `WECHAT_TOKEN` | MP backend token |
| `WECHAT_COOKIE` | Session cookie |
| `WECHAT_FAKEID` | Your account's fakeid |
| `WECHAT_NICKNAME` | Account nickname |
| `WECHAT_EXPIRE_TIME` | Token expiry timestamp (ms) |
| `ZSXQ_COOKIE` | Knowledge Planet session cookie (optional) |

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
/plugin marketplace add woyeah/wechat-oa-reader
/plugin install wechat-oa-reader
```

**Usage — just tell Claude:**

- "Search for XX official account"
- "List recent articles from XX account"
- "Fetch this WeChat article: URL"
- "Batch download articles from an account"
- "帮我看看知识星球的最新帖子"
- "List topics from my Knowledge Planet group"

## Use with Other AI CLIs

After installing the library, @-mention SKILL.md to let any AI assistant use this tool:

```bash
pip install wechat-oa-reader
```

Then in your AI CLI:

```
@path/to/SKILL.md Search for articles from "People's Daily"
```

Or simply tell the AI to use the `wechat-oa` commands.

> Full workflow details in [`skills/wechat-oa-reader/SKILL.md`](skills/wechat-oa-reader/SKILL.md)

## WeCom (企业微信) Integration

```python
import asyncio
from wechat_oa_reader import WeComClient

async def main():
    client = WeComClient(
        corp_id="your-corp-id",
        agent_secret="your-agent-secret",
        agent_id="your-agent-id",
    )
    await client.send_text("Hello from WeComClient!")

    # Send an image
    with open("chart.png", "rb") as f:
        media_id = await client.upload_media(f.read(), "chart.png")
    await client.send_image(media_id)

asyncio.run(main())
```

## WeCom MCP Server (Docker)

Deploy WeCom as an MCP service — Claude Code calls tools directly, and WeCom message callbacks are handled in the same process.

```bash
pip install wechat-oa-reader[mcp]
wecom-mcp  # starts FastMCP server on port 8000
```

**MCP Tools:**

| Tool | Description |
|------|-------------|
| `check_status` | Check WeCom API connection |
| `send_message` | Send message by name or @all |
| `list_users` | List cached address book |
| `get_messages` | Query message history |
| `get_replies` | Get received replies |

**Docker deployment:**

```bash
docker build -t wecom-mcp .
docker run -d -p 8000:8000 --env-file .env -v wecom-data:/data wecom-mcp
```

Multiple instances supported — each gets its own `.env.wecom-<name>` and Docker volume (SQLite cannot be shared across instances). See `.env.example` for the per-instance template, `docker-compose.prod.yml` for production setup, and `deploy.sh` for NAS deployment.

## Development

```bash
pip install -e ".[dev]"
python -m pytest tests/ -v
```

## License

AGPL-3.0-only — inherited from upstream [wechat-download-api](https://github.com/tmwgsicp/wechat-download-api).

## Credits

Built on [wechat-download-api](https://github.com/tmwgsicp/wechat-download-api) by tmwgsicp.
