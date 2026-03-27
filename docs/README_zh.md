# wechat-oa-reader

**微信公众号文章 + 知识星球内容读取 Python 异步库**

[![Tests](https://github.com/woyeah/wechat-oa-reader/actions/workflows/test.yml/badge.svg)](https://github.com/woyeah/wechat-oa-reader/actions/workflows/test.yml)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://python.org)
[![License](https://img.shields.io/badge/license-AGPL--3.0-green)](../LICENSE)

[English](../README.md) | 中文

扫码登录微信公众号后台，搜索公众号、获取文章列表、抓取完整内容 — 通过 **async API** 和 **CLI** 两种方式使用。同时支持浏览知识星球（zsxq.com）的帖子、评论和附件。基于 **curl_cffi** Chrome TLS 指纹模拟、**Pydantic v2** 数据模型、**httpx** 降级兜底。

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
- **知识星球** — 浏览星球、帖子列表、内容获取、附件下载（Cookie 认证，存入 `.env`）
- **企业微信（WeCom）** — `WeComClient` 发送文本和图片消息，自动缓存 access_token

## 配置

凭证存储在 `.env` 文件中：

| 变量 | 说明 |
|------|------|
| `WECHAT_TOKEN` | 公众号后台 token |
| `WECHAT_COOKIE` | 会话 cookie |
| `WECHAT_FAKEID` | 当前账号 fakeid |
| `WECHAT_NICKNAME` | 账号昵称 |
| `WECHAT_EXPIRE_TIME` | Token 过期时间戳（毫秒） |
| `ZSXQ_COOKIE` | 知识星球会话 Cookie（可选） |

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
/plugin marketplace add woyeah/wechat-oa-reader
/plugin install wechat-oa-reader
```

**使用 — 对 Claude 说：**

- "帮我搜索 XX 公众号"
- "列出 XX 公众号最近的文章"
- "抓取这篇微信文章的内容：URL"
- "批量下载某公众号的文章"
- "帮我看看知识星球的最新帖子"
- "获取知识星球某个帖子的完整内容"

## 在其他 AI CLI 中使用

安装库后，通过 @-mention SKILL.md 即可让任何 AI 助手使用本工具：

```bash
pip install wechat-oa-reader
```

然后在 AI CLI 中：

```
@path/to/SKILL.md 帮我搜索"人民日报"的文章
```

或直接告诉 AI 使用 `wechat-oa` 命令。

> 完整工作流详见 [`skills/wechat-oa-reader/SKILL.md`](../skills/wechat-oa-reader/SKILL.md)

## 企业微信（WeCom）集成

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

    # 发送图片
    with open("chart.png", "rb") as f:
        media_id = await client.upload_media(f.read(), "chart.png")
    await client.send_image(media_id)

asyncio.run(main())
```

## 企业微信 MCP 服务（Docker）

将企业微信部署为 MCP 服务 — Claude Code 直接调用 tools，同时处理企业微信消息回调。

```bash
pip install wechat-oa-reader[mcp]
wecom-mcp  # 启动 FastMCP 服务，端口 8000
```

**MCP Tools：**

| Tool | 说明 |
|------|------|
| `check_status` | 检查企业微信连接状态 |
| `send_message` | 按姓名或 @all 发消息 |
| `list_users` | 列出缓存的通讯录 |
| `get_messages` | 查询消息历史 |
| `get_replies` | 查看收到的回复 |

**Docker 部署：**

```bash
docker build -t wecom-mcp .
docker run -d -p 8000:8000 --env-file .env -v wecom-data:/data wecom-mcp
```

支持多实例 — 每个实例使用独立的 `.env.wecom-<name>` 和 Docker volume（SQLite 不支持多进程共享）。模板见 `.env.example`，生产编排见 `docker-compose.prod.yml`，NAS 一键部署见 `deploy.sh`。

## 开发

```bash
pip install -e ".[dev]"
python -m pytest tests/ -v
```

## 许可证

AGPL-3.0-only — 继承自上游 [wechat-download-api](https://github.com/tmwgsicp/wechat-download-api)。

## 致谢

基于 [wechat-download-api](https://github.com/tmwgsicp/wechat-download-api)（tmwgsicp）构建。
