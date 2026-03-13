---
name: wechat-oa-reader
description: Read and fetch WeChat Official Account (微信公众号) articles. Use this skill whenever the user wants to search WeChat public accounts, list their articles, fetch article content, or log in to the WeChat MP backend. Also trigger when the user mentions 公众号, WeChat OA, wechat-oa-reader, or wants to scrape/extract data from WeChat articles. Do NOT use for general web scraping unrelated to WeChat Official Accounts.
---

# wechat-oa-reader

Operate the `wechat-oa-reader` Python library to search WeChat Official Accounts, list articles, and fetch full article content — directly from Claude.

## Workflow

Every interaction follows this sequence. Do not skip steps.

### Step 1: Check installation

Run `scripts/check_install.py` to verify the library is installed. If not, it will auto-install via pip.

```bash
python <skill-path>/scripts/check_install.py
```

If installation fails, tell the user to install manually: `pip install wechat-oa-reader`

### Step 2: Check authentication

Run `scripts/check_auth.py` to check credential status.

```bash
python <skill-path>/scripts/check_auth.py
```

The script outputs JSON with a `status` field:
- `"valid"` — credentials exist and not expired, proceed to Step 3
- `"expired"` — credentials exist but expired, go to login
- `"missing"` — no credentials found, go to login

### Step 3: Login (if needed)

If credentials are missing or expired, run the login script:

```bash
python <skill-path>/scripts/login.py
```

This will:
1. Start the QR code login flow
2. Save a QR code PNG to a temp file
3. Print the file path

Tell the user: "Please open the QR code image at `<path>` and scan it with WeChat. I'll wait for you to complete the scan."

The script blocks until the scan is complete, then saves credentials to `.env` in the current directory.

If the user already has token/cookie, they can use manual mode:

```bash
python <skill-path>/scripts/login.py --manual --token TOKEN --cookie COOKIE
```

### Step 4: Execute the requested operation

Based on what the user asks for, run the appropriate script:

**Search for accounts:**
```bash
python <skill-path>/scripts/search.py "公众号名称" [--count 5]
```
Outputs a table of matching accounts with nickname, fakeid, and alias.

**List articles:**
```bash
python <skill-path>/scripts/list_articles.py FAKEID [--count 10] [--offset 0] [--keyword KEYWORD]
```
Outputs a table of articles with title, date, and link.

**Fetch article content:**
```bash
python <skill-path>/scripts/fetch_article.py URL [--format text|json] [--output FILE]
```
Default format is `text` (plain text). Use `--format json` for structured output with title, author, images, HTML, and plain text.

**Batch fetch:**
```bash
python <skill-path>/scripts/fetch_article.py --batch urls.txt [--format json] [--output FILE]
```
Reads URLs from a file (one per line) and fetches all articles.

## Output formatting

- **Search results and article lists**: Present as a markdown table to the user
- **Article content (text)**: Show the plain text directly
- **Article content (json)**: Show structured data or save to file as requested
- **Errors**: Show the error message and suggest next steps

## Common workflows

**"帮我搜索某个公众号的最新文章":**
1. check_install → check_auth → search → list_articles → fetch_article

**"抓取这篇公众号文章":**
1. check_install → check_auth → fetch_article (with the URL)

**"批量下载某公众号的文章":**
1. check_install → check_auth → search → list_articles → save URLs → batch fetch

## Important notes

- All scripts use UTF-8 output encoding, avoiding Windows GBK issues
- Token expires after ~4 days; if operations fail with auth errors, re-run login
- Rate limiting is built into the library (10 req/min, 3s between articles) — do not add extra delays
- The `.env` file contains credentials and should not be committed to git
