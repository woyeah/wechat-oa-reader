# wechat-oa-reader

Python async library for reading WeChat Official Account articles.

- Based on upstream `wechat-download-api` (AGPL-3.0)
- Async API only
- Pydantic v2 models

## Install

```bash
pip install wechat-oa-reader
```

For development:

```bash
pip install -e .[dev]
```

## Quick Start (Python)

```python
import asyncio
from wechat_oa_reader import WeChatClient, load_credentials


async def main() -> None:
    creds = load_credentials()
    if not creds:
        raise RuntimeError("Please login first")

    client = await WeChatClient.from_credentials(creds)

    accounts = await client.search_accounts("OpenAI")
    if not accounts:
        return

    fakeid = accounts[0].fakeid
    article_list = await client.get_articles(fakeid=fakeid, count=5)

    if article_list.items:
        article = await client.fetch_article(article_list.items[0].link)
        if article:
            print(article.title)
            print(article.plain_text[:200])


asyncio.run(main())
```

## CLI

```bash
wechat-oa login
wechat-oa status
wechat-oa search "OpenAI"
wechat-oa articles <FAKEID> -n 10
wechat-oa fetch "https://mp.weixin.qq.com/s?..."
wechat-oa fetch --batch urls.txt -o result.json
```

## Configuration

Credentials are loaded/saved from `.env`:

- `WECHAT_TOKEN`
- `WECHAT_COOKIE`
- `WECHAT_FAKEID`
- `WECHAT_NICKNAME`
- `WECHAT_EXPIRE_TIME`

Optional runtime settings:

- proxies via `WeChatClient(proxies=[...])`
- rate limit via `RateLimitConfig`

## License

AGPL-3.0-only. See `LICENSE`.

## Credits

- Upstream: `wechat-download-api` by tmwgsicp
- This package: `wechat-oa-reader` contributors
