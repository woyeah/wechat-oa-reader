# wechat-oa-reader — 微信公众号文章读取 Python 库

## 工作规则

- **任何代码修改或生成，必须通过 Codex 完成**（不直接用 Edit/Write 工具写代码）
- Codex 命令：`codex exec --model gpt-5.3-codex --full-auto --skip-git-repo-check --sandbox workspace-write - < prompt.txt 2>/dev/null`
- **Codex Windows**：bash 下可直接运行（winpty 反而找不到）
- **Context 超过 50% 时，必须询问用户是否需要执行 `/compact`**
- **CLAUDE.md 须保持在 100 行以内**
- **实现前先确认计划**：非 trivial 改动先列 ≤5 条计划，等用户确认后再动手
- **TDD**：先写测试，再写实现

## 项目概述

基于 [wechat-download-api](https://github.com/tmwgsicp/wechat-download-api)（AGPL-3.0）重构为可 `pip install` 的 async Python 库。
**核心用途**：让 newfeather 项目自动抓取微信公众号的羽绒价格数据。

## 技术栈

- Python >=3.10, httpx, curl_cffi（Chrome TLS 指纹）, pydantic v2, click, python-dotenv
- 可选：sqlite3（文章缓存 ArticleStore）
- **不依赖** FastAPI/uvicorn（纯库 + CLI）

## 项目结构

```
src/wechat_oa_reader/
├── __init__.py     # 公开 API 导出
├── models.py       # Pydantic 数据模型
├── client.py       # WeChatClient（搜索/文章列表/内容抓取）
├── auth.py         # 扫码登录 + 凭证存取（.env）
├── fetcher.py      # HTTP 抓取（curl_cffi + httpx 降级 + 代理轮转）
├── parser.py       # HTML 解析（正文/图片/纯文本）
├── proxy.py        # 代理池（轮转 + 失败冷却）
├── limiter.py      # 异步限频器（滑动窗口）
├── store.py        # SQLite 文章缓存
└── cli.py          # Click CLI（wechat-oa 命令）
```

## 关键文档

- PRD：`docs/PRD.md`
- 技术规格：`docs/TECH_SPEC.md`

## 关键约定

- **许可证**：AGPL-3.0（继承自上游）
- **全 async**：API 均为 async，CLI 用 `asyncio.run()` 调用
- **无单例/无 env 依赖**：核心模块通过构造函数注入配置
- **编辑含中文文件后确保 UTF-8 编码**（Codex 有时输出带 BOM，须检查）

## 安装与测试

```bash
pip install -e ".[dev]"          # 安装（含 pytest）
python -m pytest tests/ -v       # 运行测试（67 tests）
```

## CLI

```bash
wechat-oa login [--manual --token X --cookie Y]
wechat-oa search "公众号名"
wechat-oa articles FAKEID [-n 10]
wechat-oa fetch URL [-o file] [--text] [--batch file]
wechat-oa status
wechat-oa --version
```

## 微信 API 端点

- 登录：`mp.weixin.qq.com/cgi-bin/bizlogin`（startlogin → login）
- 二维码：`mp.weixin.qq.com/cgi-bin/scanloginqrcode`（getqrcode → ask）
- 搜索：`mp.weixin.qq.com/cgi-bin/searchbiz`
- 文章列表：`mp.weixin.qq.com/cgi-bin/appmsgpublish`
- Token 有效期 ~4 天，凭证存 `.env`

## 上游参考

`C:\Users\PC-MOD\AppData\Local\Temp\wechat-download-api\` — 已 clone
