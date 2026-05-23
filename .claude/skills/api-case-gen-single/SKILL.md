---
name: 单接口用例生成器
slug: api-case-gen-single
version: 1.0.0
description: 对 api-spec.json 中的每个接口独立生成全面的参数级测试用例，自动分析前置依赖接口链路并编排 setup_steps。每条用例保存为独立 JSON 文件。用当用户需要"对单个接口生成测试用例"、"测试接口参数校验"、"生成接口异常用例"、"单接口全面测试"时触发。
metadata: {"emoji":"🧪","requires":{"bins":[],"deps":["api-parser"]}}
---

## 使用场景

用户需要：
- 对每个接口独立生成全面的参数级测试用例（正向+异常）
- 自动分析接口的前置依赖链路（如需要先登录获取 token）
- 逐接口生成，每个接口一个独立 JSON 文件
- 覆盖参数校验、边界值、安全测试等场景

## 核心规则

### 1. 输入与输出

- **输入：** `api_parser/api-spec.json`（由 api-parser Skill 产出）
- **可选输入：** 用户指定接口范围（标签、路径关键词、接口列表），不指定则全量
- **输出目录：** `output/{项目名}/api_cases/single/`
  - `POST_api_users_register.json` — 每个接口一个文件
  - `POST_api_users_login.json`
  - `...`
  - `single_index.json` — 索引文件（所有接口用例清单+统计）
  - `single_cases_summary.md` — 用例摘要（人阅读）

项目名从 api-spec.json 的路径中提取，目录不存在时自动创建。

### 2. 前置依赖

- 必须先执行 api-parser，产出 `api-spec.json`
- 如果不存在，提示用户先解析接口文档

### 3. 文件命名规则

`{method}_{path去掉前导斜杠并将/替换为_}.json`

示例：`POST /api/users/register` → `POST_api_users_register.json`

### 4. 用例结构（核心：setup_steps + test_steps）

```json
{
  "target_endpoint": {
    "endpoint_id": "register_api_users_register_post",
    "method": "POST",
    "path": "/api/users/register",
    "name": "用户注册",
    "description": "注册新用户",
    "tags": ["用户管理"]
  },
  "setup_steps": [
    {
      "step_no": 1,
      "name": "注册前置用户",
      "note": "公共前置：确保测试环境中有可用的用户数据",
      "method": "POST",
      "url": "{{base_url}}/api/users/register",
      "headers": { "Content-Type": "application/json" },
      "params": {},
      "body": {
        "username": "{{random_username}}",
        "password": "Test@123456",
        "password_confirm": "Test@123456",
        "email": "{{random_email}}",
        "mobile": "{{random_mobile}}"
      },
      "extract": { "username": "$.username" },
      "assert": { "status_code": 200, "body_fields": { "id": "not_null" } }
    },
    {
      "step_no": 2,
      "name": "登录获取token",
      "note": "公共前置：获取认证token",
      "method": "POST",
      "url": "{{base_url}}/api/users/login",
      "headers": { "Content-Type": "application/json" },
      "params": {},
      "body": {
        "username": "{{1.extract.username}}",
        "password": "Test@123456"
      },
      "extract": { "token": "$.token" },
      "assert": { "status_code": 200, "body_fields": { "token": "not_null" } }
    }
  ],
  "test_steps": [
    {
      "step_no": 3,
      "name": "用户注册-正向",
      "scenario": "positive",
      "method": "POST",
      "url": "{{base_url}}/api/users/register",
      "headers": { "Content-Type": "application/json" },
      "params": {},
      "body": {
        "username": "{{random_username}}",
        "password": "Test@123456",
        "password_confirm": "Test@123456",
        "email": "{{random_email}}",
        "mobile": "{{random_mobile}}"
      },
      "extract": { "id": "$.id", "username": "$.username" },
      "assert": { "status_code": 200, "body_fields": { "id": "not_null", "username": "not_null" } }
    },
    {
      "step_no": 4,
      "name": "用户注册-缺少username",
      "scenario": "missing_required",
      "missing_field": "username",
      "method": "POST",
      "url": "{{base_url}}/api/users/register",
      "headers": { "Content-Type": "application/json" },
      "params": {},
      "body": {
        "password": "Test@123456",
        "password_confirm": "Test@123456",
        "email": "{{random_email}}",
        "mobile": "{{random_mobile}}"
      },
      "extract": {},
      "assert": { "status_code": 422 }
    }
  ],
  "generated_at": "ISO8601时间戳",
  "source": "api_parser/api-spec.json"
}
```

#### 字段说明

| 字段 | 必填 | 说明 |
|------|------|------|
| target_endpoint | ✅ | 目标接口信息（endpoint_id/method/path/name/description/tags） |
| setup_steps | ✅ | 前置依赖链路步骤（可能为空数组，表示无前置依赖） |
| test_steps | ✅ | 目标接口的测试场景步骤（至少包含正向用例） |
| generated_at | ✅ | 生成时间 |
| source | ✅ | 数据来源 |

#### test_steps 专有字段

| 字段 | 必填 | 说明 |
|------|------|------|
| scenario | ✅ | 场景类型：positive/missing_required/wrong_type/format_error/boundary/unique_conflict/not_found/unauthorized/forbidden/sql_injection/xss |
| missing_field | ❌ | 缺少的字段名（scenario=missing_required 时） |
| inject_field | ❌ | 注入的字段名（scenario=sql_injection/xss 时） |

### 5. 前置依赖分析（每个接口生成用例前必须执行）

对目标接口，分析并构建前置依赖链路：

#### 5.1 依赖识别

| 依赖类型 | 识别方式 | 示例 |
|---------|---------|------|
| 认证依赖 | 接口的 `auth` 字段非 none | 需要 token → 前置：登录接口 |
| 外键依赖 | 请求参数/请求体中引用其他资源 ID | `project_id` → 前置：创建项目接口 |
| 业务前置 | 接口要求特定数据状态存在 | 查询接口列表需要先有项目 |
| 唯一约束 | 请求体中有唯一约束字段 | `username` → 使用随机数据 |

#### 5.2 依赖图谱构建

从 api-spec.json 中匹配前置接口：

1. 按 path 关键词 + method 推断匹配
2. 前置接口自身也可能有依赖 → 递归解析，构建完整链路
3. 最大递归深度 5 层，超出则报错
4. 多个目标接口共享相同前置时，识别为公共前置

示例：
```
目标：查询接口列表 (GET /api/interfaces?project_id={id})
  └─ 前置1：创建项目 (POST /api/projects) → 需要 token + 产出 project_id
      └─ 前置2：登录 (POST /api/users/login) → 产出 token
          └─ 前置3：注册 (POST /api/users/register) → 产出 username/password
```

#### 5.3 公共前置缓存

- 分析过程中维护已解析的前置链路缓存
- 后续接口如果需要相同的前置链路（如登录），直接复用，不重新生成
- 在 setup_steps 中标注来源：`"ref": "POST_api_users_login.json.setup_steps[2]"`

#### 5.4 setup_steps 编排规则

- 步骤按依赖拓扑序排列（被依赖的在前）
- 每个步骤包含完整的 url/headers/params/body/extract/assert
- 步骤间通过 `{{N.extract.xxx}}` 传递变量
- extract 只提取后续步骤需要引用的变量

### 6. 测试场景覆盖

每个目标接口的 test_steps 覆盖以下场景：

| 场景 | scenario 值 | 数量 | 说明 |
|------|------------|------|------|
| 正向用例 | `positive` | 1 | 所有 required 字段传合法值 |
| 缺少必填字段 | `missing_required` | N（每个 required 字段一条） | 逐个去掉每个 required 字段 |
| 参数类型错误 | `wrong_type` | 按需 | string→数字、integer→字符串、boolean→字符串 |
| 格式校验 | `format_error` | 按需 | email/mobile/url 格式错误 |
| 边界值 | `boundary` | 按需 | 空字符串、超长字符串、最小值、最大值、0、负数 |
| 唯一约束冲突 | `unique_conflict` | 按需 | 重复已有数据 |
| 不存在的资源 | `not_found` | 按需 | 引用不存在的 ID |
| 未认证访问 | `unauthorized` | 0或1 | auth 非 none 的接口：不带 token 访问 |
| 无权限访问 | `forbidden` | 0或1 | 需要特定角色的接口：用低权限 token 访问 |
| SQL注入 | `sql_injection` | 按需 | 字符串字段注入 `1' OR 1=1--` |
| XSS注入 | `xss` | 按需 | 字符串字段注入 `<script>alert(1)</script>` |

**安全场景（SQL注入、XSS）默认生成，用户可通过参数关闭。**

**场景生成判断规则：**
- GET/DELETE 无 request_body 的接口 → 跳过 body 相关场景（missing_required/wrong_type/boundary 等）
- auth 为 none 的接口 → 跳过 unauthorized/forbidden
- 无唯一约束字段的接口 → 跳过 unique_conflict
- 无外键 ID 参数的接口 → 跳过 not_found（资源不存在场景）
- request_body 中无字符串字段的接口 → 跳过 format_error/sql_injection/xss

### 7. 字段生成规则（严格模式）

> ⚠️ **铁律：所有字段信息必须从 api-spec.json 中获取，不得推测、编造。**

#### 7.1 url 生成
- `{{base_url}}` + 目标接口 path
- 路径参数替换为前置步骤变量引用

#### 7.2 headers 生成
- Content-Type：从目标接口 content_type 读取
- Authorization：requires_auth 时添加 `Bearer {{N.extract.token}}`
- required_headers 中的其他 header

#### 7.3 params 生成
- 从 query_params 读取所有 required 参数
- 值取变量引用或合理默认值

#### 7.4 body 生成（正向用例）
- 从 request_body.fields 读取所有字段
- required 字段全部填入
- 值优先级：request_example > 变量引用 > 合理默认值

#### 7.5 body 生成（异常用例）
- **missing_required：** 在正向 body 基础上，删除指定字段
- **wrong_type：** 在正向 body 基础上，将目标字段的值改为错误类型
- **format_error：** 在正向 body 基础上，将目标字段的值改为格式错误的值
- **boundary：** 在正向 body 基础上，将目标字段的值改为边界值
- **unique_conflict：** 使用 setup_steps 中已创建的重复数据
- **not_found：** 将外键 ID 字段改为 999999
- **sql_injection：** 将目标字符串字段改为 `1' OR 1=1--`
- **xss：** 将目标字符串字段改为 `<script>alert(1)</script>`
- **unauthorized：** 不带 Authorization header

#### 7.6 extract 生成
- 从 response.fields 中提取后续 test_steps 需要的变量
- 正向用例提取完整变量（id、token 等）
- 异常用例通常 extract 为空对象 `{}`

#### 7.7 assert 生成
- **正向用例：** status_code 从 response.status_code 严格读取 + required body_fields not_null
- **异常用例：** status_code 断言期望的错误码（422/401/403/404/500），body_fields 通常为空
- 204 接口：不生成 body_fields

### 8. 变量体系

与 api-case-gen 共用：

| 变量 | 说明 |
|------|------|
| `{{base_url}}` | API 基础地址 |
| `{{random_username}}` | 随机用户名（8位） |
| `{{random_email}}` | 随机邮箱 |
| `{{random_mobile}}` | 随机手机号 |
| `{{random_string_4}}` | 4位随机字符串 |
| `{{random_string_8}}` | 8位随机字符串 |
| `{{N.extract.xxx}}` | 引用第 N 步提取的变量 |

### 9. 生成流程

#### Step 1: 准备
1. 读取 `api_parser/api-spec.json`
2. 提取所有接口列表（endpoints）
3. 如果用户指定了接口范围，过滤列表
4. 创建输出目录 `api_cases/single/`
5. 发送飞书进度卡片

#### Step 2: 遍历接口，逐个生成
```
对每个接口 endpoint（按顺序）：
  1. 分析前置依赖链路
     - 检查公共前置缓存，复用已解析的链路
     - 新链路 → 从 api-spec.json 匹配前置接口 → 递归解析
     - 编排 setup_steps（步骤间变量传递）
  
  2. 生成 test_steps
     - 生成正向用例（1条）
     - 根据场景生成判断规则，逐个生成异常用例
     - 异常用例基于正向用例修改，不从头构造
  
  3. 质量检测（三维度，详见 Step 3）
  
  4. 检测通过 → 保存为独立 JSON 文件
     - 文件名：{method}_{path}.json
     - 更新公共前置缓存
  
  5. 更新飞书卡片进度
```

#### Step 3: 质量检测（每个接口生成后立即执行）

三维度检测，与 api-case-gen 一致：

**维度一：数据引用错误**
- setup_steps 和 test_steps 中所有 `{{N.extract.xxx}}` 的 N < 当前步骤号
- 引用变量在目标步骤的 extract 中存在
- extract 路径在 api-spec 的 response.fields 中有对应字段

**维度二：断言规则正确性**
- 正向用例 status_code 与 api-spec response.status_code 一致
- 异常用例 status_code 为合理错误码（422/401/403/404/500）
- body_fields 字段名在 response.fields 中存在
- 204 无 body_fields

**维度三：编造数据检测**
- body 中无 request_body.fields 中不存在的字段
- body 包含所有 required 字段（正向用例）
- 字段值类型与文档定义一致
- Content-Type 与接口实际要求一致
- params 中无 query_params 中不存在的参数
- headers 中无 required_headers 中未定义的 header

检测结果处理：
- 有错误 → 列出所有错误 → 逐个修复 → 重新检测 → 直到零错误
- 零错误 → 保存文件

#### Step 4: 生成索引和摘要
1. 生成 `single_index.json`：
```json
{
  "project": "项目名",
  "generated_at": "ISO8601时间戳",
  "source": "api_parser/api-spec.json",
  "base_url": "http://...",
  "summary": {
    "total_endpoints": 61,
    "total_cases_files": 61,
    "total_test_steps": 385,
    "by_scenario": {
      "positive": 61,
      "missing_required": 120,
      "wrong_type": 45,
      "format_error": 30,
      "boundary": 40,
      "not_found": 25,
      "unauthorized": 50,
      "sql_injection": 8,
      "xss": 6
    }
  },
  "cases": [
    { "file": "POST_api_users_register.json", "endpoint_id": "...", "method": "POST", "path": "/api/users/register", "setup_count": 0, "test_count": 8 },
    ...
  ]
}
```

2. 生成 `single_cases_summary.md`，包含每个接口的用例概览
3. 更新飞书卡片为完成状态

### 10. 输出格式详细定义

详见 `references/用例格式.md`

## 参考文档

| 主题 | 文件 |
|------|------|
| 用例格式详细定义 | `references/用例格式.md` |
