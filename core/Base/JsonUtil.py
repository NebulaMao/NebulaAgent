import json
import re
from typing import Any, Dict, List



def extract_json_obj(s: str) -> dict:
    """从各种奇怪输出里提取第一个 JSON 对象。兼容 ```json 围栏/多余前后缀。"""
    if not s:
        raise ValueError("empty response")

    # 1) 去除常见 markdown 围栏
    s = s.strip()
    if s.startswith("```"):
        # 去掉首尾 ```xxx\n 与 结尾 ```
        s = re.sub(r"^```[a-zA-Z0-9]*\n?", "", s)
        s = re.sub(r"\n?```$", "", s).strip()

    # 2) 直接尝试解析
    try:
        return json.loads(s)
    except Exception:
        pass

    # 3) 正则提取第一个 {...} 片段再解析（防止模型啰嗦）
    m = re.search(r"\{.*\}", s, re.DOTALL)
    if not m:
        raise ValueError("no JSON object found in response")
    return json.loads(m.group(0))

