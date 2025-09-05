#!/usr/bin/env python3
"""
Streamlit 配置界面
用于知识库管理的图形化界面
"""

import streamlit as st
import pandas as pd
import json
import os
import sys
import asyncio
import logging
import subprocess
from pathlib import Path
from datetime import datetime
from typing import List, Dict

# 添加项目根目录到路径
sys.path.append(str(Path(__file__).parent))

from core.Base.vector_db import MobileAgentHelper, MobileAgentVectorDB
from knowledge_manager import KnowledgeManager
from core.phone import Phone
from core.Base.AgentBase import MCPClient
from core.Agent.KnowledgeAssistant import KnowledgeAssistant
from core.Agent.ActionAgent import ActionAssistant
from config_loader import load_config_to_env, check_config
from dotenv import load_dotenv

# 配置文件路径
CONFIG_FILE = "config.json"


def load_config():
    """加载配置文件"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            st.error(f"加载配置文件失败: {e}")
            return {}
    return {}


def save_config(config):
    """保存配置文件"""
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        st.error(f"保存配置文件失败: {e}")
        return False


def apply_env_variables(config):
    """将配置应用到环境变量"""
    for key, value in config.items():
        if value:  # 只设置非空值
            os.environ[key] = value


def check_required_config():
    """检查必需的配置是否完整"""
    required_vars = ["openai_baseurl", "openai_key"]
    config = load_config()
    
    missing_vars = []
    for var in required_vars:
        if not config.get(var) and not os.getenv(var):
            missing_vars.append(var)
    
    return len(missing_vars) == 0, missing_vars


def config_setup_page():
    """配置设置页面"""
    st.title("⚙️ 系统配置")
    st.markdown("请配置必要的环境变量以使用知识库管理系统")
    
    # 加载现有配置
    config = load_config()
    
    # 配置表单
    with st.form("config_form"):
        st.subheader("🔧 API 配置")
        
        col1, col2 = st.columns(2)
        
        with col1:
            openai_baseurl = st.text_input(
                "OpenAI Base URL *",
                value=config.get("openai_baseurl", ""),
                placeholder="https://api.siliconflow.cn/v1",
                help="OpenAI API 的基础 URL"
            )
            
            openai_key = st.text_input(
                "OpenAI API Key *",
                value=config.get("openai_key", ""),
                placeholder="sk-...",
                type="password",
                help="OpenAI API 密钥"
            )
        
        with col2:
            adb_path = st.text_input(
                "ADB Path",
                value=config.get("ADB_PATH", "adb"),
                placeholder="adb",
                help="ADB 工具的路径（可选）"
            )
        
        st.subheader("🤖 模型配置")
        
        col3, col4 = st.columns(2)
        
        with col3:
            knowledge_assistant = st.text_input(
                "知识库模型",
                value=config.get("KnowledgeAssistant", "zai-org/GLM-4.5-Air"),
                placeholder="zai-org/GLM-4.5-Air",
                help="用于从知识库获取信息的模型"
            )
            
            check_assistant = st.text_input(
                "检查模型",
                value=config.get("CheckAssistant", "zai-org/GLM-4.5-Air"),
                placeholder="zai-org/GLM-4.5-Air",
                help="用于描述手机状态的模型"
            )
            
            action_assistant = st.text_input(
                "动作模型",
                value=config.get("ActionAssistant", "zai-org/GLM-4.5-Air"),
                placeholder="zai-org/GLM-4.5-Air",
                help="用于执行手机指令的模型"
            )
        
        with col4:
            embeding_model = st.text_input(
                "嵌入模型",
                value=config.get("embeding_model", "BAAI/bge-m3"),
                placeholder="BAAI/bge-m3",
                help="用于向量化知识库的模型"
            )
            
            reranker_model = st.text_input(
                "重排序模型",
                value=config.get("reranker_model", "BAAI/bge-reranker-v2-m3"),
                placeholder="BAAI/bge-reranker-v2-m3",
                help="用于排序检索结果的模型"
            )
            
            # 兼容旧版本的 actions_model 配置
            actions_model = st.text_input(
                "Actions Model (兼容)",
                value=config.get("actions_model", "zai-org/GLM-4.5-Air"),
                placeholder="zai-org/GLM-4.5-Air",
                help="用于动作执行的模型（兼容旧版本）"
            )
        
        st.subheader("🗄️ 数据库配置")
        
        db_path = st.text_input(
            "数据库路径",
            value=config.get("db_path", "mobile_agent_help.db"),
            placeholder="mobile_agent_help.db",
            help="SQLite 数据库文件路径"
        )
        
        # 提交按钮
        submitted = st.form_submit_button("💾 保存配置", type="primary")
        
        if submitted:
            # 验证必需字段
            if not openai_baseurl or not openai_key:
                st.error("❌ OpenAI Base URL 和 API Key 是必需的！")
                return False
            
            # 保存配置
            new_config = {
                "openai_baseurl": openai_baseurl,
                "openai_key": openai_key,
                "ADB_PATH": adb_path,
                "KnowledgeAssistant": knowledge_assistant,
                "CheckAssistant": check_assistant,
                "ActionAssistant": action_assistant,
                "embeding_model": embeding_model,
                "reranker_model": reranker_model,
                "actions_model": actions_model,  # 兼容旧版本
                "db_path": db_path
            }
            
            if save_config(new_config):
                # 应用到环境变量
                apply_env_variables(new_config)
                st.success("✅ 配置保存成功！")
                st.session_state.config_completed = True
                st.rerun()
                return True
            else:
                st.error("❌ 配置保存失败！")
                return False
    
    # 显示当前配置状态
    st.markdown("---")
    st.subheader("📊 当前配置状态")
    
    status_col1, status_col2, status_col3 = st.columns(3)
    
    with status_col1:
        st.markdown("**🔧 API 配置**")
        if config.get("openai_baseurl"):
            st.success(f"✅ OpenAI Base URL: {config['openai_baseurl']}")
        else:
            st.error("❌ OpenAI Base URL: 未配置")
        
        if config.get("openai_key"):
            masked_key = "*" * (len(config["openai_key"]) - 4) + config["openai_key"][-4:]
            st.success(f"✅ OpenAI API Key: {masked_key}")
        else:
            st.error("❌ OpenAI API Key: 未配置")
    
    with status_col2:
        st.markdown("**🤖 模型配置**")
        model_configs = [
            ("KnowledgeAssistant", "知识库模型"),
            ("CheckAssistant", "检查模型"),
            ("ActionAssistant", "动作模型"),
            ("embeding_model", "嵌入模型"),
            ("reranker_model", "重排序模型")
        ]
        
        for key, name in model_configs:
            if config.get(key):
                st.info(f"ℹ️ {name}: {config[key]}")
            else:
                st.warning(f"⚠️ {name}: 使用默认值")
    
    with status_col3:
        st.markdown("**🛠️ 其他配置**")
        if config.get("ADB_PATH"):
            st.info(f"ℹ️ ADB Path: {config['ADB_PATH']}")
        
        if config.get("db_path"):
            st.info(f"ℹ️ Database Path: {config['db_path']}")
            
        if config.get("actions_model"):
            st.info(f"ℹ️ Actions Model (兼容): {config['actions_model']}")
    
    return False


def init_session_state():
    """初始化 session state"""
    # 加载并应用配置
    config = load_config()
    apply_env_variables(config)
    
    # 检查配置是否完整
    config_complete, missing_vars = check_required_config()
    
    if 'config_completed' not in st.session_state:
        st.session_state.config_completed = config_complete
    
    if 'missing_config_vars' not in st.session_state:
        st.session_state.missing_config_vars = missing_vars
    
    if 'km' not in st.session_state and st.session_state.config_completed:
        try:
            # 使用配置的数据库路径
            db_path = config.get("db_path", "mobile_agent_help.db")
            st.session_state.km = KnowledgeManager(db_path)
        except Exception as e:
            st.error(f"初始化知识库管理器失败: {e}")
            st.session_state.config_completed = False
    
    if 'current_tab' not in st.session_state:
        st.session_state.current_tab = "手机助手"
    if 'refresh_data' not in st.session_state:
        st.session_state.refresh_data = False


def display_header():
    """显示页面头部"""
    st.set_page_config(
        page_title="手机助手知识库管理",
        page_icon="📱",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    st.title("📱 手机助手知识库管理系统")
    st.markdown("---")


def sidebar_navigation():
    """侧边栏导航"""
    st.sidebar.title("🎛️ 功能导航")
    
    tabs = ["手机助手", "应用管理", "文档管理", "搜索测试", "数据导入导出", "系统信息"]
    
    selected_tab = st.sidebar.radio("选择功能", tabs)
    st.session_state.current_tab = selected_tab
    
    st.sidebar.markdown("---")
    
    # 显示数据库状态
    st.sidebar.subheader("📊 数据库状态")
    try:
        if hasattr(st.session_state, 'km') and st.session_state.km:
            packages = st.session_state.km.vector_db.get_all_packages()
            total_apps = len(packages) if packages else 0
            
            total_docs = 0
            for pkg in packages:
                docs = st.session_state.km.vector_db.search_help_documents(package_name=pkg, k=1000)
                total_docs += len(docs)
                
            st.sidebar.metric("应用数量", total_apps)
            st.sidebar.metric("文档数量", total_docs)
        else:
            st.sidebar.warning("⚠️ 知识库未初始化")
        
    except Exception as e:
        st.sidebar.error(f"获取数据库状态失败: {e}")
    
    # 显示配置状态
    st.sidebar.markdown("---")
    st.sidebar.subheader("🔧 配置状态")
    
    config = load_config()
    if config.get("openai_baseurl") and config.get("openai_key"):
        st.sidebar.success("✅ 配置完整")
    else:
        st.sidebar.error("❌ 配置不完整")
    
    # 快速重新配置按钮
    if st.sidebar.button("🔧 重新配置", key="sidebar_reconfig"):
        st.session_state.config_completed = False
        st.rerun()


def app_management_tab():
    """应用管理标签页"""
    st.header("📦 应用管理")
    
    # 应用添加表单
    with st.expander("➕ 添加新应用", expanded=True):
        with st.form("add_app_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                package_name = st.text_input(
                    "包名 *", 
                    placeholder="例如: com.tencent.mm",
                    help="Android 应用的包名，必须唯一"
                )
                app_name = st.text_input(
                    "应用名称 *", 
                    placeholder="例如: 微信",
                    help="应用的中文名称"
                )
                
            with col2:
                app_name_en = st.text_input(
                    "英文名称", 
                    placeholder="例如: WeChat",
                    help="应用的英文名称（可选）"
                )
                description = st.text_area(
                    "应用描述", 
                    placeholder="简要描述这个应用的功能",
                    help="应用的详细描述（可选）"
                )
            
            submitted = st.form_submit_button("添加应用", type="primary")
            
            if submitted:
                if package_name and app_name:
                    try:
                        st.session_state.km.add_package_mapping(
                            package_name, app_name, app_name_en or None, description or None
                        )
                        st.success(f"✅ 成功添加应用: {app_name}")
                        st.session_state.refresh_data = True
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ 添加失败: {e}")
                else:
                    st.error("❌ 包名和应用名称不能为空")
    
    # 显示现有应用
    st.subheader("📋 现有应用列表")
    
    try:
        packages = st.session_state.km.vector_db.get_all_packages()
        
        if packages:
            apps_data = []
            for pkg in packages:
                app_info = st.session_state.km.vector_db.get_app_by_package(pkg)
                if app_info:
                    # 获取文档数量
                    docs = st.session_state.km.vector_db.search_help_documents(package_name=pkg, k=1000)
                    doc_count = len(docs)
                    
                    apps_data.append({
                        "包名": pkg,
                        "应用名称": app_info.get('app_name', ''),
                        "英文名称": app_info.get('app_name_en', '') or '-',
                        "描述": app_info.get('description', '') or '-',
                        "文档数量": doc_count
                    })
            
            if apps_data:
                df = pd.DataFrame(apps_data)
                
                # 使用 data_editor 显示可编辑表格
                st.markdown("💡 **提示**: 可以直接在表格中编辑应用信息")
                edited_df = st.data_editor(
                    df, 
                    use_container_width=True,
                    num_rows="dynamic",
                    column_config={
                        "包名": st.column_config.TextColumn("包名", disabled=True),
                        "应用名称": st.column_config.TextColumn("应用名称", required=True),
                        "英文名称": st.column_config.TextColumn("英文名称"),
                        "描述": st.column_config.TextColumn("描述"),
                        "文档数量": st.column_config.NumberColumn("文档数量", disabled=True)
                    }
                )
                
                # 保存更改按钮
                if st.button("💾 保存更改", type="primary"):
                    st.info("⚠️ 表格编辑功能需要进一步开发，目前仅支持查看")
                
            else:
                st.info("📝 还没有添加任何应用")
        else:
            st.info("📝 数据库中没有应用信息")
            
    except Exception as e:
        st.error(f"❌ 获取应用列表失败: {e}")


def document_management_tab():
    """文档管理标签页"""
    st.header("📚 文档管理")
    
    # 获取应用列表用于选择
    packages = st.session_state.km.vector_db.get_all_packages()
    if not packages:
        st.warning("⚠️ 请先添加应用信息")
        return
    
    app_options = {}
    for pkg in packages:
        app_info = st.session_state.km.vector_db.get_app_by_package(pkg)
        if app_info:
            app_options[f"{app_info['app_name']} ({pkg})"] = pkg
    
    # 文档添加表单
    with st.expander("➕ 添加新文档", expanded=True):
        with st.form("add_doc_form"):
            col1, col2 = st.columns([2, 1])
            
            with col1:
                selected_app = st.selectbox(
                    "选择应用 *", 
                    options=list(app_options.keys()),
                    help="选择要添加文档的应用"
                )
                title = st.text_input(
                    "文档标题 *", 
                    placeholder="例如: 发送朋友圈",
                    help="文档的标题，用于识别和搜索"
                )
                
            with col2:
                category = st.text_input(
                    "分类", 
                    placeholder="例如: 基础操作",
                    help="文档的分类（可选）"
                )
                tags_input = st.text_input(
                    "标签", 
                    placeholder="用逗号分隔，例如: 朋友圈,发送,分享",
                    help="文档的标签，用逗号分隔（可选）"
                )
            
            content = st.text_area(
                "文档内容 *", 
                placeholder="详细描述操作步骤...",
                height=150,
                help="详细的操作步骤和说明"
            )
            
            submitted = st.form_submit_button("添加文档", type="primary")
            
            if submitted:
                if selected_app and title and content:
                    try:
                        package_name = app_options[selected_app]
                        app_info = st.session_state.km.vector_db.get_app_by_package(package_name)
                        app_name = app_info['app_name']
                        
                        tags = [tag.strip() for tag in tags_input.split(',') if tag.strip()] if tags_input else None
                        
                        st.session_state.km.add_help_document(
                            package_name, app_name, title, content, category or None, tags
                        )
                        st.success(f"✅ 成功添加文档: {title}")
                        st.session_state.refresh_data = True
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ 添加失败: {e}")
                else:
                    st.error("❌ 应用、标题和内容不能为空")
    
    # 显示现有文档
    st.subheader("📄 现有文档列表")
    
    # 应用过滤器
    filter_col1, filter_col2 = st.columns([1, 1])
    with filter_col1:
        filter_app = st.selectbox(
            "筛选应用", 
            options=["全部"] + list(app_options.keys()),
            help="选择要查看的应用文档"
        )
    
    try:
        if filter_app == "全部":
            # 显示所有文档
            all_docs = []
            for pkg in packages:
                docs = st.session_state.km.vector_db.search_help_documents(package_name=pkg, k=1000)
                all_docs.extend(docs)
        else:
            # 显示特定应用的文档
            pkg = app_options[filter_app]
            all_docs = st.session_state.km.vector_db.search_help_documents(package_name=pkg, k=1000)
        
        if all_docs:
            docs_data = []
            for doc in all_docs:
                docs_data.append({
                    "应用": doc['app_name'],
                    "标题": doc['title'],
                    "分类": doc.get('category', '') or '-',
                    "标签": ', '.join(doc.get('tags', [])) if doc.get('tags') else '-',
                    "内容预览": doc['content'][:100] + "..." if len(doc['content']) > 100 else doc['content']
                })
            
            df = pd.DataFrame(docs_data)
            
            # 显示文档表格
            st.dataframe(
                df, 
                use_container_width=True,
                column_config={
                    "应用": st.column_config.TextColumn("应用", width="small"),
                    "标题": st.column_config.TextColumn("标题", width="medium"),
                    "分类": st.column_config.TextColumn("分类", width="small"),
                    "标签": st.column_config.TextColumn("标签", width="medium"),
                    "内容预览": st.column_config.TextColumn("内容预览", width="large")
                }
            )
            
            st.info(f"📊 共找到 {len(all_docs)} 个文档")
        else:
            st.info("📝 没有找到文档")
            
    except Exception as e:
        st.error(f"❌ 获取文档列表失败: {e}")


def search_test_tab():
    """搜索测试标签页"""
    st.header("🔍 搜索测试")
    
    # 搜索表单
    with st.form("search_form"):
        col1, col2, col3 = st.columns([2, 1, 1])
        
        with col1:
            search_query = st.text_input(
                "搜索关键词", 
                placeholder="输入要搜索的内容...",
                help="输入关键词搜索相关文档"
            )
            
        with col2:
            # 应用过滤
            packages = st.session_state.km.vector_db.get_all_packages()
            app_options = {"全部": None}
            
            for pkg in packages:
                app_info = st.session_state.km.vector_db.get_app_by_package(pkg)
                if app_info:
                    app_options[f"{app_info['app_name']} ({pkg})"] = pkg
            
            selected_app = st.selectbox("筛选应用", options=list(app_options.keys()))
            
        with col3:
            max_results = st.number_input("最大结果数", min_value=1, max_value=50, value=5)
        
        search_submitted = st.form_submit_button("🔍 搜索", type="primary")
    
    if search_submitted and search_query:
        try:
            package_filter = app_options[selected_app]
            results = st.session_state.km.search_documents(package_filter, search_query, k=max_results)
            
            if results:
                st.subheader(f"📋 搜索结果 ({len(results)} 条)")
                
                for i, result in enumerate(results, 1):
                    with st.expander(f"{i}. {result['title']} - {result['app_name']}", expanded=i<=3):
                        col1, col2 = st.columns([3, 1])
                        
                        with col1:
                            st.markdown(f"**内容**: {result['content']}")
                            if result.get('category'):
                                st.markdown(f"**分类**: {result['category']}")
                            if result.get('tags'):
                                st.markdown(f"**标签**: {', '.join(result['tags'])}")
                        
                        with col2:
                            score = result.get('rerank_score', result.get('similarity', 0))
                            st.metric("相似度", f"{score:.3f}")
                            st.markdown(f"**应用**: {result['app_name']}")
                            st.markdown(f"**包名**: {result['package_name']}")
            else:
                st.warning("❌ 没有找到相关文档")
                
        except Exception as e:
            st.error(f"❌ 搜索失败: {e}")
    
    elif search_submitted:
        st.warning("⚠️ 请输入搜索关键词")


def import_export_tab():
    """数据导入导出标签页"""
    st.header("📂 数据导入导出")
    
    col1, col2 = st.columns(2)
    
    # 导入功能
    with col1:
        st.subheader("📥 数据导入")
        
        # 文件上传
        uploaded_file = st.file_uploader(
            "选择 JSON 文件", 
            type=['json'],
            help="上传包含应用和文档数据的 JSON 文件"
        )
        
        if uploaded_file is not None:
            try:
                # 预览文件内容
                json_data = json.load(uploaded_file)
                
                st.subheader("📄 文件预览")
                
                # 显示应用数量
                apps_count = len(json_data.get('apps', []))
                docs_count = len(json_data.get('documents', []))
                
                col_a, col_b = st.columns(2)
                col_a.metric("应用数量", apps_count)
                col_b.metric("文档数量", docs_count)
                
                # 显示详细信息
                if json_data.get('apps'):
                    with st.expander("📱 应用列表"):
                        for app in json_data['apps']:
                            st.markdown(f"- **{app['app_name']}** ({app['package_name']})")
                
                if json_data.get('documents'):
                    with st.expander("📚 文档列表"):
                        for doc in json_data['documents'][:10]:  # 只显示前10个
                            st.markdown(f"- **{doc['title']}** - {doc['app_name']}")
                        if len(json_data['documents']) > 10:
                            st.markdown(f"... 还有 {len(json_data['documents']) - 10} 个文档")
                
                # 导入按钮
                if st.button("📥 确认导入", type="primary"):
                    try:
                        # 保存到临时文件
                        temp_file = "temp_import.json"
                        with open(temp_file, 'w', encoding='utf-8') as f:
                            json.dump(json_data, f, ensure_ascii=False, indent=2)
                        
                        # 导入数据
                        st.session_state.km.import_from_json(temp_file)
                        
                        # 清理临时文件
                        os.remove(temp_file)
                        
                        st.success("✅ 数据导入成功！")
                        st.session_state.refresh_data = True
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"❌ 导入失败: {e}")
                        
            except json.JSONDecodeError:
                st.error("❌ JSON 文件格式错误")
            except Exception as e:
                st.error(f"❌ 文件读取失败: {e}")
    
    # 导出功能
    with col2:
        st.subheader("📤 数据导出")
        
        # 导出选项
        export_app = st.selectbox(
            "选择导出范围",
            ["全部应用"] + [f"{app_info['app_name']} ({pkg})" 
                         for pkg in st.session_state.km.vector_db.get_all_packages()
                         for app_info in [st.session_state.km.vector_db.get_app_by_package(pkg)]
                         if app_info]
        )
        
        export_filename = st.text_input(
            "导出文件名",
            value=f"knowledge_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        
        if st.button("📤 导出数据", type="primary"):
            try:
                package_filter = None
                if export_app != "全部应用":
                    # 提取包名
                    package_filter = export_app.split("(")[-1].rstrip(")")
                
                # 导出数据
                st.session_state.km.export_to_json(export_filename, package_filter)
                
                # 提供下载链接
                if os.path.exists(export_filename):
                    with open(export_filename, 'r', encoding='utf-8') as f:
                        json_str = f.read()
                    
                    st.download_button(
                        label="⬇️ 下载导出文件",
                        data=json_str,
                        file_name=export_filename,
                        mime="application/json"
                    )
                    
                    # 清理文件
                    os.remove(export_filename)
                    
                    st.success("✅ 数据导出成功！")
                
            except Exception as e:
                st.error(f"❌ 导出失败: {e}")
    
    # 示例模板
    st.markdown("---")
    st.subheader("📋 JSON 格式示例")
    
    sample_data = {
        "apps": [
            {
                "package_name": "com.tencent.mm",
                "app_name": "微信",
                "app_name_en": "WeChat",
                "description": "腾讯公司开发的即时通讯软件"
            }
        ],
        "documents": [
            {
                "package_name": "com.tencent.mm",
                "app_name": "微信",
                "category": "基础操作",
                "title": "发送朋友圈",
                "content": "发送微信朋友圈需要以下步骤：1.点击导航栏底部的发现按钮，2.点击朋友圈，3.点击右上角拍照分享按钮...",
                "tags": ["朋友圈", "发送", "分享"]
            }
        ]
    }
    
    st.code(json.dumps(sample_data, ensure_ascii=False, indent=2), language="json")


def system_info_tab():
    """系统信息标签页"""
    st.header("⚙️ 系统信息")
    
    # 配置管理区域
    st.subheader("🔧 配置管理")
    
    col_config1, col_config2 = st.columns([1, 1])
    
    with col_config1:
        if st.button("⚙️ 重新配置环境变量", type="secondary"):
            st.session_state.config_completed = False
            st.rerun()
    
    with col_config2:
        config = load_config()
        if config:
            config_json = json.dumps(config, ensure_ascii=False, indent=2)
            st.download_button(
                "📥 下载配置文件",
                data=config_json,
                file_name="config.json",
                mime="application/json"
            )
    
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🗄️ 数据库信息")
        
        try:
            # 数据库文件信息
            if hasattr(st.session_state, 'km') and st.session_state.km:
                db_path = st.session_state.km.vector_db.db_path
                if os.path.exists(db_path):
                    file_size = os.path.getsize(db_path) / 1024 / 1024  # MB
                    modified_time = datetime.fromtimestamp(os.path.getmtime(db_path))
                    
                    st.metric("数据库文件大小", f"{file_size:.2f} MB")
                    st.metric("最后修改时间", modified_time.strftime("%Y-%m-%d %H:%M:%S"))
                    st.metric("数据库路径", db_path)
                else:
                    st.warning("⚠️ 数据库文件不存在")
                
                # 统计信息
                packages = st.session_state.km.vector_db.get_all_packages()
                total_apps = len(packages) if packages else 0
                
                total_docs = 0
                for pkg in packages:
                    docs = st.session_state.km.vector_db.search_help_documents(package_name=pkg, k=1000)
                    total_docs += len(docs)
                
                st.metric("应用总数", total_apps)
                st.metric("文档总数", total_docs)
            else:
                st.warning("⚠️ 知识库管理器未初始化")
            
        except Exception as e:
            st.error(f"❌ 获取数据库信息失败: {e}")
    
    with col2:
        st.subheader("🔧 环境配置")
        
        # 环境变量检查
        config = load_config()
        env_vars = {
            "openai_baseurl": "OpenAI Base URL",
            "openai_key": "OpenAI API Key", 
            "KnowledgeAssistant": "知识库模型",
            "CheckAssistant": "检查模型",
            "ActionAssistant": "动作模型",
            "embeding_model": "嵌入模型",
            "reranker_model": "重排序模型",
            "actions_model": "Actions Model (兼容)",
            "ADB_PATH": "ADB Path"
        }
        
        for var, display_name in env_vars.items():
            # 优先使用配置文件中的值，其次是环境变量
            value = config.get(var) or os.getenv(var)
            if value:
                if "key" in var.lower():
                    # API Key 类型的值进行掩码处理
                    masked_value = "*" * (len(value) - 4) + value[-4:] if len(value) > 4 else "***"
                    st.success(f"✅ {display_name}: {masked_value}")
                else:
                    st.success(f"✅ {display_name}: {value}")
            else:
                st.error(f"❌ {display_name}: 未设置")
        
        # 系统信息
        st.subheader("💻 系统信息")
        st.info(f"Python 版本: {sys.version}")
        st.info(f"工作目录: {os.getcwd()}")
        st.info(f"配置文件: {os.path.abspath(CONFIG_FILE)}")
    
    # 危险操作区域
    st.markdown("---")
    st.subheader("⚠️ 危险操作")
    
    danger_col1, danger_col2 = st.columns(2)
    
    with danger_col1:
        with st.expander("🗑️ 清空数据库", expanded=False):
            st.warning("⚠️ 此操作将删除所有应用和文档数据，且不可恢复！")
            
            confirm_text = st.text_input("输入 'DELETE ALL' 确认删除", key="delete_db_confirm")
            
            if st.button("🗑️ 确认清空数据库", type="secondary", key="delete_db_btn"):
                if confirm_text == "DELETE ALL":
                    try:
                        # 这里需要实现清空数据库的功能
                        st.error("❌ 清空功能尚未实现")
                    except Exception as e:
                        st.error(f"❌ 清空失败: {e}")
                else:
                    st.error("❌ 确认文字输入错误")
    
    with danger_col2:
        with st.expander("🔧 重置配置", expanded=False):
            st.warning("⚠️ 此操作将删除所有配置信息，需要重新设置！")
            
            confirm_reset = st.text_input("输入 'RESET CONFIG' 确认重置", key="reset_config_confirm")
            
            if st.button("🔧 确认重置配置", type="secondary", key="reset_config_btn"):
                if confirm_reset == "RESET CONFIG":
                    try:
                        if os.path.exists(CONFIG_FILE):
                            os.remove(CONFIG_FILE)
                        st.success("✅ 配置已重置")
                        st.session_state.config_completed = False
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ 重置失败: {e}")
                else:
                    st.error("❌ 确认文字输入错误")


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
            return None, "❌ 未检测到任何连接的 ADB 设备。"

        # 如果只有一个设备，直接使用
        if len(device_ids) == 1:
            selected_id = device_ids[0]
            message = f"✅ 唯一设备已自动选择: {selected_id}"
        else:
            # 对于多个设备，返回设备列表让用户在UI中选择
            return device_ids, "检测到多个设备"

        # 获取 adb 路径（支持环境变量或默认 'adb'）
        adb_path = os.getenv("ADB_PATH", "adb")

        # 初始化 Phone 实例
        myphone = Phone(id=selected_id, adb_path=adb_path)
        return myphone, message

    except subprocess.CalledProcessError as e:
        return None, f"❌ 执行 ADB 命令失败: {e}"
    except Exception as e:
        return None, f"❌ 初始化设备时发生未知错误: {e}"


async def execute_phone_task(user_input, selected_device_id=None):
    """
    执行手机任务的异步函数
    """
    try:
        # 首先加载配置文件中的环境变量
        load_config_to_env()
        # 然后加载 .env 文件（会覆盖配置文件中的同名变量）
        load_dotenv()
        
        # 检查配置完整性
        if not check_config():
            return False, "❌ 系统配置不完整，请先完成系统配置"
        
        # 初始化手机
        if selected_device_id:
            # 使用指定的设备ID
            adb_path = os.getenv("ADB_PATH", "adb")
            myphone = Phone(id=selected_device_id, adb_path=adb_path)
            phone_status = f"✅ 使用设备: {selected_device_id}"
        else:
            # 自动检测设备
            result = init_phone()
            if isinstance(result[0], list):
                return False, f"需要选择设备: {result[0]}"
            elif result[0] is None:
                return False, result[1]
            else:
                myphone = result[0]
                phone_status = result[1]
        
        # 初始化知识助手
        knowledge_assistant = KnowledgeAssistant(myphone)
        
        # 初始化动作助手
        action_agent = ActionAssistant(myphone)
        
        # 处理用户请求
        knowledge_response = await knowledge_assistant.process_user_request(user_input)
        
        kn = knowledge_response["content"]
        app_start_result = knowledge_assistant.start_app(knowledge_response["app"])
        
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
        
        return True, {
            "phone_status": phone_status,
            "app_start_result": app_start_result,
            "knowledge_response": knowledge_response,
            "final_response": response
        }
        
    except Exception as e:
        return False, f"❌ 执行失败: {str(e)}"


def phone_assistant_tab():
    """手机助手执行标签页"""
    st.header("📱 手机助手执行")
    
    # 设备状态检查
    st.subheader("📋 设备状态")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        if st.button("🔍 检测设备", type="secondary"):
            with st.spinner("正在检测ADB设备..."):
                result = init_phone()
                if isinstance(result[0], list):
                    st.session_state.available_devices = result[0]
                    st.success(f"✅ 检测到 {len(result[0])} 个设备")
                    for i, device in enumerate(result[0]):
                        st.info(f"设备 {i+1}: {device}")
                elif result[0] is None:
                    st.error(result[1])
                    st.session_state.available_devices = []
                else:
                    st.success(result[1])
                    st.session_state.selected_device = result[0].id
    
    with col2:
        # 设备选择（如果有多个设备）
        if hasattr(st.session_state, 'available_devices') and st.session_state.available_devices:
            selected_device = st.selectbox(
                "选择设备",
                st.session_state.available_devices,
                help="选择要使用的ADB设备"
            )
            st.session_state.selected_device_id = selected_device
    
    st.markdown("---")
    
    # 用户请求输入
    st.subheader("💬 输入请求")
    
    user_input = st.text_area(
        "请描述您希望手机执行的操作",
        placeholder="例如：帮我发个朋友圈，内容是'今天天气真好'",
        height=100,
        help="详细描述您想要手机执行的操作"
    )
    
    # 执行按钮
    col_exec1, col_exec2, col_exec3 = st.columns([1, 2, 1])
    
    with col_exec2:
        if st.button("🚀 执行任务", type="primary", disabled=not user_input):
            if not user_input.strip():
                st.error("❌ 请输入有效的请求")
            else:
                # 检查是否选择了设备
                selected_device_id = getattr(st.session_state, 'selected_device_id', None)
                
                with st.spinner("正在执行任务，请稍候..."):
                    # 创建异步任务执行
                    try:
                        # 使用 asyncio.run 来执行异步函数
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        success, result = loop.run_until_complete(
                            execute_phone_task(user_input, selected_device_id)
                        )
                        loop.close()
                        
                        if success:
                            st.session_state.last_execution_result = result
                            st.success("✅ 任务执行完成！")
                        else:
                            st.error(result)
                            
                    except Exception as e:
                        st.error(f"❌ 执行过程中发生错误: {str(e)}")
    
    # 显示执行结果
    if hasattr(st.session_state, 'last_execution_result'):
        st.markdown("---")
        st.subheader("📊 执行结果")
        
        result = st.session_state.last_execution_result
        
        # 设备状态
        with st.expander("📱 设备状态", expanded=True):
            st.info(result["phone_status"])
        
        # 应用启动结果
        with st.expander("🚀 应用启动", expanded=True):
            st.code(result["app_start_result"], language="text")
        
        # 知识库查询结果
        with st.expander("🧠 知识库查询", expanded=True):
            st.json(result["knowledge_response"])
        
        # 最终执行结果
        with st.expander("✅ 最终结果", expanded=True):
            st.markdown(result["final_response"])
        
        # 清除结果按钮
        if st.button("🗑️ 清除结果"):
            if hasattr(st.session_state, 'last_execution_result'):
                delattr(st.session_state, 'last_execution_result')
            st.rerun()
    
    # 使用说明
    st.markdown("---")
    st.subheader("📖 使用说明")
    
    with st.expander("💡 如何使用手机助手", expanded=False):
        st.markdown("""
        **准备工作：**
        1. 确保手机已连接到电脑并启用USB调试
        2. 确保ADB工具已正确安装并配置
        3. 确保系统配置已完成（API密钥等）
        
        **操作步骤：**
        1. 点击"检测设备"确认手机连接状态
        2. 如果有多个设备，选择要使用的设备
        3. 在文本框中详细描述您希望执行的操作
        4. 点击"执行任务"开始自动化操作
        
        **注意事项：**
        - 请确保手机屏幕处于解锁状态
        - 执行过程中请勿操作手机
        - 复杂操作可能需要较长时间
        - 如果执行失败，请检查网络连接和API配置
        """)
    
    # 常见问题
    with st.expander("❓ 常见问题", expanded=False):
        st.markdown("""
        **Q: 为什么检测不到设备？**
        A: 请检查USB调试是否开启，ADB驱动是否正确安装
        
        **Q: 任务执行失败怎么办？**
        A: 检查网络连接、API配置和手机状态，确保所有配置正确
        
        **Q: 可以执行什么类型的操作？**
        A: 支持发送消息、操作应用、查看信息等基础手机操作
        
        **Q: 执行过程中可以中断吗？**
        A: 建议等待任务完成，强制中断可能导致状态异常
        """)


def main():
    """主函数"""
    display_header()
    init_session_state()
    
    # 检查配置是否完整
    if not st.session_state.config_completed:
        # 显示配置页面
        if config_setup_page():
            st.rerun()
        return
    
    # 配置完成后显示主界面
    sidebar_navigation()
    
    # 根据选择的标签页显示对应内容
    if st.session_state.current_tab == "手机助手":
        phone_assistant_tab()
    elif st.session_state.current_tab == "应用管理":
        app_management_tab()
    elif st.session_state.current_tab == "文档管理":
        document_management_tab()
    elif st.session_state.current_tab == "搜索测试":
        search_test_tab()
    elif st.session_state.current_tab == "数据导入导出":
        import_export_tab()
    elif st.session_state.current_tab == "系统信息":
        system_info_tab()
    
    # 页脚
    st.markdown("---")
    st.markdown(
        "<div style='text-align: center; color: gray;'>"
        "📱 手机助手知识库管理系统 | "
        f"当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        "</div>", 
        unsafe_allow_html=True
    )


if __name__ == "__main__":
    main()
