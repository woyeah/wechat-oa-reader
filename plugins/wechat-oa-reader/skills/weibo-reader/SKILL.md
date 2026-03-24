---
name: weibo-reader
description: Read and browse Weibo (微博) user posts, fetch post content, and list comments. Use this skill when the user mentions 微博, Weibo, weibo-reader, or wants to read/scrape content from weibo.com or m.weibo.cn. Do NOT use for WeChat Official Account tasks (use wechat-oa-reader instead) or Knowledge Planet tasks (use zsxq-reader instead).
---

# weibo-reader

Read posts, comments, and user info from Weibo (微博) via the m.weibo.cn mobile API.

## Workflow

Every interaction follows this sequence. Do not skip steps.

**IMPORTANT:** All scripts read `WEIBO_COOKIE` from the `.env` file in the current working directory. Before running any script, ensure your CWD is the project root (where `.env` lives):
```bash
cd /path/to/your/project
```

### Step 1: Check authentication

```bash
python <skill-path>/scripts/check_auth.py
```

- If output shows `"status": "valid"`, proceed to Step 3
- If output shows `"status": "expired"` or `"status": "missing"`, go to Step 2

### Step 2: Setup authentication (if needed)

微博的 Cookie 需要从浏览器手动复制。

**获取 Cookie 步骤：**

1. 在 Chrome 中打开 https://m.weibo.cn 并登录
2. 按 **F12** 打开 DevTools → 点击 **Network** 标签
3. 刷新页面（F5），在请求列表中找到任意一个发往 `m.weibo.cn` 的请求
4. 点击该请求 → **Headers** → 找到 **Request Headers** 中的 `Cookie:` 一行
5. 复制 `Cookie:` 后面的**完整值**（通常包含 `SUB=...` 等多个字段）

**保存 Cookie（二选一）：**

方式一：命令保存（验证后自动写入 `.env`）
```bash
python <skill-path>/scripts/check_auth.py --save --cookie "<粘贴的 Cookie 字符串>"
```

方式二：手动写入 `.env` 文件
```
WEIBO_COOKIE="SUB=YOUR_SUB_VALUE; SUBP=YOUR_SUBP_VALUE"
```

Cookie 存储在项目根目录的 `.env` 文件中（与微信公众号、知识星球凭据共用同一文件）。

### Step 3: Execute the requested operation

**Search users by keyword:**
```bash
python <skill-path>/scripts/search_user.py "关键词"
```
Returns matching users with uid, nickname, description, follower counts.

**List posts from a user:**
```bash
python <skill-path>/scripts/list_posts.py UID --count 20
```

**Paginate (older posts):**
```bash
python <skill-path>/scripts/list_posts.py UID --count 20 --since-id "CURSOR_VALUE"
```
Use the `since_id` from previous output to fetch the next page.

**Fetch a single post (full content):**
```bash
python <skill-path>/scripts/fetch_post.py BID
```
Automatically expands long text. Use `--format text` for plain text output.

**List comments on a post:**
```bash
python <skill-path>/scripts/list_comments.py POST_MID --count 20
```

**Paginate comments:**
```bash
python <skill-path>/scripts/list_comments.py POST_MID --count 20 --max-id "CURSOR_VALUE"
```

### Step 4: Present results

- Summarize the content clearly for the user
- For posts with images, mention the image count and provide URLs
- For long post lists, show key info (author, date, engagement) in a table
- Always note the `since_id` or `max_id` cursor if more pages are available

## Common Workflows

### Read a user's recent posts
1. Search for the user: `search_user.py "用户名"`
2. Get their UID from the results
3. List their posts: `list_posts.py UID --count 10`
4. Fetch full content of interesting posts: `fetch_post.py BID`

### Read comments on a post
1. Get the post's MID (from list_posts or fetch_post output)
2. List comments: `list_comments.py MID --count 20`

## Important Notes

- **Rate limiting**: Weibo has aggressive anti-scraping. Keep requests infrequent (< 10/min). If you get HTTP 418 or 429, wait before retrying.
- **Cookie expiry**: Weibo cookies expire periodically. If scripts return `auth_expired`, the user needs to re-extract the cookie from their browser.
- **Content format**: Post text from the API contains HTML tags. Scripts strip tags for plain text output where applicable.
- **Long text**: Posts marked as `is_long_text` are automatically expanded via a separate API call.

## CLI Alternative

If `wechat-oa-reader` is installed (`pip install wechat-oa-reader`), you can also use CLI commands:

```bash
wechat-oa weibo status
wechat-oa weibo user UID
wechat-oa weibo posts UID -n 20
wechat-oa weibo fetch BID [--text]
wechat-oa weibo comments POST_ID -n 20
wechat-oa weibo search "关键词"
```
