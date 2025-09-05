import os
import subprocess
from typing import List, Dict, Any, Optional, Literal
import json
import re
import base64


import xml.etree.ElementTree as ET

from core.Base.AgentBase import call_llm
# 滑动操作
SwipeDirection = Literal["up", "down", "left", "right"]
# 按键操作
Button = Literal["BACK", "HOME", "VOLUME_UP", "VOLUME_DOWN", "ENTER", "DPAD_CENTER", "DPAD_UP", "DPAD_DOWN", "DPAD_LEFT", "DPAD_RIGHT"]
# 屏幕方向
Orientation = Literal["portrait", "landscape"]
# 按压类型
PressType = Literal["LongPress", "oncLinck"]
# 按键映射
BUTTON_MAP = {
    "BACK": "KEYCODE_BACK",
    "HOME": "KEYCODE_HOME", 
    "VOLUME_UP": "KEYCODE_VOLUME_UP",
    "VOLUME_DOWN": "KEYCODE_VOLUME_DOWN",
    "ENTER": "KEYCODE_ENTER",
    "DPAD_CENTER": "KEYCODE_DPAD_CENTER",
    "DPAD_UP": "KEYCODE_DPAD_UP",
    "DPAD_DOWN": "KEYCODE_DPAD_DOWN",
    "DPAD_LEFT": "KEYCODE_DPAD_LEFT",
    "DPAD_RIGHT": "KEYCODE_DPAD_RIGHT",
}

class Phone:
    def __init__(self, id: str, adb_path: str = "adb"):
        """
        初始化手机对象
        :param id: 手机的唯一标识符
        :param adb_path: ADB命令的路径，默认为"adb"
        """
        self.id = id
        self.state = {}
        self.adb_path = adb_path
        self.installed_packages = self.list_packages()
        if "ca.zgrs.clipper" in self.installed_packages:
            self.installed_clipper = True
        else:
            self.installed_clipper = False
        

    def adb(self, *args: str) -> str:
        """执行ADB命令并返回输出"""
        try:
            result = subprocess.run(
                [self.adb_path, "-s", self.id] + list(args),
                capture_output=True,
                text=True,
                check=True,
                timeout=30
            )
            return result.stdout
        except subprocess.CalledProcessError as e:
            raise Exception(f"ADB命令执行失败: {e.stderr}")

    def get_screen_size(self) -> Dict[str, int]:
        """获取屏幕尺寸"""
        output = self.adb("shell", "wm", "size")
        size_match = re.search(r'(\d+)x(\d+)', output)
        if size_match:
            width, height = map(int, size_match.groups())
            return {"width": width, "height": height, "scale": 1}
        raise Exception("无法获取屏幕尺寸")

    def get_system_features(self) -> List[str]:
        """获取系统特性列表"""
        output = self.adb("shell", "pm", "list", "features")
        return [
            line.strip().replace("feature:", "")
            for line in output.split("\n")
            if line.strip().startswith("feature:")
        ]

    def list_apps(self) -> List[Dict[str, str]]:
        """列出所有可启动的应用"""
        output = self.adb("shell", "cmd", "package", "query-activities", 
                         "-a", "android.intent.action.MAIN", 
                         "-c", "android.intent.category.LAUNCHER")
        
        packages = []
        for line in output.split("\n"):
            line = line.strip()
            if line.startswith("packageName="):
                package_name = line.replace("packageName=", "")
                packages.append({
                    "packageName": package_name,
                    "appName": package_name
                })
        
        # 去重
        seen = set()
        unique_packages = []
        for pkg in packages:
            if pkg["packageName"] not in seen:
                seen.add(pkg["packageName"])
                unique_packages.append(pkg)
        
        return unique_packages

    def list_packages(self) -> List[str]:
        """列出所有已安装的包"""
        output = self.adb("shell", "pm", "list", "packages")
        return [
            line.strip().replace("package:", "")
            for line in output.split("\n")
            if line.strip().startswith("package:")
        ]

    def launch_app(self, package_name: str) -> str:
        """启动应用。支持传入包名或 '包名/Activity' 组件名。
        解析顺序：resolve-activity -> query-activities -> monkey 兜底
        """
        try:
            if not package_name:
                return "启动应用失败: 未提供包名"

            # 直接传了组件名（pkg/.Activity 或 pkg/fully.qualified.Activity）的话，直接开
            if "/" in package_name:
                self.adb("shell", "am", "start", "--user", "0", "-n", package_name)
                return f"组件 {package_name} 启动成功"

            # 确认是否安装
            installed = self.adb("shell", "pm", "list", "packages", package_name)
            if f"package:{package_name}" not in installed:
                return f"启动应用失败: 设备未安装 {package_name}"

            component = None

            # 1) 现代设备：resolve-activity --brief（直接返回可以喂给 am 的组件名）
            out = self.adb(
                "shell", "cmd", "package", "resolve-activity", "--brief",
                "-a", "android.intent.action.MAIN",
                "-c", "android.intent.category.LAUNCHER",
                package_name
            ).strip()

            for line in out.splitlines():
                line = line.strip()
                # 典型输出：com.example.app/.MainActivity
                if "/" in line and not line.lower().startswith("no activity"):
                    component = line
                    break

            # 2) 老设备或部分 ROM：query-activities，过滤出目标包的 name
            if not component:
                out2 = self.adb(
                    "shell", "cmd", "package", "query-activities",
                    "-a", "android.intent.action.MAIN",
                    "-c", "android.intent.category.LAUNCHER"
                )
                cur_pkg = None
                for raw in out2.splitlines():
                    s = raw.strip()
                    # 有的系统是 packageName=xxx，有的写 package=xxx
                    if s.startswith("packageName=") or s.startswith("package="):
                        cur_pkg = s.split("=", 1)[1].strip()
                    # name= 可能是 .MainActivity / fully.qualified.Activity / 甚至直接是 pkg/.MainActivity
                    elif (s.startswith("name=") or s.startswith("name:")) and cur_pkg == package_name:
                        sep = "=" if "=" in s else ":"
                        name = s.split(sep, 1)[1].strip()
                        if "/" in name:
                            component = name  # 已经是 component 形式
                        elif name.startswith("."):
                            component = f"{package_name}/{name}"
                        else:
                            component = f"{package_name}/{name}"
                        break

            if component:
                self.adb("shell", "am", "start", "--user", "0", "-n", component)
                return f"应用 {package_name} 启动成功（{component}）"

            # 3) 最后兜底：monkey（部分机型会有 toast 但也能拉起）
            self.adb("shell", "monkey", "-p", package_name,
                    "-c", "android.intent.category.LAUNCHER", "1")
            return f"应用 {package_name} 启动成功（未解析到主 Activity，使用 monkey）"

        except Exception as e:
            return f"启动应用失败: {e}"

    def terminate_app(self, package_name: str) -> str:
        """终止应用"""
        try:
            self.adb("shell", "am", "force-stop", package_name)
            return f"应用 {package_name} 已终止"
        except Exception as e:
            return f"终止应用失败: {e}"

    def list_running_processes(self) -> List[str]:
        """列出正在运行的进程"""
        output = self.adb("shell", "ps", "-e")
        processes = []
        for line in output.split("\n"):
            line = line.strip()
            if line.startswith("u"):  # 非系统进程
                parts = line.split()
                if len(parts) > 8:
                    processes.append(parts[8])
        return processes

    def press_button(self, button: Button) -> str:
        """按下按键"""
        if button not in BUTTON_MAP:
            return f"不支持的按键: {button}"
        
        try:
            self.adb("shell", "input", "keyevent", BUTTON_MAP[button])
            return f"按键 {button} 执行成功"
        except Exception as e:
            return f"按键操作失败: {e}"
    def long_press(self, x: int, y: int) -> str:
        """长按指定坐标"""
        try:
            self.adb("shell", "input", "touchscreen", "swipe", str(x), str(y), str(x), str(y), "500")
            return f"长按坐标 ({x}, {y}) 成功"
        except Exception as e:
            return f"长按操作失败: {e}"
    
    def swipe(self, direction: SwipeDirection) -> str:
        """滑动屏幕"""
        try:
            screen_size = self.get_screen_size()
            center_x = screen_size["width"] // 2
            
            if direction == "up":
                x0 = x1 = center_x
                y0 = int(screen_size["height"] * 0.80)
                y1 = int(screen_size["height"] * 0.20)
            elif direction == "down":
                x0 = x1 = center_x
                y0 = int(screen_size["height"] * 0.20)
                y1 = int(screen_size["height"] * 0.80)
            elif direction == "left":
                x0 = int(screen_size["width"] * 0.80)
                x1 = int(screen_size["width"] * 0.20)
                y0 = y1 = int(screen_size["height"] * 0.50)
            elif direction == "right":
                x0 = int(screen_size["width"] * 0.20)
                x1 = int(screen_size["width"] * 0.80)
                y0 = y1 = int(screen_size["height"] * 0.50)
            else:
                return f"不支持的滑动方向: {direction}"
            
            self.adb("shell", "input", "swipe", str(x0), str(y0), str(x1), str(y1), "1000")
            return f"向{direction}滑动成功"
        except Exception as e:
            return f"滑动操作失败: {e}"

    def swipe_from_coordinate(self, x: int, y: int, direction: SwipeDirection, distance: Optional[int] = None) -> str:
        """从指定坐标开始滑动"""
        try:
            screen_size = self.get_screen_size()
            
            # 使用提供的距离或默认值
            default_distance_y = int(screen_size["height"] * 0.3)
            default_distance_x = int(screen_size["width"] * 0.3)
            swipe_distance_y = distance or default_distance_y
            swipe_distance_x = distance or default_distance_x
            
            if direction == "up":
                x0 = x1 = x
                y0 = y
                y1 = max(0, y - swipe_distance_y)
            elif direction == "down":
                x0 = x1 = x
                y0 = y
                y1 = min(screen_size["height"], y + swipe_distance_y)
            elif direction == "left":
                x0 = x
                x1 = max(0, x - swipe_distance_x)
                y0 = y1 = y
            elif direction == "right":
                x0 = x
                x1 = min(screen_size["width"], x + swipe_distance_x)
                y0 = y1 = y
            else:
                return f"不支持的滑动方向: {direction}"
            
            self.adb("shell", "input", "swipe", str(x0), str(y0), str(x1), str(y1), "1000")
            return f"从({x}, {y})向{direction}滑动成功"
        except Exception as e:
            return f"坐标滑动操作失败: {e}"

    def send_keys(self, text: str) -> str:
        """发送文本输入"""
        if not text:
            return "文本为空，跳过输入"
        
        try:
            # 检查是否为ASCII文本
            if text.isascii():
                # 转义空格
                escaped_text = text.replace(" ", "\\ ")
                self.adb("shell", "input", "text", escaped_text)
                return f"成功输入文本: {text}"
            else:
                if self.installed_clipper:
                    self.adb("shell", "am", "startservice", "ca.zgrs.clipper/.ClipboardService")
                    
                    # 将文本设置到剪贴板
                    self.adb("shell", "am", "broadcast", "-a", "clipper.set", "-e", "text", f'"{text}"')
                    
                    # 执行粘贴操作
                    self.adb("shell", "input", "keyevent", "KEYCODE_PASTE")

                
                return f"成功输入文本: {text}"
        except Exception as e:
            return f"文本输入失败: {e}"

    def set_orientation(self, orientation: Orientation) -> str:
        """设置屏幕方向"""
        try:
            orientation_value = 0 if orientation == "portrait" else 1
            
            # 禁用自动旋转
            self.adb("shell", "settings", "put", "system", "accelerometer_rotation", "0")
            # 设置方向
            self.adb("shell", "content", "insert", "--uri", "content://settings/system",
                    "--bind", "name:s:user_rotation", "--bind", f"value:i:{orientation_value}")
            return f"屏幕方向设置为: {orientation}"
        except Exception as e:
            return f"设置屏幕方向失败: {e}"

    def get_orientation(self) -> str:
        """获取当前屏幕方向"""
        try:
            rotation = self.adb("shell", "settings", "get", "system", "user_rotation").strip()
            orientation = "portrait" if rotation == "0" else "landscape"
            return f"当前屏幕方向: {orientation}"
        except Exception as e:
            return f"获取屏幕方向失败: {e}"

    def get_screenshot(self) -> str:
        """
        获取手机屏幕截图
        :return: 截图文件的本地路径
        """
        remote_image_path = f"/sdcard/screenshot.png"  # 
        local_image_path = f"screenshot.png"
        
        screencap_result = subprocess.run(
            f"{self.adb_path} -s {self.id} shell screencap -p {remote_image_path}", 
            shell=True, capture_output=True, text=True, timeout=10
        )
        if screencap_result.returncode != 0:
            return f"截图失败: {screencap_result.stderr}"
        
        pull_result = subprocess.run(
            f"{self.adb_path} -s {self.id} pull {remote_image_path} {local_image_path}", 
            shell=True, capture_output=True, text=True, timeout=10
        )
        if pull_result.returncode != 0:
            return f"拉取截图失败: {pull_result.stderr}"

        if not os.path.exists(local_image_path):
            return "截图文件未找到"
        # 删除远程截图文件
        self.adb("shell", "rm", remote_image_path)

        return local_image_path

    def get_uiautomator_dump(self) -> str:
        """
        执行 adb uiautomator dump 命令，返回 XML 字符串
        """
        try:
            result = subprocess.run(
                [self.adb_path, "-s", self.id, "exec-out", "uiautomator", "dump", "/dev/tty"],
                capture_output=True,
                text=True,
                check=True,
            )
            output_lines = result.stdout.splitlines()
            xml_lines = [line for line in output_lines if line.strip().startswith("<?xml")]
            if xml_lines:
                start_index = output_lines.index(xml_lines[0])
                xml_content = "\n".join(output_lines[start_index:])
                hierarchy_start = xml_content.find("<hierarchy")
                if hierarchy_start != -1:
                    last_part = xml_content[hierarchy_start:]
                    hierarchy_end_tag = "</hierarchy>"
                    hierarchy_end = last_part.rfind(hierarchy_end_tag)
                    if hierarchy_end != -1:
                        full_xml = last_part[: hierarchy_end + len(hierarchy_end_tag)]
                        if full_xml.strip().endswith("</hierarchy>"):
                            return full_xml
                    return last_part
                else:
                    return xml_content
            else:
                raise ValueError("未找到 UI Automator XML。")
        except subprocess.CalledProcessError as e:
            print(f"执行 adb 命令出错: {e}")
            print(f"stderr: {e.stderr}")
            raise
        except subprocess.TimeoutExpired:
            print("adb 命令超时。")
            raise
        except FileNotFoundError:
            print("未找到 adb 命令，请确保已安装并配置环境变量。")
            raise

    @staticmethod
    def parse_bounds(bounds_str: str) -> Dict[str, int]:
        """
        解析 bounds 字符串为矩形字典
        例: '[x1,y1][x2,y2]' -> {"x": x1, "y": y1, "width": x2-x1, "height": y2-y1}
        """
        if not bounds_str or not bounds_str.startswith("[") or not bounds_str.endswith("]"):
            return {"x": 0, "y": 0, "width": 0, "height": 0}
        try:
            parts = bounds_str[1:-1].split("][")
            if len(parts) != 2:
                raise ValueError("bounds 格式错误")
            x1, y1 = map(int, parts[0].split(","))
            x2, y2 = map(int, parts[1].split(","))
            return {"x": x1, "y": y1, "width": x2 - x1, "height": y2 - y1}
        except (ValueError, IndexError) as e:
            print(f"警告: bounds 解析失败 '{bounds_str}': {e}")
            return {"x": 0, "y": 0, "width": 0, "height": 0}

    @staticmethod
    def collect_clickable_elements(node: ET.Element) -> List[Dict[str, Any]]:
        """
        递归收集所有 clickable="true" 的 UI 元素，并去掉 x<=0 y<=0 的元素
        """
        elements: List[Dict[str, Any]] = []
        for child in node:
            if child.tag == "node":
                elements.extend(Phone.collect_clickable_elements(child))
        if node.attrib.get("clickable") == "true":
            rect_data = Phone.parse_bounds(node.attrib.get("bounds", ""))
            if (
                rect_data["width"] > 0
                and rect_data["height"] > 0
                and rect_data["x"] > 0
                and rect_data["y"] > 0
            ):
                element: Dict[str, Any] = {
                    "type": node.attrib.get("class", "text"),
                    "text": node.attrib.get("text", "").strip(),
                    "label": node.attrib.get("content-desc", "").strip()
                    or node.attrib.get("hint", "").strip(),
                    "rect": rect_data,
                }
                if node.attrib.get("focused") == "true":
                    element["focused"] = True
                resource_id = node.attrib.get("resource-id", "").strip()
                if resource_id:
                    element["identifier"] = resource_id
                elements.append(element)
        return elements
    @staticmethod 
    def collect_meaningful_elements(node: ET.Element) -> List[Dict[str, Any]]:
        elements: List[Dict[str, Any]] = []

        for child in node:
            if child.tag == "node":
                elements.extend(Phone.collect_meaningful_elements(child))

        has_text = node.attrib.get("text", "").strip()
        has_label = node.attrib.get("content-desc", "").strip() or node.attrib.get("hint", "").strip()
        if has_text or has_label:
            rect_data = Phone.parse_bounds(node.attrib.get("bounds", ""))
            element: Dict[str, Any] = {
                "type": node.attrib.get("class", "text"),
                "text": node.attrib.get("text", "").strip(),
                "label": node.attrib.get("content-desc", "").strip() or node.attrib.get("hint", "").strip(),
                "rect": rect_data,
            }
            if node.attrib.get("focused") == "true":
                element["focused"] = True
            resource_id = node.attrib.get("resource-id", "").strip()
            if resource_id:
                element["identifier"] = resource_id
            if rect_data["width"] > 0 and rect_data["height"] > 0:
                elements.append(element)

        return elements
    def get_onclickable(self) -> List[Dict[str, Any]]:
        """
        获取当前屏幕所有可点击的 UI 元素
        """
        try:
            xml_string = self.get_uiautomator_dump()
            root_element = ET.fromstring(xml_string)
            screen_elements = self.collect_clickable_elements(root_element)
            return screen_elements
        except Exception as e:
            print(f"处理过程中出错: {e}")
            raise
    def get_meaningful_gui(self) -> List[Dict[str, Any]]:
        """
        获取当前屏幕所有有意义的 UI 元素
        """
        try:
            xml_string = self.get_uiautomator_dump()
            root_element = ET.fromstring(xml_string)
            screen_elements = self.collect_meaningful_elements(root_element)
            return screen_elements
        except Exception as e:
            print(f"处理过程中出错: {e}")
            raise
    async def get_phone_state(self, query: str) -> str:
        """
        获取手机当前状态，可用于检查任务是否完成
        query: str 描述想获取的信息
        """
        meaningful_gui = self.get_meaningful_gui()
        prompt = self.generate_gui_state_prompt(query,meaningful_gui)
        message = [{"role": "user", "content": prompt}]
        now_state = await call_llm(message, 
                        os.getenv("CheckAssistant"), 
                        os.getenv("openai_key"), 
                        os.getenv("openai_baseurl"),
                        )
        return {"state": now_state}
    def Onclick(self,x: int, y: int) -> bool:
        """
        执行点击操作
        :param x: 点击的 x 坐标
        :param y: 点击的 y 坐标
        :return: 操作结果描述
        """
        try:
            result = subprocess.run(
                [self.adb_path, "-s", self.id, "shell", "input", "tap", str(x), str(y)],
                capture_output=True,
                text=True,
                check=True,
            )
            return True
        except subprocess.CalledProcessError as e:
            return False
    def generate_gui_state_prompt(self,query: str, gui_elements: List[Dict[str, Any]]) -> str:
        """
        生成用于分析手机 GUI 状态的提示词。

        参数:
        - query: 用户提出的问题或希望了解的手机状态（如“当前在哪个页面”）
        - gui_elements: 通过 meaningfulgui 获取的 GUI 元素列表（应为 JSON 字符串）

        返回:
        - prompt: 结构化英文提示词，适用于调用语言模型进行状态分析
        """
        prompt = f"""
    You are a GUI state analyzer for an Android device.

    Your task is to analyze a list of GUI elements and answer a user query about the current phone state.  
    Each element contains metadata like 'text', 'resource-id', 'bounds', and 'class'.

    Use the provided GUI elements to infer the device's current state.  
    Focus on the visible screen, active app, dialogs, or any UI patterns relevant to the question.

    User Query:
    "{query}"

    GUI Elements:
    {gui_elements}

    Respond with a concise, factual English summary (max 100 words) that directly answers the user's query,  
    focusing on actionable and observable UI information.  
    Avoid speculation. Only describe what can be inferred from the GUI data.

    """
        return prompt


