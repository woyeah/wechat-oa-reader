---
name: zsxq-reader
description: Read and browse Knowledge Planet (知识星球/zsxq) groups — list topics, fetch topic content, and download attachments. Use this skill when the user mentions 知识星球, zsxq, Knowledge Planet, 星球, or wants to read/scrape content from zsxq.com. Do NOT use for WeChat Official Account tasks (use wechat-oa-reader instead).
---

# zsxq-reader

Read topics, comments, and files from Knowledge Planet (知识星球) groups via the zsxq.com API.

## Workflow

Every interaction follows this sequence. Do not skip steps.

### Step 1: Check authentication

```bash
python <skill-path>/scripts/check_auth.py
```

- If output shows `"status": "valid"`, proceed to Step 3
- If output shows `"status": "expired"` or `"status": "missing"`, go to Step 2

### Step 2: Setup authentication (if needed)

知识星球的 `zsxq_access_token` 是 HttpOnly Cookie，无法通过 JavaScript 自动提取，必须从浏览器 DevTools 手动复制。

**获取 Cookie 步骤：**

1. 在 Chrome 中打开 https://wx.zsxq.com 并登录（微信扫码）
2. 按 **F12** 打开 DevTools → 点击 **Network** 标签
3. 刷新页面（F5），在请求列表中找到任意一个发往 `api.zsxq.com` 的请求
4. 点击该请求 → **Headers** → 找到 **Request Headers** 中的 `Cookie:` 一行
5. 复制 `Cookie:` 后面的**完整值**（通常包含 `zsxq_access_token=...` 等多个字段）

**保存 Cookie（二选一）：**

方式一：命令保存（验证后自动写入 `.env`）
```bash
python <skill-path>/scripts/check_auth.py --save --cookie "<粘贴的 Cookie 字符串>"
```

方式二：手动写入 `.env` 文件
```
ZSXQ_COOKIE="abtest_env=product; zsxq_access_token=YOUR_TOKEN_HERE"
```

Cookie 存储在项目根目录的 `.env` 文件中（与微信公众号凭据共用同一文件），有效期通常 1-3 个月。

### Step 3: Execute the requested operation

**List user's groups (get group_id):**
```bash
python <skill-path>/scripts/list_groups.py
```
Returns all groups the user has joined, including `group_id`, name, owner, member/topic counts. Use this to find the `group_id` needed for other commands.

**List topics from a group:**
```bash
python <skill-path>/scripts/list_topics.py GROUP_ID --count 20
```

**List digest/pinned topics only:**
```bash
python <skill-path>/scripts/list_topics.py GROUP_ID --scope digests --count 20
```

**Paginate (older topics):**
```bash
python <skill-path>/scripts/list_topics.py GROUP_ID --count 20 --before "2026-03-01T00:00:00.000+0800"
```

**Fetch a single topic with comments:**
```bash
python <skill-path>/scripts/fetch_topic.py TOPIC_ID
```

**Fetch topic as JSON:**
```bash
python <skill-path>/scripts/fetch_topic.py TOPIC_ID --format json
```

**Fetch and save to file:**
```bash
python <skill-path>/scripts/fetch_topic.py TOPIC_ID -o output.txt
```

**Download a file attachment:**
```bash
python <skill-path>/scripts/download_file.py FILE_URL -o filename.pdf
```

**Download all attachments from a topic:**
```bash
python <skill-path>/scripts/download_file.py --topic-id TOPIC_ID
```

## Output formatting

- **Topic lists**: Present as a markdown table with columns: title/preview, author, date, type, comments count
- **Topic content (text)**: Show the plain text directly with markdown formatting
- **Topic content (json)**: Show structured data or save to file as requested
- **Errors**: Show the error message and suggest next steps (e.g., re-extract cookie if auth expired)

## Common workflows

**"帮我看看某个星球的最新帖子":**
1. check auth → list groups (find group_id) → list topics

**"获取这个帖子的内容":**
1. check auth → fetch topic (with topic_id)

**"下载星球里的附件":**
1. check auth → fetch topic → download files

**"看看星球的精华帖":**
1. check auth → list topics with `--scope digests`

## Important notes

- Cookie validity is ~1-3 months; if you get auth errors, ask the user to re-extract cookie from browser
- Cookie 存储在 `.env` 文件中（已在 `.gitignore` 中排除）
- Group ID is a numeric ID found in the zsxq URL (e.g., `https://wx.zsxq.com/group/123456`)
- Topic types: `talk` (normal post), `q_and_a` (Q&A), `article` (long article), `task` (assignment)
- Rate limiting: if you encounter error code 1059, wait a few seconds before retrying
- Topic IDs are large integers (17+ digits); scripts use Python so no precision issues, but beware of JavaScript number precision if debugging in browser
