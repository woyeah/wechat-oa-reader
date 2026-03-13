# wechat-oa-reader — Product Requirements Document

## 产品定位

**名称**：wechat-oa-reader
**类型**：Python 库 + CLI 工具
**一句话**：可 `pip install` 的微信公众号文章读取库，提供公众号搜索、文章列表、内容抓取的 Python API 和命令行工具。

## 目标用户

- 需要定期从微信公众号获取数据的 Python 开发者
- 有自建数据 pipeline 需求的项目（如行业数据分析）

## 核心能力

1. **扫码登录**：通过微信公众号后台扫码认证，获取 token/cookie
2. **搜索公众号**：按名称搜索公众号，获取 fakeid
3. **文章列表**：按 fakeid 拉取文章列表（支持分页、关键词搜索）
4. **内容抓取**：获取单篇/批量文章完整内容（HTML + 纯文本 + 图片列表）
5. **本地缓存**（可选）：SQLite 缓存已抓取的文章

## 不做

- 不做 Web 界面
- 不做图片代理服务
- 不做 RSS 输出
- 不绕过微信安全机制（扫码认证是合法路径）

## 技术约束

- **许可证**：AGPL-3.0（上游项目要求）
- **Python**：>= 3.10
- **API 风格**：全 async
- **CLI**：click
- **反检测**：curl_cffi (Chrome TLS 指纹) + 可选代理池

## 上游

基于 [tmwgsicp/wechat-download-api](https://github.com/tmwgsicp/wechat-download-api)（AGPL-3.0）重构。
