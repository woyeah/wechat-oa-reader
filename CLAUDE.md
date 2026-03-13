# wechat-oa-reader — 微信公众号文章读取 Python 库

## 工作规则

- **任何代码修改或生成，必须通过 Codex 完成**（不直接用 Edit/Write 工具写代码）
- Codex 默认配置：model=`gpt-5.3-codex`，sandbox=`workspace-write --full-auto`
- 大型 prompt 写入 txt 文件，用 stdin 传入：`codex exec --model gpt-5.3-codex --full-auto --skip-git-repo-check --sandbox workspace-write - < prompt.txt 2>/dev/null`
- **Codex Windows**：bash 下可直接运行（winpty 反而找不到）
- **Context 超过 50% 时，必须询问用户是否需要执行 `/compact`**
- **CLAUDE.md 须保持在 100 行以内**
- **实现前先确认计划**：非 trivial 改动先列 ≤5 条计划，等用户确认后再动手

## 项目概述

Fork 自 [wechat-download-api](https://github.com/tmwgsicp/wechat-download-api)（AGPL-3.0），改造为可 `pip install` 的 Python 库。提供微信公众号文章的搜索、列表、内容抓取能力。

**核心用途**：让 newfeather 项目能够自动抓取唐贸羽绒城公众号的羽绒价格数据。

## 技术栈

- Python 3.12, httpx, curl_cffi（TLS 指纹模拟）, python-dotenv
- 可选依赖：sqlite3（文章缓存）
- **不依赖** FastAPI/uvicorn（纯库，非服务）

## 项目结构

```
src/wechat_oa_reader/
├── __init__.py     # 导出 WeChatClient, WeChatAuth
├── client.py       # WeChatClient（搜索/列表/内容/批量）
├── auth.py         # WeChatAuth（扫码登录 + 凭证管理）
├── http.py         # HTTP 客户端（curl_cffi + proxy pool）
├── parser.py       # 文章 HTML 解析
├── proxy.py        # 代理池轮转
├── limiter.py      # 限频器
├── store.py        # SQLite 存储（可选）
└── poller.py       # 后台轮询（可选）
cli/__main__.py     # CLI 工具
```

## 原项目源码参考

`C:\Users\PC-MOD\AppData\Local\Temp\wechat-download-api\` — 已 clone 到本地

## 关键约定

- **许可证**：AGPL-3.0（继承自上游，不可更改）
- **编辑含中文文件后确保 UTF-8 编码**
- **Python 包管理**：统一用 `uv pip install`

## 环境

- Windows，Python `.venv/Scripts/python.exe`
- Git Bash

## 测试

```bash
PYTHONPATH=. .venv/Scripts/python.exe -m pytest tests/ -v
```

## 微信 API 端点

- 登录：`https://mp.weixin.qq.com/cgi-bin/bizlogin`
- 二维码：`https://mp.weixin.qq.com/cgi-bin/scanloginqrcode`
- 搜索公众号：`https://mp.weixin.qq.com/cgi-bin/searchbiz`
- 文章列表：`https://mp.weixin.qq.com/cgi-bin/appmsgpublish`
