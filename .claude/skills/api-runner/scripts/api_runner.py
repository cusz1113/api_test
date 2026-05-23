#!/usr/bin/env python3
"""
api_runner.py - 轻量 HTTP 请求器
用法: python3 api_runner.py '<json_request>'
输出: JSON 格式的响应（status_code, headers, body）
"""
import sys
import json
import requests

def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "缺少请求参数"}, ensure_ascii=False))
        sys.exit(1)

    try:
        req = json.loads(sys.argv[1])
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"JSON解析失败: {e}"}, ensure_ascii=False))
        sys.exit(1)

    method = req.get("method", "GET").upper()
    url = req.get("url", "")
    headers = req.get("headers", {})
    params = req.get("params", {})
    body = req.get("body")
    timeout = req.get("timeout", 30)

    if not url:
        print(json.dumps({"error": "url 不能为空"}, ensure_ascii=False))
        sys.exit(1)

    try:
        # form-urlencoded 用 data 发送，json 用 json 发送
        ct = (headers.get("Content-Type") or "").lower()
        if "application/x-www-form-urlencoded" in ct and body:
            kw = {"data": body}
        elif body:
            kw = {"json": body}
        else:
            kw = {}

        resp = requests.request(
            method=method,
            url=url,
            headers=headers,
            params=params,
            timeout=timeout,
            **kw
        )
        # 尝试解析 JSON body
        try:
            resp_body = resp.json()
        except Exception:
            resp_body = resp.text

        result = {
            "status_code": resp.status_code,
            "headers": dict(resp.headers),
            "body": resp_body
        }
        print(json.dumps(result, ensure_ascii=False, default=str))

    except requests.exceptions.Timeout:
        print(json.dumps({"error": "请求超时"}, ensure_ascii=False))
    except requests.exceptions.ConnectionError as e:
        print(json.dumps({"error": f"连接失败: {e}"}, ensure_ascii=False))
    except Exception as e:
        print(json.dumps({"error": f"请求异常: {e}"}, ensure_ascii=False))

if __name__ == "__main__":
    main()
