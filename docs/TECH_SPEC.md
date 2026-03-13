# wechat-oa-reader — Technical Specification

## 项目结构

```
wechat-oa-reader/
├── pyproject.toml
├── LICENSE                      # AGPL-3.0
├── README.md
├── .claude-plugin/
│   └── plugin.json              # Claude Code Plugin manifest
├── skills/
│   └── wechat-oa-reader/
│       ├── SKILL.md             # AI skill workflow
│       └── scripts/             # Plugin scripts
├── docs/
│   ├── PRD.md
│   └── TECH_SPEC.md
├── src/
│   └── wechat_oa_reader/
│       ├── __init__.py          # 公开 API 导出
│       ├── models.py            # Pydantic 数据模型
│       ├── auth.py              # 登录 + 凭证管理
│       ├── client.py            # 主客户端（搜索、文章列表）
│       ├── fetcher.py           # HTTP 抓取（代理 + TLS 指纹）
│       ├── parser.py            # HTML 解析（正文/图片/纯文本）
│       ├── proxy.py             # 代理池管理
│       ├── limiter.py           # 限频器
│       ├── store.py             # SQLite 缓存（可选）
│       ├── cli.py               # Click CLI 入口
│       └── py.typed             # PEP 561 type marker
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── test_parser.py
    └── test_models.py
```

## 依赖

```
httpx>=0.25
curl_cffi>=0.7
pydantic>=2.0
python-dotenv>=1.0
click>=8.0
```

## 数据模型 (models.py)

```python
class Credentials(BaseModel):
    token: str
    cookie: str
    fakeid: str | None = None
    nickname: str | None = None
    expire_time: int | None = None  # 毫秒时间戳

class Account(BaseModel):
    fakeid: str
    nickname: str
    alias: str | None = None
    head_img: str | None = None
    service_type: int | None = None

class ArticleSummary(BaseModel):
    aid: str
    title: str
    link: str
    digest: str | None = None
    cover: str | None = None
    author: str | None = None
    update_time: int = 0
    create_time: int = 0

class ArticleList(BaseModel):
    items: list[ArticleSummary]
    total: int = 0
    offset: int = 0

class ArticleContent(BaseModel):
    url: str
    title: str | None = None
    author: str | None = None
    publish_time: int = 0
    html: str
    plain_text: str
    images: list[str]

class ProxyConfig(BaseModel):
    urls: list[str] = []
    fail_cooldown: int = 120

class RateLimitConfig(BaseModel):
    requests_per_minute: int = 10
    article_fetch_interval: float = 3.0
```

## 主客户端 API (client.py)

```python
class WeChatClient:
    def __init__(
        self,
        token: str | None = None,
        cookie: str | None = None,
        proxies: list[str] | None = None,
        rate_limit: RateLimitConfig | None = None,
    ): ...

    @classmethod
    async def from_credentials(cls, credentials: Credentials, **kwargs) -> "WeChatClient": ...

    async def search_accounts(self, query: str, count: int = 5) -> list[Account]: ...

    async def get_articles(
        self, fakeid: str, count: int = 10, offset: int = 0, keyword: str | None = None
    ) -> ArticleList: ...

    async def fetch_article(self, url: str, timeout: int = 60) -> ArticleContent | None: ...

    async def fetch_articles(
        self, urls: list[str], max_concurrency: int = 5, timeout: int = 60
    ) -> list[ArticleContent]: ...

    @property
    def is_authenticated(self) -> bool: ...

    @property
    def credentials(self) -> Credentials | None: ...
```

## 登录 (auth.py)

```python
async def login_with_qrcode(
    on_qrcode: Callable[[bytes], Awaitable[None]] | None = None,
) -> Credentials:
    """
    完整的扫码登录流程。
    1. startlogin → 获取 session
    2. getqrcode → 获取二维码图片
    3. ask (轮询) → 等待扫码确认
    4. bizlogin → 完成登录，提取 token/cookie
    5. searchbiz → 获取 fakeid

    on_qrcode: 回调函数，接收二维码图片字节。
    默认行为：保存到临时文件并打印路径。
    """
    ...

def save_credentials(credentials: Credentials, path: Path | None = None) -> None:
    """保存凭证到 .env 文件"""
    ...

def load_credentials(path: Path | None = None) -> Credentials | None:
    """从 .env 文件加载凭证"""
    ...
```

## CLI 命令 (cli.py)

```
wechat-oa login [--manual]              # 扫码登录 / 手动输入
wechat-oa search QUERY                  # 搜索公众号
wechat-oa articles FAKEID [-n 10]       # 文章列表
wechat-oa fetch URL [-o FILE] [--text]  # 抓取单篇文章
wechat-oa fetch --batch FILE            # 批量抓取
wechat-oa status                        # 显示登录状态
```

## 模块职责

| 模块 | 职责 | 上游来源 |
|------|------|---------|
| models.py | Pydantic 数据模型 | 新写 |
| auth.py | 登录流程 + 凭证存取 | auth_manager + login route |
| client.py | 主 API（搜索、文章列表）| articles + search routes |
| fetcher.py | HTTP 抓取 + TLS 指纹 | http_client + article_fetcher |
| parser.py | HTML → 正文/纯文本/图片 | content_processor + helpers |
| proxy.py | 代理池轮转 + 失败冷却 | proxy_pool |
| limiter.py | 滑动窗口限频 | rate_limiter |
| store.py | SQLite 文章缓存 | rss_store |
| cli.py | Click CLI | 新写 |

## 关键技术点

1. **TLS 指纹**：curl_cffi `impersonate="chrome120"` 模拟 Chrome
2. **代理策略**：Proxy1 → Proxy2 → ... → 直连兜底
3. **登录流程**：bizlogin(startlogin) → getqrcode → ask(轮询) → bizlogin(login)
4. **Token 有效期**：~4 天，凭证存 .env
5. **文章 API**：`https://mp.weixin.qq.com/cgi-bin/appmsgpublish`
6. **搜索 API**：`https://mp.weixin.qq.com/cgi-bin/searchbiz`
7. **JSON 嵌套**：publish_page/publish_info 可能是 JSON 字符串，需二次解析
