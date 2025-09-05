import os
import logging
from fastmcp import FastMCP
from core.Base.vector_db import MobileAgentHelper
from core.Base.AgentBase import MCPClient
from core.Base.JsonUtil import  extract_json_obj


class KnowledgeAssistant:
    """
    知识助手类，负责处理应用知识库查询、应用启动等功能
    """
    
    def __init__(self, phone_instance):
        """
        初始化知识助手
        
        Args:
            phone_instance: Phone实例，用于应用启动等操作
        """
        self.phone = phone_instance
        self.helper = MobileAgentHelper()
        self.mcp = self._create_mcp_server()
        
    def _create_mcp_server(self) -> FastMCP:
        """创建MCP服务器并注册工具"""
        mcp = FastMCP(name="KnowledgeAssistant")
        
        @mcp.tool("get_app_description")
        def get_app_description(package_name: str) -> str:
            """Return the app description by Android package name.

            Args:
                package_name: e.g. 'com.example.app'.

            Returns:
                The description string if found, otherwise None.
            """
            app_info = self.helper.vector_db.get_app_by_package(package_name)
            return app_info.get('description', "") if app_info else ""
            
        @mcp.tool("list_app_actions")
        def list_app_actions(package_name: str) -> list:
            """List all supported actions for the app.

            Args:
                package_name: e.g. 'com.example.app'.

            Returns:
                A list of action names (empty if not found).
            """
            results = self.helper.vector_db.search_help_documents(package_name=package_name)
            return [result['title'] for result in results] if results else []

        @mcp.tool("get_action_knowledge")
        def get_action_knowledge(package_name: str, action_id: str) -> str:
            """Get the knowledge base content for a specific action.

            Args:
                package_name: e.g. 'com.example.app'.
                action_name: e.g. '1'.

            Returns:
                The knowledge base content string if found, otherwise None.
            """
            result = self.helper.get_help(package_name=package_name, query=action_id)
            return result
            
        @mcp.tool("StartApp")
        def StartApp(app_package_name: str) -> str:
            """
            启动指定应用(执行前先使用GetInstalledApps获取应用列表)
            :param app_package_name: 应用包名
            :return: 启动结果
            """
            return self.phone.launch_app(app_package_name)
            
        @mcp.tool("GetInstalledApps")
        def GetInstalledApps():
            """
            获取手机已安装的应用列表(如果需要使用StartApp工具，请先使用此工具获取应用列表)
            """
            return self.phone.list_apps()
            
        return mcp
    
    async def process_user_request(self, user_input: str) -> dict:
        """
        处理用户请求，查询知识库并返回应用信息和操作知识
        
        Args:
            user_input: 用户的自然语言输入
            
        Returns:
            包含app和content的字典
        """
        logging.info("=============== 开始查询知识库 ===============")
        
        # 构建知识查询提示词
        prompt = self.build_action_knowledge_prompt(user_input)
        
        # 创建MCP客户端
        client = MCPClient(
            mcp=self.mcp,
            baseurl=os.getenv("openai_baseurl", "https://api.siliconflow.cn/v1"),
            apikey=os.getenv("openai_key", "sk-x"), 
            model=os.getenv("actions_model", "Qwen/Qwen3-235B-A22B-Instruct-2507"),
            prompt=prompt,
            actionKnowledge=None
        )

        # 查询知识库
        response = await client.chat(user_input)
        knowledge_response = extract_json_obj(response)
        
        logging.info(f"获取到知识库数据: {knowledge_response}")
        return knowledge_response
    
    def start_app(self, package_name: str) -> str:
        """
        启动应用
        
        Args:
            package_name: 应用包名
            
        Returns:
            启动结果
        """
        return self.phone.launch_app(package_name)
    
    def get_action_prompt_template(self, knowledge_content: str) -> str:
        """
        生成动作执行的提示词模板
        
        Args:
            knowledge_content: 从知识库获取的操作知识
            
        Returns:
            格式化的提示词字符串
        """
        return (
            "You are a professional mobile automation assistant. "
            "Your responsibilities are as follows: "
            "1. Understand the user's natural language request and convert it into executable phone operations, using both built-in tools and methods from the knowledge base (kn). "
            "2. For every operation: execute the step, and after each click or action, immediately call the GetPhoneState tool to obtain and analyze the phone's status to confirm whether the expected result was achieved. "
            "3. For complex tasks: break them down into simple, explicit steps (e.g., clicks, input, navigation) and execute them sequentially, verifying progress after each click with GetPhoneState. "
            "4. If an exception occurs or the expected outcome is not met: re-plan and adjust the sequence of operations to ensure the user's request is ultimately satisfied. "
            "5. Responses must be concise, clear, and provide practical operational suggestions when necessary. "
            "Your goal is to execute tasks efficiently, accurately, and reliably."
            + knowledge_content
        )
    
    def build_action_knowledge_prompt(self,user_input: str) -> str:
        """
        Build a prompt to extract app package and action_id from user input,
        call the get_action_knowledge tool, and return a formatted JSON response.

        :param user_input: The natural language input from the user.
        :return: A complete prompt string for the AI model.
        """
        prompt = f"""
    You are a smart assistant that processes user requests on a mobile device.

    Given a natural language input, do the following:
    1. Determine which app the user wants to open. Output the app's package name (e.g., com.tencent.mm).
    2. Identify the user's action intent and extract it as an `action_id` (e.g., "post to Moments").
    3. Simulate calling this function:
    get_action_knowledge(package_name: str, action_id: str) -> str
    (This returns a help string from the knowledge base for that app and action.)

    Then, return the result in this strict JSON format:
    {{
    "app": "<app package name>",
    "content": "<knowledge base result>"
    }}

    If no relevant app or content is found, return null for the field.

    Example input:
    "Please help me post a Moments update with the message: 'Feeling good today!'"

    Only output the JSON result, nothing else.

    ---

    User Input:
    "{user_input}"
    """
        return prompt
    
