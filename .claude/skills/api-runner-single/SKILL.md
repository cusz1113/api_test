---
name: 单接口用例执行器
slug: api-runner-single
version: 1.0.0
description: 执行 api-case-gen-single 产出的单接口用例文件（每个接口一个 JSON），支持 setup_steps + test_steps 两阶段编排、公共前置复用、飞书卡片实时进度。用当用户需要"执行单接口测试用例"、"运行单接口测试"、"执行 single_cases"、"测试单个接口"时触发。
metadata: {"emoji":"🎯","requires":{"bins":["python3"],"deps":["api-parser","api-case-gen-single","api-report-html"]}}
---

## 使用场景

用户需要：
- 执行单接口测试用例（每个接口独立 JSON 文件）
- 支持 setup_steps（前置依赖）+ test_steps（测试场景）两阶段执行
- 支持指定执行某个或某几个接口的用例
- 实时查看执行进度（飞书卡片）

## 核心规则

### 1. 输入与输出

- **输入：** `api_cases/single/` 目录下的用例 JSON 文件
- **HTTP 请求脚本：** `scripts/api_runner.py`（复用 api-runner 的底层请求器，路径：`~/.openclaw/skills/api-runner/scripts/api_runner.py`）
- **输出目录：** `output/{项目名}/api_report/single/`
  - `POST_api_users_register_report.json` — 每个接口的独立执行报告
  - `POST_api_users_login_report.json`
  - `...`
  - `{timestamp}_single_summary.json` — 汇总报告
  - `{timestamp}_single_report.html` — HTML 可视化报告

项目名从用例文件路径中提取，目录不存在时自动创建。

### 2. 前置依赖

- 必须先完成 api-case-gen-single，产出 `api_cases/single/` 目录下的用例文件
- 目录不存在或为空时，提示用户先生成单接口用例

### 3. 接口范围选择

| 方式 | 示例 | 说明 |
|------|------|------|
| 全量执行 | 不指定 | 遍历 `single/` 目录下所有 JSON 文件 |
| 指定接口 | "执行用户注册接口" | 匹配文件名或 path 关键词 |
| 指定标签 | "执行用户管理相关接口" | 匹配用例文件中的 tags |
| 指定文件 | "执行 POST_api_users_register.json" | 精确文件名 |

### 4. 与 api-runner 的关键差异

| 维度 | api-runner（业务流） | api-runner-single（单接口） |
|------|---------------------|--------------------------|
| 用例来源 | 单个 test_cases.json | single/ 目录下多个独立文件 |
| 用例结构 | steps（线性） | setup_steps + test_steps（两阶段） |
| 变量隔离 | 每个 case 清空变量池 | 每个 case 独立，setup_steps 和 test_steps 共享变量池 |
| 公共前置复用 | 无 | 支持 ref 引用，共享 setup_steps 的执行结果 |
| 进度粒度 | 按 step 更新 | 按 test_step 更新（setup_steps 合并显示为「前置准备」） |
| 失败策略 | 失败后 SKIP 后续 step | setup_steps 失败→该用例所有 test_steps 标记 SKIP；test_step 失败→不影响其他 test_step |
| 报告输出 | 单个 report.json | 每接口独立报告 + 汇总报告 |

### 5. 请求构造规则（大模型驱动）

> ⚠️ **铁律：每个步骤的请求体中的业务数据，必须由大模型根据接口定义和测试场景智能生成，不能使用固定的模板变量替换。**

#### 5.0 为什么请求构造必须用大模型

用例 JSON 中的 `body` 字段通常包含模板变量（如 `{{random_username}}`、`{{random_email}}`），这只是**占位符**，不是最终的请求数据。实际执行时需要：

- **理解接口定义**：知道每个字段的含义、类型、约束（长度、格式、枚举值等）
- **理解测试场景**：正向用例需要合理的业务数据，异常用例需要针对性的错误数据
- **智能生成**：不仅仅是随机字符串，而是符合业务语义的数据（如用户名要像用户名、地址要像地址）
- **唯一性保证**：每次执行的数据都不同，避免唯一约束冲突影响其他用例

这些**无法通过简单的模板替换实现**，必须依赖大模型理解接口定义后生成。

#### 5.1 请求构造执行流程

```
对每个步骤执行前：

1. 读取该步骤的 body 模板（含 {{}} 占位符）
2. 读取接口定义（来自 api-spec.json）
   - 字段类型、长度限制、格式要求、枚举值
   - 必填/选填
   - 业务含义（description）
3. 读取测试场景（scenario）
   - positive → 生成合理业务数据
   - missing_required → 故意去掉某个字段
   - wrong_type → 故意传错类型
   - format_error → 故意传错误格式
   - boundary → 生成边界值数据
   - unique_conflict → 复用前置步骤已创建的数据
   - sql_injection → 注入 SQL payload
   - xss → 注入 XSS payload
4. 读取当前变量池（前置步骤提取的业务变量，如 token、user_id）
5. 将上述信息组装为 prompt，调用大模型生成最终的请求体 JSON
6. 大模型返回可直接使用的完整请求体
```

#### 5.2 大模型构造请求的 Prompt 模板

```
你是一个接口测试数据构造专家。请为以下测试步骤生成完整的请求体 JSON。

【接口定义】
- 接口：{method} {path}
- 接口名称：{endpoint_name}
- 请求字段：
{fields_definition}

【测试场景】
- 场景类型：{scenario}
- 场景说明：{scenario_description}
- 用例名称：{step_name}
- 用例中的请求体内容：{body}

【变量池】（前置步骤已提取的业务变量，可直接使用）
{variable_pool}

【要求】
1. 根据接口定义和测试场景，和用例中的请求体内容，生成完整的请求体 JSON
2. 每个字段的数据必须符合其类型和约束（长度、格式、枚举值等）
3. 数据要有业务语义（如用户名要像真实用户名，邮箱要像真实邮箱）
4. 以下类型的数据每次必须全新生成，不可复用：
   - 用户名/昵称/名称：每次生成不同的值
   - 邮箱：每次生成不同的邮箱地址
   - 手机号：每次生成不同的手机号
   - 密码：使用强密码 Test@123456（无唯一约束可复用）
5. 变量池中的业务变量（如 token、user_id）直接使用，不要修改
6. 如果是异常场景，只需修改目标字段，其他字段保持合理
7.对于用例数据中的请求数据字段不要做新增和删除字段的操作（比如测试用例测的是某个字段缺失，在生成用例的时候不能自作主张加上这个字段的内容）

【输出格式】直接返回 JSON 对象（不要包裹在 markdown 代码块中）：
{body_template}
```

#### 5.3 数据生成原则

| 原则 | 说明 |
|------|------|
| **业务语义** | 用户名用英文字母开头+数字（如 `john2026`），不用随机字符串（如 `a8f3k2`） |
| **格式合规** | 邮箱用 `xxx@yyy.com` 格式，手机号用 11 位中国手机号格式 |
| **每次唯一** | 同一接口的不同步骤，用户名/邮箱/手机号必须不同 |
| **异常精准** | `missing_required` 只去掉目标字段，其他字段正常；`format_error` 只改目标字段格式 |
| **前置复用** | `unique_conflict` 场景必须复用前置步骤已创建的数据 |
| **外键引用** | project_id、user_id 等外键必须从变量池获取，不可硬编码 |

#### 5.4 大模型构造 vs Python 模板替换

| 维度 | Python 模板替换（旧） | 大模型智能构造（新） |
|------|---------------------|---------------------|
| 用户名 | `{{random_username}}` → `tst7f3k2` | 大模型 → `john_wang2026` |
| 邮箱 | `{{random_email}}` → `tst7f3k2@test.com` | 大模型 → `john.wang@example.com` |
| 手机号 | `{{random_mobile}}` → `13812345678` | 大模型 → `13987654321` |
| 业务字段 | 无模板 → 跳过或报错 | 大模型根据 description 生成合理值 |
| 枚举字段 | 无模板 → 跳过或报错 | 大模型根据 enum 约束选择 |
| 嵌套对象 | 逐层替换，容易遗漏 | 大模型整体生成，结构完整 |

> ⚠️ **绝对禁止：** 用 Python 脚本的字符串替换（`str.replace`）来处理 `{{}}` 模板变量。模板变量只是用例生成时的占位符，实际执行时由大模型根据接口定义智能生成最终数据。

### 6. AI 智能断言规则（大模型驱动）

> ⚠️ **铁律：L2 智能断言必须通过调用大模型来分析响应内容，不能硬编码为 Python 规则或简单文本匹配。**

#### 6.0 为什么必须用大模型

L2 智能断言的核心是**语义理解**——判断响应内容的含义是否与用例的测试验证目的一致。这需要理解：
- 接口的业务含义和预期行为
- 错误信息的语义（「邮箱已存在」≠「邮箱格式错误」）
- 上下文关系（缺少 username 时返回 email 的错误信息是不对的）
- 不同场景下相同 HTTP 状态码的不同含义

这些**无法通过硬编码规则或正则匹配实现**，必须依赖大模型的语言理解能力。

#### 6.1 断言分层

每个步骤的断言分为两层：

| 层级 | 名称 | 执行方式 | 说明 |
|------|------|---------|------|
| L1 | 基础断言 | Python 脚本机械执行 | 用例 JSON 中的 assert 规则（status_code + body_fields），可直接用脚本判断 |
| L2 | 智能断言 | **必须调用大模型** | 将 scenario、请求、响应发送给大模型，由大模型分析响应内容是否符合测试目的 |

> ⚠️ **绝对禁止：** 将 L2 智能断言实现为 Python 的 if/else 规则、正则匹配、关键词查找。L2 的判断主体是大模型，不是代码。

#### 6.2 智能断言执行流程

```
对每个步骤执行完毕后：

1. 先执行 L1 基础断言（Python 脚本机械判断 status_code + body_fields）

2. 如果 L1 失败 → 标记 FAIL，L2 不执行

3. 如果 L1 通过 → 执行 L2 智能断言：
   a. 准备上下文信息：
      - 该步骤的 scenario 字段（测试场景类型）
      - 该步骤的 name（用例名称）
      - 发送的请求体（request body）
      - 接口定义（来自 api-spec.json 的请求参数和响应定义）
      - 实际响应体（response.body）
      - HTTP 状态码
   b. 将上述信息组装为 prompt，调用大模型进行分析
   c. 大模型返回 JSON 结构的断言结果（passed + reason）
   d. 将大模型结果记录为 smart_assert

4. 最终断言结果 = L1 AND L2（两层都通过才算 PASS）
```

#### 6.3 L2 大模型分析 Prompt 模板

调用大模型时，使用以下 prompt 结构（根据实际情况调整）：

```
你是一个接口测试断言分析专家。请分析以下测试步骤的响应是否符合测试验证目的。

【用例信息】
- 场景类型：{scenario}
- 用例名称：{step_name}
- 接口：{method} {path}
- 请求体：{request_body}

【接口定义】（来自 api-spec.json）
{endpoint_definition}

【实际响应】
- HTTP 状态码：{status_code}
- 响应体：{response_body}

【分析要求】
1. 判断这条用例的测试验证目的是什么
2. 分析实际响应内容是否与测试目的语义一致
3. 如果响应包含错误信息，判断错误信息是否准确描述了该场景预期的错误类型
4. 给出明确的通过/失败结论

【输出格式】请返回 JSON：
{
  "passed": true/false,
  "purpose": "该用例的测试验证目的",
  "expected": "预期的响应行为",
  "actual": "实际响应的语义分析",
  "reason": "判断理由（失败时必须明确说明期望什么、实际返回了什么、为什么不一致）"
}
```

#### 6.5 各场景的智能断言要点

> 以下要点是大模型分析时的参考方向，**不是硬编码规则**。大模型应根据实际响应内容灵活判断。

| scenario | 测试目的 | 大模型分析要点 |
|----------|---------|--------------|
| `positive` | 正常流程走通 | 响应体是否包含预期的业务数据？关键字段值是否合理？ |
| `missing_required` | 缺少必填字段被拒绝 | 错误信息是否指出了**正确的缺失字段**？不能是其他字段的错误 |
| `wrong_type` | 参数类型错误被拒绝 | 错误信息是否与**类型**相关？不能是格式错误或缺失字段 |
| `format_error` | 格式校验失败被拒绝 | 错误信息是否与**格式校验**相关？不能是「已存在」「重复」等其他类型错误 |
| `boundary` | 边界值被正确处理 | 边界值是否被合理拒绝或处理？错误信息是否与边界条件相关？ |
| `unique_conflict` | 唯一约束冲突被拒绝 | 错误信息是否与**唯一性**相关？不能是格式错误或类型错误 |
| `not_found` | 资源不存在被拒绝 | 错误信息是否与**资源不存在**相关？ |
| `unauthorized` | 未认证被拒绝 | 错误信息是否与**认证**相关？ |
| `forbidden` | 无权限被拒绝 | 错误信息是否与**权限**相关？ |
| `sql_injection` | SQL 注入被防御 | 是否存在数据泄露？是否返回了不该返回的数据？ |
| `xss` | XSS 注入被防御 | 注入的脚本是否被转义？是否被存储到数据库？ |

> ⚠️ **核心原则：大模型必须理解响应内容的语义，而不是做简单的文本匹配。**
> 
> **反面示例（大模型必须判定为失败）：**
> - `format_error` 场景（邮箱格式错误），响应返回「邮箱已存在」 → ❌ FAIL
>   - 理由：「邮箱已存在」是唯一约束冲突的错误，不是格式校验的错误。用例期望触发格式校验失败，但实际触发了唯一约束校验
> - `format_error` 场景（手机号格式错误），响应返回「手机号已存在」 → ❌ FAIL
>   - 理由：同上，错误信息语义与格式校验不匹配
> - `missing_required` 场景（缺少 username），响应返回「邮箱格式错误」 → ❌ FAIL
>   - 理由：错误信息指向 email 字段而非 username 字段

#### 6.3 各场景的智能断言规则

| scenario | 测试目的 | 智能断言检查点 |
|----------|---------|--------------|
| `positive` | 正常流程走通 | 响应体包含预期的业务数据（如创建成功返回 id、登录返回 token）；关键字段值合理 |
| `missing_required` | 缺少必填字段被拒绝 | 响应体包含错误信息（error message/detail），错误信息指出缺少了哪个字段 |
| `wrong_type` | 参数类型错误被拒绝 | 响应体包含错误信息，错误信息与类型错误相关 |
| `format_error` | 格式校验失败被拒绝 | 响应体包含错误信息，**且错误信息必须与格式校验相关**（如包含 format、invalid、邮箱、手机号等关键词），不能返回「已存在」「重复」等不相关错误 |
| `boundary` | 边界值被正确处理 | 根据具体 boundary_type 检查：空值被拒绝、超长被截断或拒绝、密码不一致有明确提示 |
| `unique_conflict` | 唯一约束冲突被拒绝 | 响应体包含唯一性冲突的错误信息（如「用户名已存在」），**不能是格式错误或类型错误** |
| `not_found` | 资源不存在被拒绝 | 响应体包含「不存在」或「未找到」相关的错误信息 |
| `unauthorized` | 未认证被拒绝 | 响应体包含认证相关的错误信息 |
| `forbidden` | 无权限被拒绝 | 响应体包含权限相关的错误信息 |
| `sql_injection` | SQL 注入被防御 | 响应体不包含数据库原始数据泄露；不返回 200 成功响应；错误信息不暴露 SQL 语句 |
| `xss` | XSS 注入被防御 | 响应体中的注入内容被转义（`<script>` 变为 `&lt;script&gt;`）或不被存储 |

> ⚠️ **核心原则：智能断言不是简单地检查「响应是否有错误信息」，而是检查「错误信息是否与该用例的测试目的语义匹配」。**
> 
> **反面示例（必须标记失败）：**
> - `format_error` 场景（邮箱格式错误），响应返回「邮箱已存在」 → ❌ FAIL（错误信息与格式校验无关）
> - `format_error` 场景（手机号格式错误），响应返回「手机号已存在」 → ❌ FAIL（错误信息与格式校验无关）
> - `missing_required` 场景（缺少 username），响应返回「邮箱格式错误」 → ❌ FAIL（错误信息指出的字段不对）
> - `unique_conflict` 场景（用户名重复），响应返回「字段类型错误」 → ❌ FAIL（错误信息与唯一约束无关）

#### 6.6 智能断言输出格式

在 assertions 数组中，L2 断言以 `type: "smart_assert"` 记录，`reason` 字段必须包含大模型的完整分析：

```json
{
  "type": "smart_assert",
  "scenario": "format_error",
  "purpose": "邮箱格式错误应被格式校验拒绝",
  "expected": "响应包含与格式校验相关的错误信息",
  "actual": "响应 body: {"detail": "邮箱已存在"}",
  "passed": false,
  "reason": "用例测试目的是验证邮箱格式校验（如 abc 不是合法邮箱格式），但响应返回「邮箱已存在」——这是唯一约束冲突的错误，不是格式校验的错误。错误信息语义与测试目的不匹配。"
}
```

#### 6.7 智能断言对最终结果的影响

- L1 通过 + L2 通过 → **PASS**
- L1 通过 + L2 未通过 → **FAIL**（例如：状态码正确但响应内容语义与测试目的不匹配）
- L1 未通过 → **FAIL**（L2 不执行）
- L2 无法判断（响应体为空或格式异常）→ 记录 WARN，不改变 L1 结果

#### 6.8 特殊情况处理

- **响应体为空**（如 204 No Content）：L2 断言跳过，仅依赖 L1
- **响应体非 JSON**（如 HTML 错误页）：L2 断言记录 WARN，尝试从文本中提取关键信息
- **L2 断言与 L1 冲突**（如 L1 期望 422 但实际 200，但 200 响应的内容确实合理）：L1 优先，标记 FAIL，但在 reason 中说明可能需要调整用例预期
- **L2 错误信息语义不匹配**：L2 断言标记 FAIL 时，大模型的 reason 中必须明确说明「期望 X 类型的错误，实际返回 Y 类型的错误，两者语义不匹配」

### 7. 执行流程

#### Step 1: 任务准备 & 发送进度卡片

```
1. 扫描 single/ 目录，收集所有用例 JSON 文件
2. 根据用户指定的接口范围过滤文件列表
3. 读取 single_index.json（如果存在），获取统计信息
4. 统计：
   - 接口总数（文件数）
   - 总 test_steps 数（所有文件的 test_steps 之和）
   - 场景分布（positive/missing_required/...）
5. 通过 message tool 发送初始进度卡片（记录 messageId）
```

#### Step 2: 遍历文件，逐接口执行

```
对每个用例文件（按文件名排序）：
  
  a. 读取 JSON 文件，解析 target_endpoint + setup_steps + test_steps
  
  b. 【执行 setup_steps】
     - 更新飞书卡片：「🔧 {接口名} — 前置准备中...」
     - 初始化该用例的变量池
     - 检查公共前置缓存：
       - 已缓存 → 复用变量池，跳过执行
       - 未缓存 → 逐个执行 setup_steps
     - 对每个 setup_step：
       - 🧠 **大模型构造请求**：准备上下文，调用大模型生成请求体
       - 调用 api_runner.py 发送请求
       - 🧠 **大模型分析响应**：提取变量存入变量池
       - 记录结果
     - setup_steps 全部成功 → 缓存变量池（标记为公共前置）
     - setup_steps 任一失败 → 该用例所有 test_steps 标记 SKIP，进入下一个接口
  
  c. 【执行 test_steps】
     - 对每个 test_step：
       - 🧠 **大模型构造请求**：
         1. 准备上下文：接口定义（api-spec.json）+ scenario + step_name + body 模板 + 变量池
         2. 调用大模型生成最终的请求体 JSON
         3. 大模型返回完整请求体（所有 {{}} 占位符已替换为合理的业务数据）
       - 调用 api_runner.py 发送请求（使用大模型生成的请求体）
       - 🧠 **大模型智能断言**（双层断言）：
         1. L1 基础断言：执行用例 JSON 中的 assert 规则（status_code + body_fields）
         2. L2 智能断言：调用大模型分析响应内容是否符合 scenario 的测试验证目的
         3. 最终结果 = L1 AND L2
       - 提取变量存入变量池
       - 记录：step_no, name, scenario, status, request, response, assertions（含 smart_assert）
       - 更新飞书卡片进度（按 test_step 粒度）
       - test_step 失败 → 不影响其他 test_step，继续执行下一个
  
  d. 【保存接口报告】
     - 该接口所有步骤执行完毕
     - 生成独立报告文件：`{method}_{path}_report.json`
     - 更新飞书卡片：「✅ {接口名} 完成 (N通过/M失败)」
  
  e. 进入下一个接口
```

#### Step 3: 最终状态更新

所有接口执行完毕后：
- 全部通过：绿色 header「✅ 单接口测试执行完成」
- 有失败：红色 header「⚠️ 单接口测试执行完成（N条失败）」
- 进度条 status 改为 success/failed

#### Step 4: 生成汇总报告

输出 `{timestamp}_single_summary.json`：
```json
{
  "project": "web-test-platform",
  "started_at": "ISO8601",
  "finished_at": "ISO8601",
  "duration_seconds": 120,
  "base_url": "http://...",
  "summary": {
    "total_endpoints": 61,
    "total_test_steps": 385,
    "passed_steps": 350,
    "failed_steps": 30,
    "skipped_steps": 5,
    "pass_rate": "90.9%",
    "endpoints_passed": 55,
    "endpoints_failed": 6
  },
  "endpoint_results": [
    {
      "file": "POST_api_users_register.json",
      "method": "POST",
      "path": "/api/users/register",
      "name": "用户注册",
      "status": "PASS",
      "setup_status": "PASS",
      "test_results": {
        "total": 8,
        "passed": 8,
        "failed": 0,
        "skipped": 0
      },
      "details": [ ... ]
    }
  ]
}
```

#### Step 5: 生成 HTML 报告

调用 api-report-html Skill（v2.0.0）生成深色科技风可视化 HTML 报告。脚本自动检测报告格式（业务流 vs 单接口），无需额外参数：
```
python3 ~/.openclaw/skills/api-report-html/scripts/generate_html_report.py '<summary_report.json路径>'
```
输出文件：同目录下 `_summary.html`

### 8. 公共前置缓存机制

```
执行过程中维护一个缓存字典：

cache = {
  "POST_api_users_login.json:setup_steps": {
    "variable_pool": { "username": "xxx", "token": "yyy" },
    "results": [ ... ]
  }
}
```

**缓存命中规则：**
- 当前用例的 setup_steps 与缓存中的 setup_steps 步骤列表一致（method + path + body 结构相同）
- 命中 → 直接复用 variable_pool，跳过 setup_steps 执行
- 未命中 → 正常执行 setup_steps，执行成功后写入缓存

**缓存失效规则：**
- setup_steps 中有 random_* 变量 → 不缓存（每次执行数据不同）
- setup_steps 执行失败 → 不缓存



### 9. 接口独立报告格式

每个接口执行完毕后，保存独立报告：

```json
{
  "project": "web-test-platform",
  "endpoint": {
    "endpoint_id": "...",
    "method": "POST",
    "path": "/api/users/register",
    "name": "用户注册",
    "tags": ["用户管理"]
  },
  "executed_at": "ISO8601",
  "base_url": "http://...",
  "summary": {
    "setup_total": 0,
    "setup_passed": 0,
    "setup_failed": 0,
    "test_total": 8,
    "test_passed": 7,
    "test_failed": 1,
    "test_skipped": 0,
    "status": "FAIL"
  },
  "setup_results": [],
  "test_results": [
    {
      "step_no": 1,
      "name": "用户注册-正向",
      "scenario": "positive",
      "status": "PASS",
      "request": { "method": "POST", "url": "...", "headers": {...}, "params": {}, "body": {...} },
      "response": { "status_code": 200, "body": {...} },
      "assertions": [
        { "type": "status_code", "expected": 200, "actual": 200, "passed": true },
        { "type": "body_field", "field": "id", "rule": "not_null", "actual": 123, "passed": true }
      ],
      "extracted": { "id": 123, "username": "test_xxx" },
      "duration_ms": 156
    }
  ],
  "duration_ms": 1200
}
```

### 10. 错误处理

| 场景 | 处理 |
|------|------|
| setup_steps 失败 | 标记该接口所有 test_steps 为 SKIP，记录 setup 失败原因，进入下一个接口 |
| 请求超时 | 标记 test_step FAIL，更新进度 |
| 连接失败 | 标记 test_step FAIL，更新进度，提示用户检查环境，暂停执行 |
| 响应非 JSON | 仍记录 body 文本，AI 尝试分析 |
| extract 失败 | 标记 FAIL，记录实际响应结构 |
| 飞书卡片更新失败 | 不中断执行，记录警告 |
| 用例文件 JSON 格式错误 | 跳过该文件，记录错误，继续执行其他文件 |

### 11. 重要约束

- **严格顺序执行：** 接口间按文件名排序，接口内 setup_steps → test_steps 顺序
- **变量隔离：** 每个接口独立变量池，公共前置通过缓存复用
- **幂等性：** 不修改用例文件，只读取
- **可中断：** 用户中途要求停止时，保存已完成的结果，更新卡片为中断状态
- **细粒度进度：** 每完成一个 test_step 立即更新飞书卡片
- **report.json 格式兼容：** 汇总报告的格式与 api-runner 的 report.json 兼容，可复用 api-report-html 生成 HTML

## 参考文档

| 主题 | 文件 |
|------|------|
| 底层 HTTP 请求器 | `~/.openclaw/skills/api-runner/scripts/api_runner.py` |
| HTML 报告生成 | `~/.openclaw/skills/api-report-html/SKILL.md`（v2.0.0，自动检测格式） |
