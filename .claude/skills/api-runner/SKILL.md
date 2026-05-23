---
name: 接口用例执行器
slug: api-runner
version: 1.1.0
description: AI 驱动的接口用例执行器，读取 test_cases.json，AI 负责变量解析、数据构造、断言判断，requests 负责发送请求。通过飞书卡片消息实时展示执行进度。
metadata: {"emoji":"🚀","requires":{"bins":["python3"],"deps":["api-parser","api-flow","api-case-gen","api-report-html"]}}
---

## 使用场景

用户需要：
- 执行已生成的接口测试用例
- AI 自动解析变量、构造请求、分析响应、判断断言
- 实时查看执行进度（飞书卡片进度条）
- 输出结构化的执行报告

## 核心规则

### 1. 输入与输出
- **输入：** `api_cases/test_cases.json`（由 api-case-gen Skill 产出）
- **HTTP 请求脚本：** `scripts/api_runner.py`（底层请求器）
- **执行脚本：** `scripts/run_all_cases.py`（顶层执行器，负责变量解析、断言、报告）
- **输出目录：** `output/{项目名}/api_report/`
  - `{YYYYMMDD_HHmmss}_report.json` — 结构化执行结果（机器消费）
  - `{YYYYMMDD_HHmmss}_summary.md` — 人可读摘要

项目名从 test_cases.json 的路径中提取，目录不存在时自动创建。

### 2. 前置依赖
- 必须先完成 api-case-gen，产出 `test_cases.json`
- 指定目录下不存在 `test_cases.json` 时，提示用户先生成用例

### 3. 请求构造规则（大模型驱动）

> ⚠️ **铁律：每个步骤的请求体中的业务数据，必须由大模型根据接口定义和业务流上下文智能生成，不能使用固定的模板变量替换。**

#### 3.0 为什么请求构造必须用大模型

用例 JSON 中的 `body` 字段通常包含模板变量（如 `{{random_username}}`、`{{random_email}}`），这只是**占位符**，不是最终的请求数据。实际执行时需要：

- **理解接口定义**：知道每个字段的含义、类型、约束（长度、格式、枚举值等）
- **理解业务流上下文**：当前步骤在业务流中的角色（创建什么资源、查询什么条件）
- **智能生成**：不仅仅是随机字符串，而是符合业务语义的数据
- **唯一性保证**：每次执行的数据都不同，避免唯一约束冲突影响后续步骤

这些**无法通过简单的模板替换实现**，必须依赖大模型理解接口定义后生成。

#### 3.1 请求构造执行流程

```
对每个步骤执行前：

1. 读取该步骤的 body 模板（含 {{}} 占位符）
2. 读取接口定义（来自 api-spec.json）
   - 字段类型、长度限制、格式要求、枚举值
   - 必填/选填
   - 业务含义（description）
3. 读取业务流上下文
   - 当前步骤在业务流中的角色
   - 前序步骤已创建的资源（变量池）
4. 读取测试场景（scenario，如果有）
5. 将上述信息组装为 prompt，调用大模型生成最终的请求体 JSON
6. 大模型返回可直接使用的完整请求体
```

#### 3.2 大模型构造请求的 Prompt 模板

```
你是一个接口测试数据构造专家。请为以下测试步骤生成完整的请求体 JSON。

【接口定义】
- 接口：{method} {path}
- 接口名称：{endpoint_name}
- 请求字段：
{fields_definition}

【业务流上下文】
- 业务流名称：{flow_name}
- 当前步骤：{step_name}
- 步骤角色：{step_role}

【变量池】（前序步骤已提取的业务变量，可直接使用）
{variable_pool}

【要求】
1. 根据接口定义和业务流上下文，生成完整的请求体 JSON
2. 每个字段的数据必须符合其类型和约束（长度、格式、枚举值等）
3. 数据要有业务语义（如用户名要像真实用户名，邮箱要像真实邮箱）
4. 以下类型的数据每次必须全新生成，不可复用：
   - 用户名/昵称/名称：每次生成不同的值
   - 邮箱：每次生成不同的邮箱地址
   - 手机号：每次生成不同的手机号
   - 密码：使用强密码 Test@123456（无唯一约束可复用）
5. 变量池中的业务变量（如 token、project_id、case_id）直接使用，不要修改
6. 数据要与前序步骤创建的资源有合理的业务关联
7.对于用例数据中的请求数据字段不要做新增和删除字段的操作


【输出格式】直接返回 JSON 对象（不要包裹在 markdown 代码块中）：
{body_template}
```

#### 3.3 数据生成原则

| 原则 | 说明 |
|------|------|
| **业务语义** | 用户名用英文字母开头+数字（如 `john2026`），不用随机字符串（如 `a8f3k2`） |
| **格式合规** | 邮箱用 `xxx@yyy.com` 格式，手机号用 11 位中国手机号格式 |
| **每次唯一** | 同一业务流中不同步骤的用户名/邮箱/手机号必须不同 |
| **前置复用** | 变量池中的 token、project_id 等业务变量直接使用 |
| **外键引用** | project_id、user_id 等外键必须从变量池获取，不可硬编码 |
| **业务关联** | 创建用例时关联到正确的项目，查询时使用已存在的资源 ID |

> ⚠️ **绝对禁止：** 用 Python 脚本的字符串替换（`str.replace`）来处理 `{{}}` 模板变量。模板变量只是用例生成时的占位符，实际执行时由大模型根据接口定义和业务流上下文智能生成最终数据。

### 4. AI 智能断言规则（大模型驱动）

> ⚠️ **铁律：L2 智能断言必须通过调用大模型来分析响应内容，不能硬编码为 Python 规则或简单文本匹配。**

#### 4.0 为什么必须用大模型

L2 智能断言的核心是**语义理解**——判断响应内容的含义是否与该步骤在业务流中的预期行为一致。这需要理解：
- 接口的业务含义和预期行为
- 错误信息的语义（「邮箱已存在」≠「邮箱格式错误」）
- 上下文关系（缺少 username 时返回 email 的错误信息是不对的）
- 不同场景下相同 HTTP 状态码的不同含义

这些**无法通过硬编码规则或正则匹配实现**，必须依赖大模型的语言理解能力。

#### 4.1 断言分层

每个步骤的断言分为两层：

| 层级 | 名称 | 执行方式 | 说明 |
|------|------|---------|------|
| L1 | 基础断言 | Python 脚本机械执行 | 用例 JSON 中的 assert 规则（status_code + body_fields），可直接用脚本判断 |
| L2 | 智能断言 | **必须调用大模型** | 将步骤角色、请求、响应发送给大模型，由大模型分析响应内容是否符合预期 |

> ⚠️ **绝对禁止：** 将 L2 智能断言实现为 Python 的 if/else 规则、正则匹配、关键词查找。L2 的判断主体是大模型，不是代码。

#### 4.2 智能断言执行流程

```
对每个步骤执行完毕后：

1. 先执行 L1 基础断言（Python 脚本机械判断 status_code + body_fields）

2. 如果 L1 失败 → 标记 FAIL，L2 不执行

3. 如果 L1 通过 → 执行 L2 智能断言：
   a. 准备上下文信息：
      - 该步骤在业务流中的角色（创建资源、查询、修改、删除、认证等）
      - 该步骤的 name（步骤名称）
      - 发送的请求体（request body）
      - 接口定义（来自 api-spec.json 的请求参数和响应定义）
      - 实际响应体（response.body）
      - HTTP 状态码
   b. 将上述信息组装为 prompt，调用大模型进行分析
   c. 大模型返回 JSON 结构的断言结果（passed + reason）
   d. 将大模型结果记录为 smart_assert

4. 最终断言结果 = L1 AND L2（两层都通过才算 PASS）
```

#### 4.3 L2 大模型分析 Prompt 模板

调用大模型时，使用以下 prompt 结构（根据实际情况调整）：

```
你是一个接口测试断言分析专家。请分析以下测试步骤的响应是否符合预期行为。

【业务流上下文】
- 业务流名称：{flow_name}
- 当前步骤角色：{step_role}（创建资源/查询/修改/删除/认证等）
- 步骤名称：{step_name}
- 接口：{method} {path}
- 请求体：{request_body}

【接口定义】（来自 api-spec.json）
{endpoint_definition}

【实际响应】
- HTTP 状态码：{status_code}
- 响应体：{response_body}

【分析要求】
1. 判断该步骤在业务流中的预期行为是什么
2. 分析实际响应内容是否与预期行为一致
3. 如果是创建类步骤，响应体是否包含新创建的资源标识
4. 如果包含错误信息，判断错误信息是否准确描述了预期的错误类型
5. 给出明确的通过/失败结论

【输出格式】请返回 JSON：
{
  "passed": true/false,
  "purpose": "该步骤的预期行为",
  "expected": "预期的响应行为",
  "actual": "实际响应的语义分析",
  "reason": "判断理由（失败时必须明确说明期望什么、实际返回了什么、为什么不一致）"
}
```

#### 4.4 智能断言输出格式

在 assertions 数组中，L2 断言以 `type: "smart_assert"` 记录，`reason` 字段必须包含大模型的完整分析：

```json
{
  "type": "smart_assert",
  "step_role": "创建资源",
  "purpose": "创建项目后应返回新项目的 id 和 name",
  "expected": "响应包含有效的项目标识和名称",
  "actual": "响应 body: {"id": 42, "name": "test_project"}",
  "passed": true,
  "reason": "大模型分析：响应正确返回了新创建项目的 id=42 和 name=test_project，与请求一致"
}
```

> ⚠️ **核心原则：大模型必须理解响应内容的语义，而不是做简单的文本匹配。**
> 
> **反面示例（大模型必须判定为失败）：**
> - 缺少必填字段的步骤，响应返回「邮箱格式错误」 → ❌ FAIL（错误信息指出的字段不对）
> - 类型错误的步骤，响应返回「字段不能为空」 → ❌ FAIL（错误信息与类型错误无关）
> - 创建资源的步骤，响应返回了错误信息而非业务数据 → ❌ FAIL

#### 4.5 智能断言对最终结果的影响

- L1 通过 + L2 通过 → **PASS**
- L1 通过 + L2 未通过 → **FAIL**（例如：状态码正确但响应内容语义不匹配）
- L1 未通过 → **FAIL**（L2 不执行）
- L2 无法判断（响应体为空或格式异常）→ 记录 WARN，不改变 L1 结果

#### 4.6 特殊情况处理

- **响应体为空**（如 204 No Content）：L2 断言跳过，仅依赖 L1
- **响应体非 JSON**：L2 断言记录 WARN，尝试从文本中提取关键信息
- **L2 断言与 L1 冲突**：L1 优先，标记 FAIL，在 reason 中说明可能需要调整用例预期
- **L2 错误信息语义不匹配**：L2 断言标记 FAIL 时，大模型的 reason 中必须明确说明「期望 X 类型的错误，实际返回 Y 类型的错误，两者语义不匹配」

### 5. 执行流程（严格按此流程）

#### Step 1: 任务拆解 & 发送进度卡片

收到执行任务后，**第一时间**完成以下动作：

```
1. 读取 test_cases.json，解析 base_url 和 cases 列表
2. 统计：
   - 用例总数
   - 总步骤数（所有 case 的 steps 之和）
   - 优先级分布
3. 通过 message tool 发送初始进度卡片（记录 messageId）
4. 开始执行
```

**初始进度卡片模板：**

```json
{
  "config": { "wide_screen_mode": true },
  "header": {
    "template": "blue",
    "title": { "tag": "plain_text", "content": "🚀 接口测试执行中..." }
  },
  "elements": [
    {
      "tag": "progress",
      "value": 0,
      "status": "running"
    },
    {
      "tag": "markdown",
      "content": "**进度:** 0/{total_steps} 步 (0/{total_cases} 用例)\n**通过:** 0 | **失败:** 0 | **跳过:** 0\n\n⏳ 准备开始..."
    }
  ]
}
```

#### Step 2: 逐条用例执行（AI 驱动循环）

对每条 case，按以下循环执行每个 step：

```
对 case 中的每个 step:
  a. 【🧠 大模型构造请求】
     - 准备上下文：接口定义（api-spec.json）+ 业务流上下文 + body 模板 + 变量池
     - 调用大模型生成最终的请求体 JSON
     - 大模型返回完整请求体（所有 {{}} 占位符已替换为合理的业务数据）

  b. 【AI 构造】组装完整的请求参数 JSON（method + url + headers + 大模型生成的 body）

  c. 【发送请求】通过 exec 调用 api_runner.py:
     exec: python3 {skill_scripts_dir}/api_runner.py '<请求JSON>'

  d. 【🧠 大模型智能断言】读取响应，完成双层断言：
     - L1 基础断言：执行用例 JSON 中的 assert 规则（status_code + body_fields）
     - L2 智能断言：调用大模型分析响应内容是否符合该步骤的预期行为
     - 最终结果 = L1 AND L2
     - 根据 step 的 extract 规则，从响应中提取变量，存入变量池
     - 记录：step_no, name, status(pass/fail), request, response, assertions（含 smart_assert）

  e. 【更新进度卡片】每完成一个 step，立即通过 message edit 更新飞书卡片：
     - 重新计算进度百分比：已完成步骤数 / 总步骤数
     - 更新进度条 value（0-100）
     - 更新统计数字
     - 当前步骤状态追加到明细中
     - 如果全部完成，更新 header 标题为 "✅ 执行完成" 或 "⚠️ 执行完成（有失败）"

  f. 【AI 决策】如果当前 step 失败：
     - 判断是否影响后续步骤（如未获取到 token）
     - 如果后续步骤依赖失败数据，标记剩余步骤为 SKIP，但每个 SKIP 的步骤也更新进度
     - 如果不影响，继续执行

  g. 更新变量池，进入下一个 step
```

**进度卡片更新模板（每个 step 后 edit）：**

```json
{
  "config": { "wide_screen_mode": true },
  "header": {
    "template": "blue",
    "title": { "tag": "plain_text", "content": "🚀 接口测试执行中... (已完成 {completed_steps}/{total_steps})" }
  },
  "elements": [
    {
      "tag": "progress",
      "value": {progress_percent},
      "status": "running"
    },
    {
      "tag": "markdown",
      "content": "**进度:** {completed_steps}/{total_steps} 步 ({completed_cases}/{total_cases} 用例)\n**通过:** {passed} | **失败:** {failed} | **跳过:** {skipped}\n\n{step_details}"
    }
  ]
}
```

**step_details 格式：**
```
✅ [Case1] Step 1 register — 200 OK
✅ [Case1] Step 2 login — 200 OK, token已获取
⏳ [Case2] Step 1 token — 执行中...
```

- ✅ 表示 PASS
- ❌ 表示 FAIL（附带简要原因）
- ⏭️ 表示 SKIP
- ⏳ 表示当前正在执行（仅在最新一步显示）

#### Step 3: 最终状态更新

所有用例执行完毕后：

- 如果全部通过：header template 改为 `green`，标题 "✅ 接口测试执行完成"
- 如果有失败：header template 改为 `red`，标题 "⚠️ 接口测试执行完成（{failed}条失败）"
- 进度条 status 改为 `success`（全通过）或 `failed`（有失败）

#### Step 4: 生成报告

同原有逻辑，生成 report.json 和 summary.md 到输出目录。

#### Step 5: 生成 HTML 报告

报告 JSON 生成后，立即调用 api-report-html Skill 生成可视化 HTML 报告：

```
python3 ~/.openclaw/skills/api-report-html/scripts/generate_html_report.py '<report.json路径>'
```

将生成的 HTML 文件发送给用户。

### 6. 重要约束

- **严格顺序执行**：case 内的 steps 必须按 step_no 顺序执行，不可并行
- **变量隔离**：每个 case 开始时清空变量池，仅保留 base_url
- **幂等性**：不要修改用例文件，只读取
- **可中断**：如果用户中途要求停止，保存已完成的结果，更新卡片为中断状态
- **细粒度进度**：每完成一个 step 立即更新飞书卡片，不攒批
- **卡片消息 ID**：初始发送后必须记住 messageId，后续所有 edit 使用同一个 messageId

### 7. 错误处理

| 场景 | 处理 |
|------|------|
| 请求超时 | 标记 step FAIL，更新进度，记录错误信息，判断是否继续 |
| 连接失败 | 标记 step FAIL，更新进度，提示用户检查环境，暂停执行 |
| 响应非 JSON | 仍记录 body 文本，AI 尝试分析 |
| extract 失败（路径不存在） | 标记 FAIL，更新进度，记录实际响应结构 |
| AI 无法解析变量 | 降级为合理默认值，记录说明 |
| 飞书卡片更新失败 | 不中断执行，记录警告，继续下一步 |
