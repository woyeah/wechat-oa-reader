---
name: wechat-oa-reader
description: Read and fetch WeChat Official Account (微信公众号) articles. Use this skill whenever the user wants to search WeChat public accounts, list their articles, fetch article content, or log in to the WeChat MP backend. Also trigger when the user mentions 公众号, WeChat OA, wechat-oa-reader, or wants to scrape/extract data from WeChat articles. Do NOT use for general web scraping unrelated to WeChat Official Accounts.
---

# wechat-oa-reader

Operate the `wechat-oa-reader` CLI to search WeChat Official Accounts, list articles, and fetch full article content.

## Workflow

Every interaction follows this sequence. Do not skip steps.

### Step 1: Check installation and CLI

```bash
pip show wechat-oa-reader || pip install wechat-oa-reader
```

If installation fails, tell the user to install manually: `pip install wechat-oa-reader`

Then detect which CLI command works and use it for all subsequent steps:
```bash
wechat-oa --version 2>/dev/null && WOA="wechat-oa" || WOA="python -m wechat_oa_reader"
```

Use `$WOA` in place of `wechat-oa` for all commands below. If running on Windows and `$WOA` doesn't work, fall back to `python -m wechat_oa_reader` directly.

### Step 2: Check authentication

```bash
$WOA status
```

- If output shows `"authenticated": true` and not expired, proceed to Step 4
- If output shows `Not authenticated` or expired, go to Step 3

### Step 3: Login (if needed)

**QR code login (two-phase):**

Phase 1 — Get the QR code:
```bash
python <skill-path>/scripts/login.py --start
```
This will:
- Automatically open the QR code image in the system viewer (Windows/macOS/Linux)
- Print ASCII QR art to terminal as fallback
- Output JSON with `qr_path` and `session_path` on the last line

Tell the user: "请扫描弹出的二维码登录，扫码后我会继续完成登录流程"

Phase 2 — Wait for scan and complete login:
```bash
python <skill-path>/scripts/login.py --complete --session <session_path from JSON>
```
This blocks until the user scans, then saves credentials to `.env`.

**Manual login (if user already has token/cookie):**
```bash
$WOA login --manual --token TOKEN --cookie COOKIE
```

### Step 4: Execute the requested operation

**Search for accounts:**
```bash
$WOA search "公众号名称" --count 5
```
Outputs JSON array of matching accounts with nickname, fakeid, and alias.

**List articles:**
```bash
$WOA articles FAKEID -n 10 --offset 0 --keyword KEYWORD
```
Outputs JSON with articles including title, date, and link.

**Fetch article content (plain text):**
```bash
$WOA fetch URL --text
```

**Fetch article content (JSON with full metadata):**
```bash
$WOA fetch URL
```

**Fetch and save to file:**
```bash
$WOA fetch URL -o output.txt --text
```

**Batch fetch from URL list:**
```bash
$WOA fetch --batch urls.txt --text
```

## Output formatting

- **Search results and article lists**: Present the JSON as a markdown table to the user
- **Article content (text)**: Show the plain text directly
- **Article content (json)**: Show structured data or save to file as requested
- **Errors**: Show the error message and suggest next steps (e.g., re-login if auth expired)

## Common workflows

**"帮我搜索某个公众号的最新文章":**
1. check install → status → search → articles → fetch

**"抓取这篇公众号文章":**
1. check install → status → fetch (with the URL)

**"批量下载某公众号的文章":**
1. check install → status → search → articles → save URLs to file → batch fetch

## Important notes

- Token expires after ~4 days; if you get auth errors, re-run `$WOA login`
- Rate limiting is built into the library (10 req/min, 3s between articles) — do not add extra delays
- The `.env` file contains credentials and should not be committed to git
