#!/usr/bin/env python3
"""
手机助手主程序配置模块
负责从配置文件加载环境变量并初始化系统
"""

import json
import os
import sys
from pathlib import Path

# 配置文件路径
CONFIG_FILE = "config.json"


def load_config_to_env():
    """
    从配置文件加载环境变量
    这个函数应该在程序启动时首先调用
    """
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # 将配置应用到环境变量（只有在环境变量未设置时才设置）
            for key, value in config.items():
                if value and not os.getenv(key):
                    os.environ[key] = value
            
            print(f"✅ 已从 {CONFIG_FILE} 加载配置")
            return True
            
        except Exception as e:
            print(f"❌ 加载配置文件失败: {e}")
            return False
    else:
        print(f"⚠️  配置文件 {CONFIG_FILE} 不存在")
        return False


def check_config():
    """
    检查必要的配置是否完整
    """
    required_vars = ["openai_baseurl", "openai_key"]
    missing_vars = []
    
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print("❌ 缺少必要的环境变量:")
        for var in missing_vars:
            print(f"   - {var}")
        print("\n💡 请运行以下命令打开配置界面:")
        print("   ./start_config_ui.sh")
        print("   或者")
        print("   streamlit run streamlit_config.py")
        return False
    
    print("✅ 配置检查通过")
    return True


def show_current_config():
    """
    显示当前配置信息（用于调试）
    """
    print("\n📋 当前配置:")
    config_vars = ["openai_baseurl", "openai_key", "actions_model", "ADB_PATH"]
    
    for var in config_vars:
        value = os.getenv(var)
        if value:
            if "key" in var.lower():
                # API Key 类型的值进行掩码处理
                masked_value = "*" * (len(value) - 4) + value[-4:] if len(value) > 4 else "***"
                print(f"   {var}: {masked_value}")
            else:
                print(f"   {var}: {value}")
        else:
            print(f"   {var}: 未设置")


if __name__ == "__main__":
    # 测试配置加载
    load_config_to_env()
    show_current_config()
    print(f"\n配置完整性检查: {'通过' if check_config() else '失败'}")
