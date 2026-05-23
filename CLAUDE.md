# API Test — AI 驱动的接口自动化测试智能体

## 项目概述

基于 Claude Code Skill 系统的全链路接口自动化测试项目。从接口文档解析到业务流分析、用例生成、执行、报告输出，全流程由大模型驱动。不使用传统脚本生成的硬编码用例，而是让 AI 理解接口定义后智能构造测试数据、分析响应语义、判断测试结果。

**技术栈：** Python 3.12

**目录约定：**
- 原始接口文档：`docx/{项目名}/`
- 全部产出：`output/{项目名}/`

## 完整流水线

```
docx/{项目名}/   → 原始接口文档存放位置

api-parser        → 解析接口文档，输出 api-spec.json + api-spec-summary.md → output/{项目名}/api_parser/
    ↓
api-flow          → 分析依赖关系，串联业务流，输出 api_flow.json + api_flow.md → output/{项目名}/api_flow/
    ↓
api-flow-patch    → 手动补充遗漏的业务流（可选）
    ↓
api-case-gen      → 逐业务流生成测试用例，输出 test_cases.json → output/{项目名}/api_cases/
api-case-gen-single → 逐接口生成参数级用例（正向+异常），输出 single/*.json → output/{项目名}/api_cases/single/
    ↓
api-runner        → AI 驱动执行业务流用例，飞书卡片实时进度 → output/{项目名}/api_report/
api-runner-single → 执行单接口用例（setup_steps + test_steps 两阶段） → output/{项目名}/api_report/single/
    ↓
api-report-html   → 深色科技风 HTML 报告，自动检测格式
```

辅助工具：**captcha-recognizer**（图鉴验证码识别）、**mineru**（文档提取）

## 工作流控制

**铁律：每完成一个流水线步骤后必须停止，展示产出摘要并等待用户确认，用户确认后方可继续下一步。**

例如：
- api-parser 完成 → 展示 `api-spec-summary.md`，等待用户确认 → 用户确认后执行 api-flow
- api-flow 完成 → 展示 `api_flow.md` + 覆盖率，等待用户确认 → 用户确认后执行 api-case-gen / api-case-gen-single
- api-case-gen 完成 → 展示 `test_cases_summary.md`，等待用户确认 → 用户确认后执行 api-runner / api-runner-single
- api-runner 完成 → 展示报告摘要，等待用户确认 → 用户确认后执行 api-report-html

**禁止：** 未经用户确认连续执行多个步骤，或用户要求执行 A 时自动连带执行 B/C/D。

## Skill 详情

### 1. api-parser — 接口文档解析器（v2.0.0）

读取 `docx/{项目名}/` 下的接口文档（URL 或本地文件），解析 6 种格式：OpenAPI 3.x / Swagger 2.0 / YApi / Postman / HAR / cURL → 统一的 `api-spec.json`。

**核心规则：**
- 所有 `$ref` 引用必须就地展开为完整定义，保留 `schema_ref` 记录原始引用名
- 请求体和响应体全部扁平化：去掉嵌套 schema 层，字段的 `required` 标记在字段自身
- 每个接口都必须有 `auth` 字段（none/bearer/api_key/basic/oauth2/custom），从 security 定义或请求头推断
- 缺少 name → 从 method + path 自动生成；缺少 tags → 归为"未分类"
- 解析完成后必须对比原文档接口总数，确保全量覆盖

**输出：** `output/{项目名}/api_parser/api-spec.json` + `api-spec-summary.md`

### 2. api-flow — 业务流分析器（v2.0.0）

从 `api-spec.json` 分析接口调用关系，四阶段分析：

1. **Phase 1 逐接口分析：** 认证需求、资源依赖（外键识别）、产出资源、约束识别、测试关注点
2. **Phase 2 依赖图谱：** 外键依赖、认证依赖、顺序依赖、共享资源
3. **Phase 3 串联业务流：** CRUD 模式、关联管理模式、执行+结果模式、认证流程模式、公共步骤抽取
4. **Phase 4 异常场景：** 鉴权/参数校验/边界值/唯一约束/业务规则/安全，覆盖率校验必须 100%

**v2.0 关键变更：** 每个步骤必须从 api-spec.json 嵌入完整的接口文档信息（request_body、response、query_params、path_params 等），用例生成器可直接使用，无需回查 api-spec。

**铁律：** response.status_code 必须严格从 api-spec 读取，不得推测。

**输出：** `output/{项目名}/api_flow/api_flow.json` + `api_flow.md`

### 3. api-flow-patch — 业务流补充器（v1.0.0）

用户手写 MD 或口述业务流 → 匹配 api-spec 中的接口 → 去重判断 → 补充到 `api_flow.json`。只追加不删除，不修改已有流程。

### 4. api-case-gen — 业务流用例生成器（v3.1.0）

**不使用任何脚本代码生成用例。** 每条业务流由 AI 独立生成一条正向用例。

**铁律：** 所有字段必须从业务流步骤中嵌入的接口文档获取，不得推测、编造。

**三维度质量检测（每条用例生成后立即执行）：**
- **维度一 数据引用错误：** 变量引用步骤号 < 当前步骤号、extract 变量存在性、extract 路径在 response.fields 中存在
- **维度二 断言规则正确性：** status_code 与文档一致、body_fields 字段名存在、204 无 body_fields
- **维度三 编造数据检测：** body 无额外字段、必填字段不遗漏、类型正确、Content-Type 一致、params/headers 无编造

**常见陷阱：** verify 接口也要传 body、token 接口可能是 form-urlencoded、status_code 不总为 200、extract 字段名从 response.fields 读取。

**输出：** `output/{项目名}/api_cases/test_cases.json` + `test_cases_summary.md`

### 5. api-case-gen-single — 单接口用例生成器（v1.0.0）

对 api-spec 中每个接口独立生成全面的参数级用例，包含 setup_steps（前置依赖）+ test_steps（测试场景）。

**前置依赖分析：** 认证依赖 → 外键依赖 → 业务前置，递归构建依赖图谱（最大深度 5），公共前置缓存复用。

**测试场景覆盖（11 种）：** positive / missing_required / wrong_type / format_error / boundary / unique_conflict / not_found / unauthorized / forbidden / sql_injection / xss

**文件命名：** `{method}_{path去掉前导斜杠并将/替换为_}.json`

**输出：** `output/{项目名}/api_cases/single/` 目录下每个接口一个 JSON 文件 + `single_index.json` + `single_cases_summary.md`

### 6. api-runner — 业务流用例执行器（v1.1.0）

**AI 全权驱动**执行循环：
- **请求构造：** 大模型理解接口定义 + 业务流上下文 → 生成具有业务语义的请求数据（禁止简单字符串替换 `{{}}` 模板）
- **L1 基础断言：** Python 脚本机械判断 status_code + body_fields
- **L2 智能断言：** 调用大模型分析响应语义是否与步骤预期行为一致（禁止硬编码 if/else 规则）

**进度：** 飞书卡片实时更新，每完成一个 step 刷新一次。L1+L2 都通过才算 PASS。

**输出：** `output/{项目名}/api_report/{timestamp}_report.json` + `_summary.md`

### 7. api-runner-single — 单接口用例执行器（v1.0.0）

与 api-runner 类似的 AI 驱动执行，关键差异：
- 两阶段编排：setup_steps 先执行 → test_steps 逐个执行
- 公共前置缓存：相同 setup_steps 执行一次后缓存变量池复用
- setup_steps 失败 → 该接口所有 test_steps 标记 SKIP
- test_step 失败 → 不影响其他 test_step
- 报告输出：每个接口独立报告 + 汇总报告

**L2 智能断言特别关注：** 异常场景的错误信息语义必须与测试目的匹配（如 `format_error` 用例返回「邮箱已存在」→ FAIL，因为这是唯一约束错误而非格式错误）。

**输出：** `output/{项目名}/api_report/single/`

### 8. api-report-html — HTML 报告生成器（v2.0.0）

自动检测两种报告格式（`cases` 字段 → 业务流格式，`endpoint_results` → 单接口格式），生成深色科技风单文件 HTML。

**视觉差异：** 单接口报告比业务流报告多 setup_steps 区域（灰色左边框 + 🔧 前缀）和 scenario 紫色标签。支持通过/失败过滤、折叠展开、Authorization 脱敏。

### 9. captcha-recognizer — 验证码识别器（v2.0.0）

使用图鉴（ttshitu）API，支持数英混合/纯数字/中文/计算题/拖动拼图/缺口识别。可通过命令行或 Python 函数调用。

### 10. mineru — 文档提取器

通过 MinerU API 将 PDF/图片/网页转为 Markdown/HTML/LaTeX/DOCX。支持免登录 flash-extract（限 10MB/20 页）和需 token 的 extract（支持表格/公式识别）。

## 项目约定

### 变量体系

| 变量 | 说明 |
|------|------|
| `{{base_url}}` | API 基础地址 |
| `{{random_username}}` / `{{random_email}}` / `{{random_mobile}}` | 随机生成，每次唯一 |
| `{{random_string_4}}` / `{{random_string_8}}` | 随机字符串，用于去重 |
| `{{N.extract.xxx}}` | 引用第 N 步提取的变量 |

### 数据传递

- 步骤间数据通过 `input_vars` / `output_vars` 流转
- 前置步骤响应通过 JSONPath 提取变量（如 `$.id`、`$.token`），后续步骤用 `{{N.extract.xxx}}` 引用

### 文件命名约定

- api-parser 输出：`api-spec.json`
- api-flow 输出：`api_flow.json` / `api_flow.md`
- api-case-gen 输出：`test_cases.json`
- api-case-gen-single 输出：`{METHOD}_path_to_endpoint.json`
- api-runner 输出：`{YYYYMMDD_HHmmss}_report.json` + `_summary.md`
- api-runner-single 输出：`{timestamp}_single_summary.json`

### 目录结构

```
docx/{项目名}/                        ← 原始接口文档
└── (OpenAPI/Swagger/YApi/Postman/HAR/cURL 文件)

output/{项目名}/                       ← 全部产出
├── api_parser/
│   ├── api-spec.json
│   └── api-spec-summary.md
├── api_flow/
│   ├── api_flow.json
│   └── api_flow.md
├── api_cases/
│   ├── test_cases.json
│   ├── test_cases_summary.md
│   └── single/
│       ├── POST_api_users_register.json
│       ├── ...
│       ├── single_index.json
│       └── single_cases_summary.md
└── api_report/
    ├── {timestamp}_report.json
    ├── {timestamp}_summary.md
    ├── {timestamp}_report.html
    └── single/
        ├── POST_api_users_register_report.json
        ├── {timestamp}_single_summary.json
        └── {timestamp}_single_report.html
```

### 质量检查清单（api-case-gen 使用）

参见 SKILL.md 中的三维度系统性检测规范，核心是：
1. 不编造任何字段 — 所有数据从文档获取
2. 不遗漏必填字段 — required=true 必须全部填入
3. status_code 严格从文档读取 — 不做推测

## 本地开发

本仓库是 Skill 定义的开发仓库。Skills 存放在 `.claude/skills/` 目录下，Claude Code 通过 Skill 工具加载并执行。主流程依赖于 Claude Code 平台托管的能力（飞书消息、大模型调用等），本地仓库主要定义 Skill 的指令和规则。

```bash
# Python 版本
python --version  # 3.12

# 项目依赖（当前为空，各 Skill 自行管理）
# 部分 Skill 需要: pip install requests
```
