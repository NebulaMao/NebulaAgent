import asyncio
import json
import logging
import os
from typing import Any, Dict, List
from fastmcp import FastMCP
from core.phone import Button, Phone, PressType, SwipeDirection
from core.Base.AgentBase import call_llm
from core.Base.JsonUtil import extract_json_obj


class ActionAssistant:
    def __init__(self, phone: Phone):
        """
        初始化ActionAgent
        :param phone: Phone实例
        """
        self.phone = phone
        self.action_mcp = FastMCP(name="PhoneAutomationactionsMCP")
        self._setup_tools()
    
    def _setup_tools(self):
        """设置MCP工具"""
        
        @self.action_mcp.tool
        async def GetPhoneState(query: str = "简述当前手机状态"):
            """
            通过query获取手机状态,可以询问具体坐标
            param query: 查询内容
            :return: 手机状态信息
            """
            info = await self.phone.get_phone_state(query)
            return info

        @self.action_mcp.tool(name="touch_action")
        async def touch_action(PressType: PressType, description: str) -> str:
            """
            根据描述执行点击或长按操作
            :param PressType: oncLinck or LongPress
            :param description: 要点击的东西
            :return: 点击结果
            """
            MeaningfulGui = self.phone.get_meaningful_gui()
            prompt = self.build_gui_matching_prompt(description, MeaningfulGui)
            message = [{"role": "user", "content": prompt}]
            response_text = await call_llm(
                message, 
                os.getenv("ActionAssistant", "zai-org/glm-4.5"), 
                os.getenv("openai_key", "sk-x"), 
                os.getenv("openai_baseurl", "https://api.siliconflow.cn/v1")
            )
            logging.info(f"获取到数据: {response_text}")
            try:
                response_json = extract_json_obj(response_text)
                x = int(response_json["x"])
                y = int(response_json["y"])
            except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                return None
            print(f"点击坐标: ({x}, {y})")

            if PressType == "oncLinck":
                success = self.phone.Onclick(int(x), int(y))
                logging.info(f"执行点击操作: 坐标=({x}, {y}), 结果={'成功' if success else '失败'}")
                if success:
                    now_state = await self.phone.get_phone_state("当前我点击了" + description + "描述当前手机状态")
                    return f"点击成功！当前手机状态为：{now_state}"
                return f"点击失败"
            elif PressType == "LongPress":
                success = self.phone.long_press(int(x), int(y))
                logging.info(f"执行长按操作: 坐标=({x}, {y}), 结果={'成功' if success else '失败'}")
                if success:
                    now_state = await self.phone.get_phone_state("当前我点击了" + description + "描述当前手机状态")
                    return f"长按成功！当前手机状态为：{now_state}"
                return f"长按失败"
            logging.warning(f"未知操作类型: {PressType}")
            return f"未知操作类型: {PressType}"

        @self.action_mcp.tool
        def swipe(direction: SwipeDirection) -> str:
            """
            执行滑动操作
            """
            return self.phone.swipe(direction)

        @self.action_mcp.tool
        def long_press(x: int, y: int) -> str:
            """
            执行长按操作
            """
            return self.phone.long_press(x, y)

        @self.action_mcp.tool
        def send_keys(text: str) -> str:
            """
            输入文字
            """
            return self.phone.send_keys(text)

        @self.action_mcp.tool
        def press_button(button: Button) -> str:
            """
            按键操作
            """
            return self.phone.press_button(button)
    
    def get_mcp(self):
        """获取MCP实例"""
        return self.action_mcp

    def build_gui_matching_prompt(self, description: str, gui_elements: List[Dict[str, Any]]) -> str:
        """
        构建一个提示词，指导AI模型找到最匹配描述的GUI元素。
        
        :param description: 目标GUI元素的自然语言描述。
        :param gui_elements: 表示GUI元素的字典列表（应包含'text'、'resource-id'、'bounds'、'class'等键）。
        :return: 一个格式化的提示字符串，用于发送给AI模型。
        """
        prompt = f"""
        ```
    You are a UI element matcher for an Android device.

    Your task is to analyze a list of GUI elements and a user-provided description.  
    Identify the GUI element that best matches the description.  
    Each element contains metadata like 'text', 'resource-id', 'bounds', and 'class'.

    Once you've found the best match, calculate the center point from the 'bounds' rectangle:  
    Format: [left, top, right, bottom]  
    Center:  
    x = (left + right) // 2  
    y = (top + bottom) // 2

    Return only the result in this exact JSON format:
    {{"x": number, "y": number}}

    ---

    User Description:
    "{description}"

    GUI Elements:
    {gui_elements}

    Only output the JSON result, nothing else.
    ```
    """
        return prompt
