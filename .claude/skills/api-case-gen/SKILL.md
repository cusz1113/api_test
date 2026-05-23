---
name: 接口用例生成器
slug: api-case-gen
version: 3.1.0
description: 基于业务流逐条生成可执行的接口测试用例。每条业务流调用一次大模型，由 AI 严格根据接口文档信息生成用例。
metadata: {"emoji":"📋","requires":{"bins":[],"deps":["api-parser","api-flow"]}}
---

## 使用场景

用户需要：
- 基于业务流自动生成可执行的接口测试用例
- 每条业务流生成一组正向用例（正常流程走通）
- 用例可直接用于自动化执行

## 核心设计：AI 逐条生成

> ⚠️ **本 Skill 不使用任何 Python/脚本代码生成用例。每条业务流由 AI（大模型）逐条分析并生成用例。**

### 生成模式

对 `api_flow.json` 中的每条业务流，AI 执行一次独立的用例生成：

```
对每条业务流 flow：
  1. AI 读取 flow 的所有步骤（含嵌入的接口文档信息）
  2. AI 逐步骤分析，严格根据接口文档生成 url/headers/params/body/extract/assert
  3. AI 验证变量依赖链完整性
  4. AI 输出该业务流对应的 1 条测试用例 JSON
  5. AI 对生成的用例进行自检（质量检查清单）
```

**核心原则：AI 看到的就是接口文档写的，不多不少。**

## 输入与输出

### 输入
- `api_flow/api_flow.json` — 业务流定义（步骤已嵌入完整接口文档）
- 输出目录从 api_flow.json 的路径中提取项目名

### 输出目录
- `output/{项目名}/api_cases/`
- `test_cases.json` — 所有测试用例合并后的 JSON
- `test_cases_summary.md` — 用例摘要（人阅读）

### 前置依赖
- 必须先执行 api-flow，产出 `api_flow.json`
- 如果不存在，提示用户先分析业务流

## 用例生成策略

### 一个业务流 = 一条正向用例
- 每条业务流生成 **1 条用例**（完整流程走通）
- 用例的每一步对应业务流的每一步
- 步骤间通过变量传递实现数据关联

## 字段生成规则（严格模式）

> ⚠️ **铁律：所有字段必须从业务流步骤中嵌入的接口文档信息获取，不得推测、编造。**

### 1. url 生成
- `{{base_url}}` + 步骤的 `path`
- 路径参数（如 `{id}`、`{suite_id}`）替换为前置步骤提取的变量：`{{N.extract.id}}`
- 变量引用 `{{N.extract.xxx}}` 中的 N 必须小于当前步骤号

### 2. headers 生成
- 从步骤的 `content_type` 设置 `Content-Type`
- 步骤的 `requires_auth == true` → 添加 `Authorization: Bearer {{N.extract.token}}`（N 为 login 步骤号）
- 步骤的 `required_headers` 中的其他 header 也要加入
- **Content-Type 必须与步骤的 content_type 一致**（有些接口是 `application/x-www-form-urlencoded`）

### 3. params 生成（查询参数）
- 从步骤的 `query_params` 中读取所有参数
- **required 参数必须全部填入**，值为前置步骤的变量引用或合理默认值
- 可选参数不填

### 4. body 生成
- 从步骤的 `request_body.fields` 中读取所有字段
- **required 字段全部填入，不得遗漏**（这是之前用例出错的根因）
- 字段值来源优先级：
  1. 步骤的 `request_example` 中的值（直接使用，变量引用保留 `{{N.extract.xxx}}` 格式）
  2. 前置步骤 extract 的变量引用 `{{N.extract.xxx}}`
  3. 合理的默认测试数据（如 `"Test@123456"`）
- 如果 `request_body.fields` 为空（GET/DELETE 等无请求体的接口），body 不填
- **对于嵌套对象字段，展开为 JSON 对象**

### 5. extract（提取变量）
- 从步骤的 `response.fields` 中确定要提取的变量
- 提取规则：
  - 创建类接口（POST）→ 提取 `$.id`（如果 response.fields 有 id）
  - 登录接口 → 提取 `$.token`（如果 response.fields 有 token）
  - token 接口 → 提取实际返回的字段名（如 `$.access_token`，从 response.fields 中读取）
  - 嵌套对象 → 用完整路径（如 `$.user.id`）
- **只提取后续步骤需要引用的变量 + 流程结束时需要报告的变量**
- 如果 response.fields 为空（如 204 No Content），extract 为空对象 `{}`

### 6. assert（断言）

#### status_code
- **直接从步骤的 `response.status_code` 读取**，不做任何推测
- 步骤写 200 → 断言 200
- 步骤写 201 → 断言 201
- 步骤写 204 → 断言 204

#### body_fields
- 从步骤的 `response.fields` 中读取所有 required 字段
- 每个字段生成 `not_null` 断言
- **字段名必须与 response.fields 中的 name 完全一致**
- 如果 response.fields 为空（如 204），不生成 body_fields
- **不做精确值匹配，只断言 not_null 或 type**

## 变量体系

### 全局变量
| 变量 | 说明 | 示例 |
|------|------|------|
| `{{base_url}}` | API 基础地址 | `http://124.222.144.182:8888` |
| `{{random_username}}` | 随机用户名（8位） | `tsta3f2k9x` |
| `{{random_email}}` | 随机邮箱 | `tsta3f2k9x@test.com` |
| `{{random_mobile}}` | 随机手机号 | `13812340001` |
| `{{random_string_4}}` | 4位随机字符串 | `x7k2` |
| `{{random_string_8}}` | 8位随机字符串 | `x7k2m9p4` |

### 步骤间变量
| 格式 | 说明 |
|------|------|
| `{{N.extract.xxx}}` | 引用第 N 步提取的变量 xxx |

### 特殊处理
- 密码不在响应中返回，登录步骤的密码使用固定值 `Test@123456`，后续步骤如果需要密码直接用固定值
- `{{N.extract.token}}` 和 `{{N.extract.new_token}}` 是变量名，实际 token 的提取路径从 response.fields 中读取

## 生成流程

### Step 1: 准备
1. 读取 `api_flow/api_flow.json`
2. 确认 `business_flows` 不为空
3. 创建输出目录（如不存在）

### Step 2: 逐条生成 + 即时质量检测
对每条业务流（按顺序），AI 执行以下操作：

```
输入：一条业务流（含所有步骤及其嵌入的接口文档信息）

处理：
1. 分析流程的整体变量依赖（哪些步骤产出变量、哪些步骤消费变量）
2. 逐步骤生成用例步骤：
   a. 从步骤的接口文档信息中读取所有字段定义
   b. 生成 url（处理路径参数替换）
   c. 生成 headers（Content-Type + Authorization）
   d. 生成 params（必填查询参数）
   e. 生成 body（必填字段全部填入，值从 request_example 或变量引用获取）
   f. 生成 extract（从 response.fields 中选择后续需要的变量）
   g. 生成 assert（status_code + required body_fields）
3. 验证变量依赖链：
   - 每个 {{N.extract.xxx}} 的 N < 当前步骤号
   - 每个 {{N.extract.xxx}} 在步骤 N 的 extract 中确实存在
   - 每个 required 字段都有值
4. ⭐ 质量检测（必须执行，详见下方「质量检测规范」）
   - 检测不通过 → 立即修复 → 重新检测 → 直到全部通过
   - 检测通过 → 输出用例 JSON

输出：1 条测试用例 JSON（附带质量检测通过记录）
```

> ⚠️ **每条用例生成后必须立即执行质量检测，不允许跳过。检测不通过的用例不得输出。**

### Step 3: 质量检测规范

> 每条用例生成后，AI 必须以**审查者视角**重新检查生成的用例，与业务流步骤中的接口文档信息逐项比对。

#### 检测维度一：数据引用错误

对用例中的每个步骤，检查所有变量引用：

```
对每个步骤 step（step_no = N）：
  收集该步骤中所有的 {{M.extract.xxx}} 引用（从 url/body/headers/params 中）
  对每个引用：
    a. M < N ?（引用的步骤必须在当前步骤之前）
       ❌ 否 → 错误：引用了未来步骤
    b. 步骤 M 的 extract 中有 xxx ?
       ❌ 否 → 错误：引用了不存在的提取变量
    c. 步骤 M 的 response.fields 中有对应的字段？
       ❌ 否 → 错误：提取路径指向不存在的响应字段
```

**同时检查反向：** 前置步骤 extract 的变量是否被后续步骤正确引用（是否有死变量）。死变量不是错误但需要确认是否有遗漏。

#### 检测维度二：断言规则正确性

对用例中的每个步骤，将 assert 与业务流步骤的接口文档比对：

```
对每个步骤 step：
  对应的业务流步骤 = flow.steps[step_no - 1]

  1. status_code 检查：
     assert.status_code == 业务流步骤.response.status_code ?
     ❌ 否 → 错误：状态码与文档不一致

  2. body_fields 字段名检查：
     对 assert.body_fields 中的每个字段名：
       字段名在 业务流步骤.response.fields 中存在？
       ❌ 否 → 错误：断言了文档中不存在的字段

  3. body_fields 完整性检查：
     业务流步骤.response.fields 中所有 required=true 的字段
     是否都在 assert.body_fields 中？
     ❌ 否 → 警告：遗漏了 required 字段的断言

  4. 204 特殊检查：
     assert.status_code == 204 时，assert 中不应有 body_fields
     ❌ 否 → 错误：204 无响应体，不应有 body_fields 断言

  5. 空响应检查：
     业务流步骤.response.fields 为空时，assert 不应有 body_fields
     ❌ 否 → 错误：文档中无响应字段定义，断言无依据
```

#### 检测维度三：编造数据检测

对用例中的每个步骤，将 body/headers/params 与业务流步骤的接口文档比对：

```
对每个步骤 step：
  对应的业务流步骤 = flow.steps[step_no - 1]

  1. body 字段编造检查：
     对 step.body 中的每个字段名：
       字段名在 业务流步骤.request_body.fields 中存在？
       ❌ 否 → 错误：编造了文档中不存在的请求字段

  2. body 必填遗漏检查：
     业务流步骤.request_body.fields 中所有 required=true 的字段
     是否都在 step.body 中？
     ❌ 否 → 错误：遗漏了必填字段

  3. body 字段类型检查：
     对 step.body 中的每个字段：
       值的类型是否与文档定义一致？
       （string→字符串值, integer→整数值, boolean→布尔值, array→数组, object→对象）
       ❌ 否 → 错误：字段值类型与文档不一致

  4. headers 编造检查：
     step.headers 中除了 Content-Type 和 Authorization 外
     是否有其他 header？
       这些 header 是否在 业务流步骤.required_headers 中定义？
       ❌ 否 → 错误：编造了文档中未定义的请求头

  5. Content-Type 检查：
     step.headers["Content-Type"] == 业务流步骤.content_type ?
     ❌ 否 → 错误：Content-Type 与文档不一致

  6. params 编造检查：
     对 step.params 中的每个参数名：
       参数名在 业务流步骤.query_params 中存在？
       ❌ 否 → 错误：编造了文档中不存在的查询参数

  7. params 必填遗漏检查：
     业务流步骤.query_params 中所有 required=true 的参数
     是否都在 step.params 中？
     ❌ 否 → 错误：遗漏了必填查询参数

  8. extract 路径编造检查：
     对 step.extract 中的每个 JSONPath：
       解析出根字段名（如 $.user.id → user，$.token → token）
       根字段名在 业务流步骤.response.fields 中存在？
       ❌ 否 → 错误：提取路径指向文档中不存在的响应字段
```

#### 检测结果处理

```
检测完成后：
  如果有错误 →
    1. 列出所有错误（步骤号 + 错误类型 + 具体描述）
    2. 逐个修复
    3. 重新执行全部检测
    4. 重复直到零错误

  如果零错误 →
    输出用例 JSON
    附带："质量检测通过：3个维度，N项检查，0个错误"
```

### Step 4: 合并输出
将所有业务流的用例合并为 `test_cases.json`：
```json
{
  "project": "项目名",
  "generated_at": "ISO8601时间戳",
  "source": "api_flow/api_flow.json",
  "base_url": "http://...",
  "summary": {
    "total_flows": 13,
    "total_cases": 13,
    "by_priority": {"P0": 13}
  },
  "cases": [...]
}
```

### Step 5: 生成摘要
生成 `test_cases_summary.md`，包含每条用例的步骤概览。

### Step 6: 最终验证
对所有用例执行质量检查清单，发现问题立即修复。

## 用例结构

```json
{
  "id": "{flow_id}_001",
  "name": "{flow_name}-正向",
  "flow_id": "user_auth",
  "flow_name": "用户注册登录认证流程",
  "priority": "P0",
  "tags": ["用户管理", "正向"],
  "preconditions": ["测试环境可用"],
  "steps": [
    {
      "step_no": 1,
      "name": "register",
      "method": "POST",
      "url": "{{base_url}}/api/users/register",
      "headers": {"Content-Type": "application/json"},
      "params": {},
      "body": {
        "username": "{{random_username}}",
        "password": "Test@123456",
        "password_confirm": "Test@123456",
        "email": "{{random_email}}",
        "mobile": "{{random_mobile}}"
      },
      "extract": {
        "username": "$.username"
      },
      "assert": {
        "status_code": 200,
        "body_fields": {
          "id": "not_null",
          "username": "not_null"
        }
      }
    }
  ]
}
```

## 质量检查清单（已升级为「质量检测规范」）

> ⚠️ 质量检查已从简单的 10 项清单升级为**三个维度的系统性检测**，详见上方 Step 3「质量检测规范」。
> 生成每条用例后，AI 必须执行以下检测：

### 维度一：数据引用错误
- 变量引用步骤号 < 当前步骤号
- 变量引用在目标步骤的 extract 中存在
- extract 路径在 response.fields 中有对应字段

### 维度二：断言规则正确性
- status_code 与 response.status_code 一致
- body_fields 字段名在 response.fields 中存在
- 204 无 body_fields
- response.fields 为空时无 body_fields

### 维度三：编造数据检测
- body 中无 request_body.fields 中不存在的字段
- body 包含所有 required 字段
- body 字段值类型与文档定义一致
- headers 中无 required_headers 中未定义的 header
- Content-Type 与 content_type 一致
- params 中无 query_params 中不存在的参数
- params 包含所有 required 参数
- extract 路径无编造

## 常见陷阱（必须避免）

| 陷阱 | 错误做法 | 正确做法 |
|------|---------|---------|
| verify 接口 | 不传 body | body 必须包含 request_body.fields 中的所有 required 字段（如 `token`） |
| token 接口 | 用 JSON 格式 | content_type 是 form-urlencoded 时，body 写成 key-value 对象（执行器负责编码） |
| device 注册 | 只传 name、ip | body 必须包含所有 required 字段（id、system） |
| 创建项目 | 不传 user | body 必须包含所有 required 字段（包括 user） |
| extract 字段名 | 写 `$.access_token` | 从 response.fields 中读取实际字段名（可能是 `$.token`） |
| status_code | 一律写 200 | 从 response.status_code 读取（可能是 201、204） |

## 参考文档

| 主题 | 文件 |
|------|------|
| 用例格式详细定义 | `references/用例格式.md` |
