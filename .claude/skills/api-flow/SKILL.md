---
name: 接口业务流分析器
slug: api-flow
version: 2.0.0
description: 从 api-spec.json 中分析接口调用关系，串联业务流程，识别异常场景，输出标准化的业务流JSON文件。每个步骤包含完整的接口文档信息。
metadata: {"emoji":"🔄","requires":{"bins":[],"deps":["api-parser"]}}
---

## 使用场景

用户需要：
- 分析项目中接口之间的调用依赖关系
- 串联出完整的业务流程（注册→登录→创建→查询→修改→删除）
- 识别异常测试场景（鉴权失败、参数校验、边界值等）
- 基于业务流生成自动化测试脚本

## 核心规则

### 1. 输入与输出
- **输入：** `api-spec.json`（由 api-parser Skill 产出）
- **输出目录：** `output/{项目名}/api_flow/`
  - `api_flow.json` — 业务流JSON（机器消费）
  - `api_flow.md` — 业务流描述（人阅读）
- 项目名与 api-parser 保持一致，从 api-spec.json 的路径中提取
- 目录不存在时自动创建

### 2. 前置依赖
- 必须先执行 api-parser，产出 `api-spec.json`
- 如果指定目录下不存在 `api-spec.json`，提示用户先解析接口文档

### 3. 四阶段分析

#### Phase 1: 逐接口分析
对每个接口独立分析：
- **认证需求**：是否需要 token，影响流程编排
- **资源依赖**：哪些字段是外键（如 project_id、suite_id），需要前置创建
- **产出资源**：该接口执行后会产出什么（如创建后返回 id）
- **唯一约束**：哪些字段不能重复（如 username、email）
- **格式约束**：哪些字段有格式要求（如 email、mobile）
- **测试关注点**：这个接口单独测试时需要验证什么

#### Phase 2: 依赖图谱
分析接口间的依赖关系：
- **外键依赖**：哪些接口引用了其他资源（project_id → 项目接口）
- **认证依赖**：哪些接口需要先登录获取 token
- **顺序依赖**：哪些操作必须按先后顺序执行（创建→查询→修改→删除）
- **共享资源**：哪些流程需要相同的前置数据

#### Phase 3: 串联业务流
将相关接口串联为完整业务流程：
- 按业务模块分组（用户认证、项目管理、测试执行等）
- 每条流程包含完整生命周期（创建→使用→验证→清理）
- 步骤间通过 `input_vars` / `output_vars` 传递数据
- 流程末尾必须清理创建的测试数据
- 同一步骤被多个流程使用时，抽取为公共步骤（如登录）

#### Phase 4: 异常场景 + 覆盖率校验
- **鉴权异常**：未认证访问、无效 Token、Token 过期
- **参数校验**：缺少必填字段、类型错误、格式错误
- **边界值**：不存在的 ID、超长字符串、负数页码、超大分页
- **唯一约束**：重复用户名、重复项目名
- **业务规则**：密码不一致、级联删除
- **安全性**：SQL 注入、XSS 注入
- **覆盖率校验**：所有业务流 + 异常场景必须覆盖 100% 的接口

### 4. 流程步骤格式（v2.0 — 含接口文档详情）

> ⚠️ **每个步骤必须包含完整的接口文档信息，从 api-spec.json 中直接提取嵌入。**
> 目的：用例生成器（api-case-gen）可以直接从业务流中获取所有接口信息，无需回查 api-spec.json。

每个步骤包含：
```json
{
  "name": "登录",
  "method": "POST",
  "path": "/api/users/login",
  "requires_auth": false,
  "input_vars": {"username": "1.username", "password": "1.password"},
  "output_vars": ["token"],
  "request_example": {"username": "testuser", "password": "Test@123456"},
  "params": {"page": 1},
  "note": "可选备注",

  "endpoint_id": "login_api_users_login_post",
  "endpoint_name": "用户登录",
  "description": "用户登录获取token",
  "tags": ["用户管理"],

  "request_body": {
    "fields": [
      {"name": "username", "type": "string", "required": true, "description": "用户名"},
      {"name": "password", "type": "string", "required": true, "description": "密码"}
    ]
  },
  "query_params": [],
  "path_params": [],
  "required_headers": [],
  "content_type": "application/json",

  "response": {
    "status_code": 200,
    "description": "Successful Response",
    "fields": [
      {"name": "token", "type": "string", "required": true, "description": "JWT Token"},
      {"name": "user", "type": "object", "required": true, "description": "用户信息",
       "children": [
        {"name": "id", "type": "integer", "required": true},
        {"name": "username", "type": "string", "required": true}
       ]}
    ],
    "example": {
      "token": "eyJhbGciOiJIUzI1NiIs...",
      "user": {"id": 1, "username": "testuser"}
    }
  },
  "error_responses": [
    {"status_code": 422, "description": "Validation Error"}
  ]
}
```

#### 字段说明

| 字段 | 必填 | 说明 |
|------|------|------|
| name | ✅ | 步骤名称 |
| method | ✅ | HTTP 方法 |
| path | ✅ | 接口路径 |
| requires_auth | ✅ | 是否需要认证 |
| input_vars | ❌ | 输入变量映射（`"步骤号.变量名"` 引用前置步骤产出） |
| output_vars | ❌ | 本步骤产出的变量名列表 |
| request_example | ❌ | 请求体示例（可含 `{{变量}}` 占位符） |
| params | ❌ | 查询参数示例 |
| note | ❌ | 备注说明 |
| **endpoint_id** | ✅ | api-spec.json 中接口的唯一标识 |
| **endpoint_name** | ✅ | 接口名称 |
| **description** | ❌ | 接口描述 |
| **tags** | ❌ | 接口标签 |
| **request_body** | ✅ | 请求体字段定义（从 api-spec 复制） |
| **request_body.fields** | ✅ | 请求体字段列表，含 name/type/required/description |
| **query_params** | ✅ | 查询参数定义（从 api-spec params.query 复制） |
| **path_params** | ✅ | 路径参数定义（从 api-spec params.path 复制） |
| **required_headers** | ✅ | 必需的请求头（从 api-spec required_headers 复制） |
| **content_type** | ✅ | Content-Type（从 api-spec 推断，默认 application/json） |
| **response** | ✅ | 成功响应定义（从 api-spec response[0] 复制） |
| **response.status_code** | ✅ | 成功响应状态码（**严格从 api-spec 读取**） |
| **response.fields** | ✅ | 响应体字段列表，含 name/type/required/description |
| **response.example** | ❌ | 响应体示例（从 api-spec 复制） |
| **error_responses** | ❌ | 错误响应列表（从 api-spec response[1:] 复制） |

### 5. 接口文档嵌入规则

生成业务流时，**必须从 api-spec.json 中提取以下信息嵌入到每个步骤**：

```
对每个步骤对应的接口：
1. 在 api-spec.json 的 endpoints 中找到匹配的接口（method + path）
2. 提取 endpoint_id、name、description、tags
3. 提取 request_body（所有字段及 required 标记）
4. 提取 params.query（所有查询参数）
5. 提取 params.path（所有路径参数）
6. 提取 required_headers
7. 推断 content_type（检查 request_body 的 media type）
8. 提取 response[0] 作为成功响应（status_code + fields + example）
9. 提取 response[1:] 作为错误响应
10. 将以上信息完整嵌入步骤中
```

**禁止：**
- ❌ 省略字段信息（如只写 method/path 不写 request_body）
- ❌ 简化字段列表（必须包含 api-spec 中的所有字段）
- ❌ 修改 status_code（严格复制 api-spec 中的值）

### 6. 流程变量约定
- `{{random_string_4}}` — 4位随机字符串，用于去重
- `{{random_username}}` — 随机用户名
- `{{random_email}}` — 随机邮箱
- `{{random_mobile}}` — 随机手机号
- `{{global.test_username}}` — 全局测试账号
- `{{N.var}}` — 引用第N步的输出变量

### 7. 输出格式

```json
{
  "project": "项目名",
  "analyzed_at": "ISO8601时间戳",
  "source": "api_parser/api-spec.json",
  "summary": {
    "total_endpoints": 61,
    "total_business_flows": 13,
    "total_edge_cases": 19,
    "coverage": "61/61",
    "coverage_pct": "100%",
    "uncovered": []
  },
  "business_flows": [...],
  "edge_cases": [...]
}
```

### 8. 优先级定义
- **P0**：核心流程，必须覆盖（认证、CRUD、执行）
- **P1**：重要场景，建议覆盖（复制、异常校验）
- **P2**：补充场景，可选覆盖（安全测试、极端边界值）

### 9. 分析流程
1. 确认 `api-spec.json` 存在
2. 读取 `references/输出格式.md` 了解详细输出规范
3. 执行四阶段分析
4. **为每个步骤从 api-spec.json 提取并嵌入完整接口文档信息**
5. 校验覆盖率，未覆盖 100% 时补充流程
6. 保存 `api_flow.json` + `api_flow.md`
7. 展示摘要，等待用户确认

### 10. 质量检查清单（生成后必须逐项验证）

- [ ] 每个步骤都包含 endpoint_id
- [ ] 每个步骤的 response.status_code 与 api-spec 一致
- [ ] 每个步骤的 response.fields 与 api-spec 一致
- [ ] 每个步骤的 request_body.fields 包含所有 required 字段
- [ ] 每个步骤的 query_params 与 api-spec params.query 一致
- [ ] 每个步骤的 required_headers 与 api-spec 一致
- [ ] content_type 与接口实际要求一致（json vs form-urlencoded）
- [ ] 所有接口覆盖率 100%

## 参考文档

| 主题 | 文件 |
|------|------|
| 输出格式详细定义 | `references/输出格式.md` |
| 分析策略与模式库 | `references/分析策略.md` |
