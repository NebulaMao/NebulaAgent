import asyncio
import logging
from dotenv import load_dotenv
from core.phone import Phone
from core.Base.AgentBase import MCPClient
from core.Agent.KnowledgeAssistant import KnowledgeAssistant
from core.Agent.ActionAgent import ActionAssistant
import os
import subprocess

# 导入配置加载器
from config_loader import load_config_to_env, check_config

# 首先加载配置文件中的环境变量
load_config_to_env()

# 然后加载 .env 文件（会覆盖配置文件中的同名变量）
load_dotenv()


def init_phone():
    """
    初始化一个 Phone 实例：
    1. 获取所有通过 ADB 连接的设备
    2. 若有多个设备，提示用户选择其中一个
    3. 使用选择的设备 ID 和环境变量指定的 adb_path 创建 Phone 实例
    4. 返回 Phone 实例
    """
    try:
        # 获取 ADB 设备列表
        result = subprocess.run(['adb', 'devices'], capture_output=True, text=True, check=True)
        lines = result.stdout.strip().split('\n')[1:]  # 跳过第一行 header

        # 解析在线设备
        device_lines = [line for line in lines if line.strip() and '\tdevice' in line]
        device_ids = [line.split('\t')[0] for line in device_lines]

        if not device_ids:
            print("❌ 未检测到任何连接的 ADB 设备。")
            return None

        # 如果只有一个设备，直接使用
        if len(device_ids) == 1:
            selected_id = device_ids[0]
            print(f"✅ 唯一设备已自动选择: {selected_id}")
        else:
            # 多个设备，让用户选择
            print("📱 检测到多个设备，请选择要使用的设备：")
            for idx, device_id in enumerate(device_ids):
                print(f"  {idx + 1}. {device_id}")

            while True:
                try:
                    choice = int(input("请输入设备编号: ")) - 1
                    if 0 <= choice < len(device_ids):
                        selected_id = device_ids[choice]
                        break
                    else:
                        print(f"请输入 1 到 {len(device_ids)} 之间的数字。")
                except ValueError:
                    print("请输入有效数字。")

            print(f"✅ 已选择设备: {selected_id}")

        # 获取 adb 路径（支持环境变量或默认 'adb'）
        adb_path = os.getenv("ADB_PATH", "adb")

        # 初始化 Phone 实例
        myphone = Phone(id=selected_id, adb_path=adb_path)
        return myphone

    except subprocess.CalledProcessError as e:
        print(f"❌ 执行 ADB 命令失败: {e}")
        print(f"错误输出: {e.stderr}")
        return None
    except Exception as e:
        print(f"❌ 初始化设备时发生未知错误: {e}")
        return None



async def main():
    # 检查配置完整性
    print("🔧 检查系统配置...")
    if not check_config():
        print("\n❌ 系统配置不完整，程序退出")
        print("💡 请先运行配置界面完成系统配置:")
        print("   ./start_config_ui.sh")
        exit(1)
    
    print("正在初始化手机...")
    myphone = init_phone()
    if myphone is None:
        print("❌ 手机初始化失败，请检查设备连接或 ADB 配置。")
        exit(1)
    print("✅ 手机初始化成功！")
    # 初始化知识助手
    print("正在初始化知识助手...")
    knowledge_assistant = KnowledgeAssistant(myphone)
    print("✅ 知识助手初始化成功！")
    print("正在初始化动作助手...")
    action_agent = ActionAssistant(myphone)
    print("✅ 动作助手初始化成功！")
    user_input = input("请输入您的请求: ")
    logging.basicConfig(level=logging.INFO)
    logging.info("=============== 开始查询知识库并打开应用 ===============")
    
    # 使用KnowledgeAssistant处理用户请求
    knowledge_response = await knowledge_assistant.process_user_request(user_input)
    logging.info(f"获取到数据: {knowledge_response}")
    
    kn = knowledge_response["content"]
    print(knowledge_assistant.start_app(knowledge_response["app"]))
    
    # 获取动作执行的提示词模板
    action_prompt = knowledge_assistant.get_action_prompt_template(kn)
    
    client = MCPClient(
        mcp=action_agent.get_mcp(),
        baseurl=os.getenv("openai_baseurl", "https://api.siliconflow.cn/v1"),
        apikey=os.getenv("openai_key", "sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"),
        model=os.getenv("actions_model", "zai-org/glm-4.5"),
        prompt=action_prompt,
        actionKnowledge=kn
    )
    client.set_state_invalidating_tools(["GetPhoneState", "touch_action"])

    response = await client.chat("当前已经打开"+knowledge_response["app"] + ","+ user_input)
    print(response)


if __name__ == "__main__":
    print("选择的actions_model:", os.getenv("actions_model", "zai-org/glm-4.5"))
    asyncio.run(main())
