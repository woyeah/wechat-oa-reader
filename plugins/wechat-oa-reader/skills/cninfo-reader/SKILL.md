---
name: cninfo-reader
description: Fetch 上市公司定期报告 (年报/半年报/一季报/三季报) from 巨潮资讯网 (cninfo.com.cn) — the official disclosure platform for Chinese listed companies (沪市/深市/北交所). Use this skill when the user mentions 巨潮, cninfo, 年报, 半年报, 季报, 定期报告, A股年报, 上市公司年报, or asks to download/scrape annual reports of Chinese listed companies. Do NOT use for WeChat Official Account tasks (use wechat-oa-reader), Knowledge Planet tasks (use zsxq-reader), or Weibo tasks (use weibo-reader).
---

# cninfo-reader

Fetch periodic reports (annual / semi-annual / quarterly) of any A-share listed company on the Shanghai, Shenzhen, or Beijing Stock Exchange.

**No authentication required** — cninfo is the official public disclosure platform, all data is open.

## Workflow

### Step 1: Find the stock

```bash
python <skill-path>/scripts/search_company.py "公司名 or 股票代码"
```

Returns matching listed companies as JSON, including `code`, `org_id`, `plate` (`szse`/`sse`/`bj`), and `name`.

Use 6-digit stock code if you know it (most reliable), otherwise search by Chinese name or pinyin.

### Step 2: List periodic reports

```bash
python <skill-path>/scripts/list_reports.py CODE --type TYPE [options]
```

`--type` is required, one of:
- `annual` → 年度报告
- `semiannual` → 半年度报告
- `q1` → 第一季度报告
- `q3` → 第三季度报告

Optional:
- `--org-id ORGID` — Skip the auto-resolution lookup (faster if you already have it from Step 1)
- `--plate szse|sse|bj` — Skip the auto-resolution lookup
- `--since 2020-01-01 --until 2025-12-31` — Date range filter
- `--page 1 -n 30` — Pagination

Example:
```bash
# 平安银行最近的年报
python scripts/list_reports.py 000001 --type annual

# 贵州茅台 2020 年以来的半年报
python scripts/list_reports.py 600519 --type semiannual --since 2020-01-01

# 北交所七丰精工的一季报
python scripts/list_reports.py 873169 --type q1
```

Output is JSON with an `items` array, each item carrying `title`, `time` (ISO datetime), `adjunct_url` (the PDF path), and `adjunct_size` (KB).

### Step 3: Download a specific report

```bash
python <skill-path>/scripts/download_report.py ADJUNCT_URL [-o output.pdf]
```

Pass the `adjunct_url` from Step 2 (e.g. `finalpage/2025-03-15/1222806505.PDF`) — the script prefixes `http://static.cninfo.com.cn/` automatically. Full `http://static.cninfo.com.cn/...` URLs are also accepted (SSRF guard rejects other hosts).

Without `-o`, the file is saved with the basename from the URL.

## Output formatting

- For `search_company`: present results as a markdown table with columns `code | name | plate | org_id`.
- For `list_reports`: present items as a markdown table with `date | title | size (KB) | adjunct_url`. Mention `has_more` if more pages exist.
- For `download_report`: report the saved path and size.

## Common workflows

**"帮我下载平安银行最新年报"**
1. `list_reports.py 000001 --type annual -n 5` → pick the top non-摘要 entry
2. `download_report.py <its adjunct_url> -o 平安银行2024年报.pdf`

**"贵州茅台过去三年的所有定期报告"**
1. For each type in `[annual, semiannual, q1, q3]`: `list_reports.py 600519 --type <type> --since 2022-01-01 --until 2025-12-31`
2. Aggregate and present to the user

**"我想看某只北交所股票的年报"**
1. `search_company.py "公司名"` → get code + org_id + plate
2. `list_reports.py CODE --type annual --plate bj --org-id ORGID`

## Important notes

- **No login required.** No cookies, no token, no `.env` file. Just run the scripts.
- **Be polite with rate.** cninfo is a public service — don't hammer it. The default per-script call rate is fine.
- **PDF size matters.** Annual reports are typically 1–10 MB; the `adjunct_size` field is in KB.
- **报告摘要 vs full report**: Most companies publish a brief 摘要 PDF alongside the full report. Look at the `title` to distinguish (e.g. "2024年年度报告摘要" vs "2024年年度报告").
- **delisted companies** still have their historical disclosures available — the `delisted` flag from `search_company` is informational only.
- **北交所 codes** start with `43`, `83`, `87`, `88`, or `89`. The script infers `plate=bj` automatically from the code.

## CLI Alternative

If `wechat-oa-reader` is installed (`pip install wechat-oa-reader` or `uv pip install -e .`), CLI commands are available:

```bash
wechat-oa cninfo search "平安银行"
wechat-oa cninfo reports 000001 --type annual --since 2020-01-01
wechat-oa cninfo download finalpage/2025-03-15/X.PDF -o report.pdf
```

The CLI is a thin wrapper around the same `CninfoClient` class in `src/wechat_oa_reader/cninfo.py`. Use it interchangeably with the scripts above.
