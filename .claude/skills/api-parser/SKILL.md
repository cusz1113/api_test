---
name: 接口文档解析器
slug: api-parser
version: 2.0.0
description: 解析多种格式的接口文档（OpenAPI、Swagger、YApi、Postman、HAR、cURL），统一输出为标准JSON格式，确保接口全覆盖。
metadata: {"emoji":"📄","requires":{"bins":[]}}
---

## 使用场景

用户需要：
- 解析接口文档（URL或本地文件）
- 从 Swagger/OpenAPI/YApi/Postman/HAR/cURL 中提取全部接口
- 统一接口数据格式，用于测试或文档管理

## 核心规则

### 1. 输入与输出
- **输入：** 接口文档URL（http/https）或本地文件路径（.json/.yaml/.yml/.har/.txt）
- **输入文件路径：** `docx/{项目名}/`（原始接口文档存放位置）
- **输出目录：** `output/{项目名}/api_parser/`
  - `api-spec.json` — 统一数据格式（机器消费）
  - `api-spec-summary.md` — 审阅摘要（人阅读）
- 项目名由用户指定或从文档名自动提取
- 目录不存在时自动创建
- **自动识别** 来源类型（openapi/swagger/yapi/postman/har/curl）；用户可通过 `--source-type` 手动指定

### 2. 全量覆盖
- 文档中的**每个接口**都必须被提取，不得遗漏
- 解析完成后，对比原文档接口总数
- 发现差异时必须先报告再继续

### 3. 解析流程
1. 读取 `references/数据格式.md` 了解统一输出格式
2. 读取 `references/解析规则.md` 了解各来源的解析策略
3. 逐个解析所有接口，转为统一格式
4. 按解析规则中的校验清单逐项验证
5. 使用 `references/摘要模板.md` 生成摘要
6. 展示摘要，等待用户确认

### 4. 引用展开
- 所有 Schema 引用（$ref）必须就地展开为完整定义
- 保留 `schema_ref` 字段记录原始引用名称
- 循环引用处理：最大递归深度10，超出则标记

### 5. 鉴权检测
- 从 security 定义和请求头自动推断鉴权方式
- 每个接口都必须有 `auth` 字段
- 未指定鉴权时默认为 `none`

### 6. 智能默认值
- 缺少 `name` → 从 method + path 自动生成
- 缺少 `description` → 设为空字符串
- 缺少 `tags` → 归为 "未分类"
- 缺少 `example` → 根据 schema 默认值生成

## 参考文档

| 主题 | 文件 |
|------|------|
| 统一数据格式定义 | `references/数据格式.md` |
| 各来源解析规则 | `references/解析规则.md` |
| 摘要生成模板 | `references/摘要模板.md` |
