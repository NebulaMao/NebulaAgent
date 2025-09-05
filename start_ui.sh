#!/bin/bash

# 启动 Streamlit 知识库配置界面

echo "🚀 启动手机助手UI中..."

# 设置 Streamlit 配置
export STREAMLIT_SERVER_PORT=8501
export STREAMLIT_SERVER_ADDRESS=0.0.0.0
export STREAMLIT_SERVER_HEADLESS=true

streamlit run main_ui.py --server.port 8501 --server.address 0.0.0.0
