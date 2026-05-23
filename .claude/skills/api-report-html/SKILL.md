---
name: HTML测试报告生成器
slug: api-report-html
version: 2.0.0
description: 将接口测试执行报告转换为精美的深色科技风 HTML 测试报告。支持两种报告格式：业务流用例报告（api-runner 产出）和单接口用例报告（api-runner-single 产出）。自动检测格式，无需额外参数。用当用户需要"生成测试报告"、"HTML报告"、"可视化报告"时触发。
metadata: {"emoji":"📊","requires":{"bins":["python3"],"deps":["api-runner","api-runner-single"]}}
---

## 使用场景

用户需要：
- 将接口测试执行结果生成可视化 HTML 报告
- 报告中详细展示每个用例/接口的请求和响应信息
- 可在浏览器中打开查看，也可分享给团队

## 核心规则

### 1. 输入与输出

- **输入：** JSON 报告文件（自动检测格式）
  - 业务流报告：`{timestamp}_report.json`（由 api-runner 产出）
  - 单接口报告：`{timestamp}_single_summary.json`（由 api-runner-single 产出）
- **脚本：** 本 Skill 目录下的 `scripts/generate_html_report.py`
- **模板：** 本 Skill 目录下的 `templates/report.html`
- **输出：** 同目录下 `.html` 文件
  - `_report.json` → `_report.html`
  - `_summary.json` → `_summary.html`

### 2. 前置依赖

- 必须先执行 api-runner 或 api-runner-single，产出报告 JSON

### 3. 使用方式

```bash
python3 {skill_scripts_dir}/generate_html_report.py '<报告JSON路径>'
```

输出 HTML 文件路径会打印到 stdout。

### 4. 自动格式检测

脚本自动检测报告格式：
- 报告中包含 `cases` 字段 → **格式A（业务流报告）**
- 报告中包含 `endpoint_results` 字段 → **格式B（单接口报告）**

### 5. 两种格式的视觉差异

| 维度 | 业务流报告 | 单接口报告 |
|------|-----------|-----------|
| 顶部统计 | 用例通过 X/Y | 接口通过 X/Y |
| 过滤按钮 | 全部/通过/失败 | 全部/通过/失败 |
| 详情结构 | 用例 → 步骤 | 接口 → 前置准备 + 测试步骤 |
| 前置步骤 | 无 | 灰色左边框 + 🔧 前缀 + 独立区域 |
| 场景标签 | 无 | 紫色标签显示 scenario |

### 6. 报告内容要求

HTML 报告必须包含以下内容：

#### 6.1 汇总面板（顶部）
- 项目名称、执行时间、耗时、Base URL
- 通过/失败/跳过步骤数 + 通过率 + 进度条
- 用例/接口通过数

#### 6.2 用例/接口列表（可折叠）
- 业务流：用例 ID、名称、优先级、状态、步骤统计
- 单接口：HTTP 方法标签 + 路径、接口名称、状态、步骤统计

#### 6.3 步骤详情
- 请求方法+URL（彩色标签）、请求头、请求参数、请求体
- 响应状态码（彩色）、响应体（JSON 语法高亮）
- 断言结果表格、提取变量表格

#### 6.4 样式要求
- **深色科技风**：深蓝底色 + 渐变光晕 + 霓虹边框
- **单文件 HTML**：所有 CSS 和 JS 内联，无外部依赖
- **响应式布局**：支持桌面和移动端
- **代码高亮**：JSON 语法高亮（黑白灰配色）
- **HTTP 方法颜色**：GET=蓝、POST=绿、PUT=橙、DELETE=红、PATCH=紫
- **交互功能**：用例/步骤可折叠展开、全部展开/折叠、通过/失败过滤
- **Authorization 脱敏**：只显示前12位 + `***`
- **中文字体优先**：`-apple-system, "PingFang SC", "Microsoft YaHei", sans-serif`

### 7. 兼容性

- 两种报告格式共用同一个 HTML 模板和渲染脚本
- 断言字段兼容 `pass`（业务流）和 `passed`（单接口）两种命名
- 模板变量统一映射，无需为不同格式维护多套模板

## 参考文档

| 主题 | 文件 |
|------|------|
| 渲染脚本 | `scripts/generate_html_report.py` |
| HTML 模板 | `templates/report.html` |
