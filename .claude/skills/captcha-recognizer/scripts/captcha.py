#!/usr/bin/env python3
"""
captcha.py - 验证码识别脚本（图鉴 ttshitu API）

用法:
  python3 captcha.py --base64 "data:image/png;base64,..."
  python3 captcha.py --file /path/to/captcha.png
  python3 captcha.py --file /tmp/captcha.png --retries 3 --length 4
  python3 captcha.py --file /tmp/slide_top.png --file2 /tmp/slide_bottom.png --typeid 1033
"""
import argparse
import json
import sys
import os
import tempfile
import base64
import time
import requests

API_URL = "http://api.ttshitu.com"
DEFAULT_USERNAME = "musen123456"
DEFAULT_PASSWORD = "Musen123456"

# typeid 映射：验证码类型 → 图鉴 typeid
TYPE_MAP = {
    "alnum": 3,       # 数英混合（默认）
    "number": 2,      # 纯数字
    "chinese": 5,     # 中文
    "calc": 7,        # 计算题
    "slide": 1033,    # 拖动拼图（需要两张图）
    "gap": 18,        # 缺口识别（需要两张图）
}


def predict_base64(username, password, typeid, image_path, imageback_path=None, timeout=60, retries=3):
    """
    使用 JSON + Base64 提交图鉴识别请求。

    Args:
        username: 图鉴账号
        password: 图鉴密码
        typeid: 验证码类型 ID
        image_path: 验证码图片路径
        imageback_path: 第二张图片路径（拖动拼图/缺口识别等需要）
        timeout: HTTP 超时秒数
        retries: 重试次数

    Returns:
        dict: {"result": "识别结果", "id": "..."}

    Raises:
        RuntimeError: 识别失败
    """
    with open(image_path, "rb") as f:
        b64_image = base64.b64encode(f.read()).decode()
    data = {"username": username, "password": password, "typeid": str(typeid), "image": b64_image}

    if imageback_path:
        with open(imageback_path, "rb") as fb:
            data["imageback"] = base64.b64encode(fb.read()).decode()

    last_error = "未知错误"
    for attempt in range(retries):
        try:
            resp = requests.post(f"{API_URL}/predict", json=data, timeout=timeout)
            result = resp.json()
            if result.get("success"):
                return result["data"]
            msg = str(result.get("message", ""))
            last_error = msg
            # 人工不足/超时等情况重试
            if any(x in msg for x in ["人工不足", "超时", "timeout", "请延长超时时间"]):
                time.sleep(2)
                continue
            raise RuntimeError(f"图鉴识别失败: {msg}")
        except requests.exceptions.Timeout:
            last_error = "请求超时"
            time.sleep(2)
            continue
        except requests.exceptions.RequestException as e:
            last_error = str(e)
            time.sleep(2)
            continue

    raise RuntimeError(f"图鉴识别重试{retries}次仍失败: {last_error}")


def recognize_captcha(file_path=None, base64_data=None, file_path2=None,
                      max_retries=3, length=4, typeid=None, type_name=None,
                      username=None, password=None):
    """
    识别验证码。

    Args:
        file_path: 本地图片路径（主图）
        base64_data: base64 data URI (data:image/png;base64,...)
        file_path2: 第二张图片路径（拖动拼图/缺口识别等）
        max_retries: 最大重试次数（默认 3）
        length: 验证码长度（默认 4）
        typeid: 图鉴 typeid（直接指定，优先于 type_name）
        type_name: 验证码类型名称（alnum/number/chinese/calc/slide/gap）
        username: 图鉴账号（默认从环境变量或内置）
        password: 图鉴密码（默认从环境变量或内置）

    Returns:
        str: 识别出的验证码文本，失败返回 None
    """
    # 账号密码优先级：参数 > 环境变量 > 默认值
    username = username or os.environ.get("TTSHITU_USERNAME", DEFAULT_USERNAME)
    password = password or os.environ.get("TTSHITU_PASSWORD", DEFAULT_PASSWORD)

    # 确定 typeid
    if typeid is not None:
        tid = typeid
    elif type_name and type_name in TYPE_MAP:
        tid = TYPE_MAP[type_name]
    else:
        tid = TYPE_MAP["alnum"]  # 默认数英混合

    # 准备主图文件
    tmp_path = None
    if file_path:
        img_path = file_path
    elif base64_data:
        if ',' in base64_data:
            b64_str = base64_data.split(',', 1)[1]
        else:
            b64_str = base64_data
        tmp_path = tempfile.mktemp(suffix='.png')
        with open(tmp_path, 'wb') as f:
            f.write(base64.b64decode(b64_str))
        img_path = tmp_path
    else:
        return None

    try:
        result = predict_base64(
            username=username,
            password=password,
            typeid=tid,
            image_path=img_path,
            imageback_path=file_path2,
            retries=max_retries
        )
        code = result.get("result", "")
        # 数英混合类型：只取字母数字，截断到预期长度
        if tid in (2, 3, 7):  # 数字/数英/计算题
            code = ''.join(c for c in code if c.isalnum())
            if length and len(code) > length:
                code = code[:length]
        return code
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return None
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='验证码识别（图鉴 ttshitu）')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--base64', help='Base64 编码的图片 (data:image/png;base64,...)')
    group.add_argument('--file', help='本地图片文件路径')
    parser.add_argument('--file2', help='第二张图片路径（拖动拼图/缺口识别等）')
    parser.add_argument('--retries', type=int, default=3, help='最大重试次数 (默认: 3)')
    parser.add_argument('--length', type=int, default=4, help='验证码长度 (默认: 4)')
    parser.add_argument('--typeid', type=int, help='图鉴 typeid（直接指定）')
    parser.add_argument('--type', choices=['alnum', 'number', 'chinese', 'calc', 'slide', 'gap'],
                        default='alnum', help='验证码类型 (默认: alnum)')
    parser.add_argument('--username', help='图鉴账号（默认内置）')
    parser.add_argument('--password', help='图鉴密码（默认内置）')

    args = parser.parse_args()

    code = recognize_captcha(
        file_path=args.file,
        base64_data=args.base64,
        file_path2=args.file2,
        max_retries=args.retries,
        length=args.length,
        typeid=args.typeid,
        type_name=args.type,
        username=args.username,
        password=args.password,
    )

    if code:
        print(code)
    else:
        sys.exit(1)
