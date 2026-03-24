# Weibo Reader — 设计文档

## 概述

为 wechat-oa-reader 添加微博（Weibo）内容抓取功能，作为继微信公众号、知识星球之后的第三个内容源。

### 目标 Use Cases（P0）

1. **获取用户微博列表** — 输入 UID，分页拉取微博
2. **获取单条微博详情** — 输入 bid，获取完整内容（含长文展开）
3. **获取微博评论** — 指定微博 ID，分页抓取评论
4. **搜索用户** — 按关键词搜索微博用户

### 后续 TODO（不在本次范围）

- 搜索微博内容（按关键词/话题）
- 获取热搜榜
- 内容分发/同步到微博
- 舆情监控/分析

---

## 架构

采用混合模式：核心 client 放库里（可编程调用），同时加 Skill 供 Claude Code 使用。

### 文件结构

```
src/wechat_oa_reader/
├── weibo.py              # WeiboClient（async）
├── models.py             # 新增 Weibo* 数据模型

plugins/wechat-oa-reader/skills/
└── weibo-reader/
    ├── SKILL.md           # Claude Code Skill 工作流
    └── scripts/
        ├── check_auth.py   # 验证 Cookie 有效性
        ├── list_posts.py   # 获取用户微博列表
        ├── fetch_post.py   # 获取单条微博详情
        ├── list_comments.py # 获取评论
        ├── search_user.py  # 搜索用户
        └── _errors.py      # 共享错误处理
```

### CLI 命令

```bash
wechat-oa weibo status                    # 检查 Cookie 有效性
wechat-oa weibo user UID                  # 用户信息
wechat-oa weibo posts UID [-n 20]         # 用户微博列表
wechat-oa weibo fetch BID [--text]        # 单条微博详情
wechat-oa weibo comments POST_ID [-n 20]  # 评论
wechat-oa weibo search "关键词"            # 搜索用户
```

---

## 数据模型

新增 Pydantic v2 模型至 `models.py`：

### WeiboUser

| 字段 | 类型 | 说明 |
|------|------|------|
| `uid` | `str` | 用户 UID |
| `nickname` | `str` | 昵称 |
| `avatar` | `str \| None` | 头像 URL |
| `description` | `str \| None` | 简介 |
| `followers_count` | `int \| None` | 粉丝数 |
| `following_count` | `int \| None` | 关注数 |
| `verified` | `bool` | 是否认证 |
| `verified_reason` | `str \| None` | 认证说明 |

### WeiboPost

| 字段 | 类型 | 说明 |
|------|------|------|
| `bid` | `str` | 微博短 ID |
| `mid` | `str` | 微博数字 ID |
| `uid` | `str` | 发布者 UID |
| `text` | `str` | 纯文本内容 |
| `html` | `str \| None` | 原始 HTML 内容 |
| `images` | `list[str]` | 图片 URL 列表（`large` 尺寸） |
| `video_url` | `str \| None` | 视频 URL |
| `repost` | `WeiboPost \| None` | 转发的原微博（递归） |
| `is_long_text` | `bool` | 是否长文（`fetch_post` 会自动展开） |
| `created_at` | `datetime` | 发布时间（解析自 API 字符串） |
| `likes_count` | `int` | 点赞数 |
| `reposts_count` | `int` | 转发数 |
| `comments_count` | `int` | 评论数 |

### WeiboPostList

| 字段 | 类型 | 说明 |
|------|------|------|
| `items` | `list[WeiboPost]` | 微博列表 |
| `total` | `int \| None` | 总数 |
| `since_id` | `str \| None` | 分页游标（用于下一页请求） |

### WeiboComment

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | `str` | 评论 ID |
| `uid` | `str` | 评论者 UID |
| `nickname` | `str` | 评论者昵称 |
| `text` | `str` | 评论文本 |
| `created_at` | `datetime` | 评论时间 |
| `likes_count` | `int` | 点赞数 |

### WeiboCommentList

| 字段 | 类型 | 说明 |
|------|------|------|
| `items` | `list[WeiboComment]` | 评论列表 |
| `total` | `int \| None` | 总数 |
| `max_id` | `str \| None` | 游标（用于下一页请求） |

---

## WeiboClient 接口

```python
class WeiboClient:
    """微博内容抓取客户端，基于 m.weibo.cn 移动端接口。"""

    def __init__(
        self,
        cookie: str,
        *,
        proxies: list[str] | None = None,
        rate_limit: RateLimitConfig | None = None,
    ): ...

    @property
    def is_authenticated(self) -> bool: ...

    async def check_auth(self) -> bool:
        """验证 Cookie 是否有效。"""

    async def get_user(self, uid: str) -> WeiboUser:
        """获取用户信息。"""

    async def get_posts(
        self, uid: str, *, since_id: str | None = None, count: int = 20
    ) -> WeiboPostList:
        """获取用户微博列表，支持分页。"""

    async def fetch_post(self, bid: str) -> WeiboPost:
        """获取单条微博详情，含长文展开。"""

    async def get_comments(
        self, post_id: str, *, max_id: str | None = None, count: int = 20
    ) -> WeiboCommentList:
        """获取微博评论，游标分页。"""

    async def search_users(self, query: str) -> list[WeiboUser]:
        """按关键词搜索用户。"""
```

---

## API 端点

所有请求走 `m.weibo.cn`，需携带 Cookie。

| 功能 | 端点 | 说明 |
|------|------|------|
| 用户信息 | `GET /api/container/getIndex?uid={uid}` | `containerid` 前缀 `100505` |
| 微博列表 | `GET /api/container/getIndex?containerid={动态发现}&since_id={since_id}` | 先通过用户信息接口的 `tabsInfo` 发现微博 tab 的 containerid，不硬编码 `107603` |
| 单条微博 | `GET /statuses/show?id={bid}` | 含完整内容 |
| 长文展开 | `GET /statuses/longtext?id={mid}` | 长微博全文 |
| 评论 | `GET /api/comments/show?id={mid}&max_id={max_id}` | 游标分页评论 |
| 搜索用户 | `GET /api/container/getIndex?containerid=100103type%3D3%26q%3D{query}` | 用户搜索 |

### 请求头

```
User-Agent: Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) ...
X-Requested-With: XMLHttpRequest
Cookie: {WEIBO_COOKIE}
Referer: https://m.weibo.cn/
```

---

## 认证

- **方式**：手动 Cookie — 用户从浏览器 `m.weibo.cn` 复制 Cookie
- **存储**：`.env` 文件中 `WEIBO_COOKIE=...`
- **验证**：`check_auth` 请求用户主页，检查响应状态
- **无自动登录**，无 Playwright

---

## HTTP 层

- **复用现有 `Fetcher` 类**（与 WeChatClient 一致），获得 proxy rotation、rate limiting、curl_cffi 支持
- WeiboClient 构造函数接受 `proxies: list[str]`（与 WeChatClient 签名一致），内部构建 `ProxyPool` + `Fetcher`
- Skill 脚本使用同步 `httpx`（与 zsxq 脚本一致）

## 反爬策略

- 复用现有 `RateLimitConfig`（默认保守频率，建议 10 req/min）
- 复用 `ProxyPool`（可选）
- 固定移动端 User-Agent
- 请求失败时指数退避重试（最多 3 次），HTTP 418/429 时加长等待

## 错误处理

Weibo 特有的错误码和场景：

| 错误 | 含义 | 处理 |
|------|------|------|
| HTTP 418 | 反爬拦截 | 退避重试，提示用户降低频率 |
| HTTP 429 | 频率限制 | 退避重试 |
| HTTP 403 | Cookie 失效 | 提示用户重新获取 Cookie |
| `errno: 20003` | Cookie 过期 | 同上 |
| `errno: 20101` | 用户不存在 | 抛异常 |
| `errno: 22009` | 内容已删除 | 返回 None 或标记 |

## 测试策略

遵循 CLAUDE.md 的 TDD 要求：

1. **Mock API 响应 fixture** — `tests/fixtures/weibo/` 下存放各端点的示例 JSON 响应
2. **模型解析测试** — mock JSON → Pydantic 模型，验证字段映射
3. **WeiboClient 测试** — mock httpx，验证请求参数和响应解析
4. **Skill 脚本测试** — subprocess 调用 + mock HTTP

---

## 技术参考

- [crawl4weibo](https://github.com/Praeviso/crawl4weibo)（MIT）— 数据模型和接口设计参考
- [dataabc/weibo-crawler](https://github.com/dataabc/weibo-crawler)（4.4k stars）— 端点和反爬经验参考
- [Xarrow/weibo-scraper](https://github.com/Xarrow/weibo-scraper)（MIT）— 轻量实现参考

---

## 实现顺序

1. 数据模型（`models.py` 新增 Weibo* 模型）+ 模型测试
2. `WeiboClient`（`weibo.py`）+ client 测试
3. CLI 命令（`cli.py` 新增 `weibo` 子命令组）
4. Skill 脚本（`plugins/.../weibo-reader/scripts/`）
5. SKILL.md

每步先写测试，再写实现。

---

## 不做的事

- 不用 Playwright / 浏览器自动化
- 不实现自动登录
- 不做视频下载（只保留 URL）
- 不做数据分析/可视化
- 不做内容发布/同步
