---
name: captcha-recognizer
slug: captcha-recognizer
version: 2.0.0
description: 使用图鉴（ttshitu）API 识别图形验证码。支持 base64 图片和本地文件路径输入，支持多种验证码类型（数英混合、纯数字、中文、计算题、拖动拼图、缺口识别）。当需要"识别验证码"、"验证码识别"、"captcha"、"ocr"时触发。
metadata: {"emoji":"🔐","requires":{"bins":["python3"],"deps":["requests"]}}
---

## 使用场景

- 识别图形验证码（字母数字混合、纯数字、中文、计算题等）
- 拖动拼图 / 缺口识别（支持双图模式）
- 在接口测试执行中自动识别验证码
- 任何需要验证码 OCR 的场景

## 核心能力

- **引擎**：图鉴（ttshitu）API（`http://api.ttshitu.com`）
- **输入**：验证码图片（base64 data URI 或本地文件路径）
- **输出**：识别出的验证码文本字符串
- **类型**：数英混合(3)、纯数字(2)、中文(5)、计算题(7)、拖动拼图(1033)、缺口识别(18)
- **重试**：自动重试（人工不足/超时等情况自动重试，最多 3 次）

## 使用方式

### 命令行

```bash
# 识别本地图片文件（数英混合，默认）
python3 scripts/captcha.py --file /path/to/captcha.png

# 识别 base64 图片
python3 scripts/captcha.py --base64 "data:image/png;base64,iVBORw0KGgo..."

# 指定验证码类型
python3 scripts/captcha.py --file /tmp/captcha.png --type number      # 纯数字
python3 scripts/captcha.py --file /tmp/captcha.png --type chinese     # 中文
python3 scripts/captcha.py --file /tmp/captcha.png --type calc        # 计算题

# 拖动拼图（需要两张图）
python3 scripts/captcha.py --file /tmp/top.png --file2 /tmp/bottom.png --type slide

# 缺口识别（需要两张图）
python3 scripts/captcha.py --file /tmp/bg.png --file2 /tmp/target.png --type gap

# 直接指定图鉴 typeid
python3 scripts/captcha.py --file /tmp/captcha.png --typeid 3

# 指定重试次数和验证码长度
python3 scripts/captcha.py --file /tmp/captcha.png --retries 3 --length 4
```

### Python 代码调用

```python
import sys
sys.path.insert(0, '/path/to/captcha-recognizer/scripts')
from captcha import recognize_captcha

# 从文件路径（数英混合，默认）
code = recognize_captcha(file_path="/tmp/captcha.png")

# 从 base64 data URI
code = recognize_captcha(base64_data="data:image/png;base64,...")

# 指定类型
code = recognize_captcha(file_path="/tmp/captcha.png", type_name="number")
code = recognize_captcha(file_path="/tmp/captcha.png", type_name="chinese")

# 拖动拼图（双图）
code = recognize_captcha(file_path="/tmp/top.png", file_path2="/tmp/bottom.png", type_name="slide")

# 带重试
code = recognize_captcha(file_path="/tmp/captcha.png", max_retries=3, length=4)
```

### 在接口测试执行器中集成

```python
from captcha import recognize_captcha

# 1. 获取验证码
resp = requests.get(f"{base_url}/api/v1/auth/captcha")
data = resp.json()
captcha_key = data['data']['captcha_key']
captcha_image = data['data']['captcha_image']

# 2. 识别验证码（~1-3秒）
captcha_code = recognize_captcha(base64_data=captcha_image, max_retries=1)

# 3. 使用验证码请求接口
# ... 如果接口返回验证码错误，重新获取+识别（业务验证重试）
```

### 在 Shell 脚本中集成

```bash
# 获取验证码
CAPTCHA_RESP=$(curl -s 'http://host/api/v1/auth/captcha')
CAPTCHA_KEY=$(echo $CAPTCHA_RESP | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['captcha_key'])")
CAPTCHA_IMAGE=$(echo $CAPTCHA_RESP | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['captcha_image'])")

# 识别验证码
CAPTCHA_CODE=$(python3 scripts/captcha.py --base64 "$CAPTCHA_IMAGE")

# 使用
curl -X POST 'http://host/api/v1/auth/login' \
  -H 'Content-Type: application/json' \
  -d "{\"captcha_key\":\"$CAPTCHA_KEY\",\"captcha_code\":\"$CAPTCHA_CODE\",...}"
```

## 参数说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--file` | 本地图片文件路径（主图） | 与 --base64 二选一 |
| `--base64` | Base64 编码图片（支持 data URI 格式） | 与 --file 二选一 |
| `--file2` | 第二张图片路径（拖动拼图/缺口识别） | 可选 |
| `--type` | 验证码类型：alnum/number/chinese/calc/slide/gap | alnum |
| `--typeid` | 图鉴 typeid（直接指定，优先于 --type） | 3（数英混合） |
| `--retries` | 最大重试次数 | 3 |
| `--length` | 验证码预期长度（数英/数字/计算题类型生效） | 4 |
| `--username` | 图鉴账号 | 内置默认 |
| `--password` | 图鉴密码 | 内置默认 |

### typeid 对照表

| 类型 | typeid | 说明 |
|------|--------|------|
| 数英混合 | 3 | 字母+数字混合（默认） |
| 纯数字 | 2 | 纯数字验证码 |
| 中文 | 5 | 中文验证码 |
| 计算题 | 7 | 如 "3+5=?" |
| 拖动拼图 | 1033 | 需要两张图（--file + --file2） |
| 缺口识别 | 18 | 需要两张图（--file + --file2） |

## 输出

- 成功：stdout 输出识别文本，exit code 0
- 失败：stderr 输出错误信息，exit code 1

## 账号配置

优先级：`--username/--password` > 环境变量 `TTSHITU_USERNAME/TTSHITU_PASSWORD` > 内置默认值

```bash
# 推荐通过环境变量配置（避免硬编码）
export TTSHITU_USERNAME="your_username"
export TTSHITU_PASSWORD="your_password"
```

## 准确率提升策略

在执行器中建议使用**业务验证重试**（最可靠）：

```
获取验证码 → 图鉴识别 → 请求接口
  ↓ 如果返回验证码错误
获取新验证码 → 图鉴识别 → 再请求
  ↓ 最多重试 3 轮
```

## 注意事项

- 依赖 `requests` 库：`pip install requests`
- 不需要 MCP、不需要 API Key、不需要 MiniMax CLI
- 图鉴 API 为付费服务，每次识别消耗题分
- 超时建议 60 秒（API 文档要求）
- 人工不足/超时等场景自动重试
