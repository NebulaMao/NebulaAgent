#!/usr/bin/env python3
"""
知识库管理工具
用于添加、编辑和管理手机操作助手的帮助文档
"""

import os
import sys
import json
import argparse
import logging
from typing import List
from pathlib import Path
from dotenv import load_dotenv

# 添加项目根目录到路径
sys.path.append(str(Path(__file__).parent))

from core.Base.vector_db import MobileAgentHelper, MobileAgentVectorDB

# 加载环境变量
load_dotenv()

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class KnowledgeManager:
    """知识库管理器"""
    
    def __init__(self, db_path: str = "mobile_agent_help.db"):
        self.helper = MobileAgentHelper(db_path)
        self.vector_db = self.helper.vector_db
        
    def add_package_mapping(self, package_name: str, app_name: str, 
                           app_name_en: str = None, description: str = None):
        """添加应用包名映射"""
        self.vector_db.add_package_mapping(package_name, app_name, app_name_en, description)
        print(f"✅ 成功添加应用映射: {package_name} -> {app_name}")
        
    def add_help_document(self, package_name: str, app_name: str, title: str, 
                         content: str, category: str = None, tags: List[str] = None):
        """添加帮助文档"""
        self.vector_db.add_help_document(package_name, app_name, title, content, category, tags)
        print(f"✅ 成功添加帮助文档: {app_name} - {title}")
        
    def search_documents(self, package_name: str = None, query: str = "", k: int = 5):
        """搜索帮助文档"""
        results = self.vector_db.search_help_documents(package_name, query, k=k)
        if not results:
            print("❌ 未找到相关文档")
            return
            
        print(f"🔍 找到 {len(results)} 个相关文档:")
        for i, result in enumerate(results, 1):
            score = result.get('rerank_score', result.get('similarity', 0))
            print(f"\n{i}. {result['title']} (相似度: {score:.3f})")
            print(f"   应用: {result['app_name']} ({result['package_name']})")
            print(f"   分类: {result.get('category', '未分类')}")
            print(f"   内容: {result['content'][:100]}...")
            
    def list_apps(self):
        """列出所有应用"""
        packages = self.vector_db.get_all_packages()
        if not packages:
            print("❌ 数据库中没有应用信息")
            return
            
        print("📱 已注册的应用:")
        for pkg in packages:
            app_info = self.vector_db.get_app_by_package(pkg)
            if app_info:
                print(f"  • {app_info['app_name']} ({pkg})")
                if app_info.get('description'):
                    print(f"    描述: {app_info['description']}")
                    
    def list_documents_for_app(self, package_name: str):
        """列出指定应用的所有文档"""
        results = self.vector_db.search_help_documents(package_name=package_name, k=50)
        if not results:
            print(f"❌ 应用 {package_name} 没有帮助文档")
            return
            
        app_info = self.vector_db.get_app_by_package(package_name)
        app_name = app_info['app_name'] if app_info else package_name
        
        print(f"📚 {app_name} 的帮助文档:")
        for i, result in enumerate(results, 1):
            print(f"  {i}. {result['title']}")
            if result.get('category'):
                print(f"     分类: {result['category']}")
            if result.get('tags'):
                print(f"     标签: {', '.join(result['tags'])}")
                
    def import_from_json(self, json_file: str):
        """从JSON文件批量导入"""
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            # 导入应用映射
            if 'apps' in data:
                for app in data['apps']:
                    self.add_package_mapping(
                        app['package_name'],
                        app['app_name'],
                        app.get('app_name_en'),
                        app.get('description')
                    )
                    
            # 导入帮助文档
            if 'documents' in data:
                for doc in data['documents']:
                    self.add_help_document(
                        doc['package_name'],
                        doc['app_name'],
                        doc['title'],
                        doc['content'],
                        doc.get('category'),
                        doc.get('tags')
                    )
                    
            print(f"✅ 成功从 {json_file} 导入数据")
            
        except Exception as e:
            print(f"❌ 导入失败: {e}")
            
    def export_to_json(self, output_file: str, package_name: str = None):
        """导出到JSON文件"""
        try:
            data = {"apps": [], "documents": []}
            
            # 导出应用映射
            if package_name:
                app_info = self.vector_db.get_app_by_package(package_name)
                if app_info:
                    data["apps"].append(app_info)
            else:
                # 导出所有应用
                packages = self.vector_db.get_all_packages()
                for pkg in packages:
                    app_info = self.vector_db.get_app_by_package(pkg)
                    if app_info:
                        data["apps"].append(app_info)
                        
            # 导出文档
            results = self.vector_db.search_help_documents(package_name=package_name, k=1000)
            for result in results:
                doc_data = {
                    "package_name": result["package_name"],
                    "app_name": result["app_name"],
                    "title": result["title"],
                    "content": result["content"],
                    "category": result.get("category"),
                    "tags": result.get("tags")
                }
                data["documents"].append(doc_data)
                
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
            print(f"✅ 成功导出到 {output_file}")
            
        except Exception as e:
            print(f"❌ 导出失败: {e}")


def interactive_mode():
    """交互式添加模式"""
    km = KnowledgeManager()
    
    print("🤖 欢迎使用知识库管理工具 - 交互模式")
    print("输入 'help' 查看可用命令，输入 'quit' 退出")
    
    while True:
        try:
            cmd = input("\n📝 请输入命令: ").strip()
            
            if cmd.lower() in ['quit', 'exit', 'q']:
                print("👋 再见!")
                break
                
            elif cmd.lower() == 'help':
                print("""
可用命令:
  add-app     - 添加应用映射
  add-doc     - 添加帮助文档
  search      - 搜索文档
  list-apps   - 列出所有应用
  list-docs   - 列出指定应用的文档
  import      - 从JSON文件导入
  export      - 导出到JSON文件
  help        - 显示此帮助
  quit        - 退出程序
                """)
                
            elif cmd.lower() == 'add-app':
                package_name = input("包名 (如 com.tencent.mm): ").strip()
                app_name = input("应用名称 (如 微信): ").strip()
                app_name_en = input("英文名称 (可选): ").strip() or None
                description = input("应用描述 (可选): ").strip() or None
                
                if package_name and app_name:
                    km.add_package_mapping(package_name, app_name, app_name_en, description)
                else:
                    print("❌ 包名和应用名称不能为空")
                    
            elif cmd.lower() == 'add-doc':
                package_name = input("包名 (如 com.tencent.mm): ").strip()
                if not package_name:
                    print("❌ 包名不能为空")
                    continue
                    
                app_info = km.vector_db.get_app_by_package(package_name)
                if not app_info:
                    print(f"❌ 未找到包名 {package_name} 的应用信息，请先添加应用映射")
                    continue
                    
                app_name = app_info['app_name']
                title = input("文档标题 (如 '发送朋友圈'): ").strip()
                category = input("分类 (可选): ").strip() or None
                
                print("请输入文档内容 (多行输入，输入 'END' 结束):")
                content_lines = []
                while True:
                    line = input()
                    if line.strip() == 'END':
                        break
                    content_lines.append(line)
                content = '\n'.join(content_lines)
                
                tags_str = input("标签 (用逗号分隔，可选): ").strip()
                tags = [tag.strip() for tag in tags_str.split(',') if tag.strip()] if tags_str else None
                
                if title and content:
                    km.add_help_document(package_name, app_name, title, content, category, tags)
                else:
                    print("❌ 标题和内容不能为空")
                    
            elif cmd.lower() == 'search':
                package_name = input("包名 (可选): ").strip() or None
                query = input("搜索关键词: ").strip()
                k = input("返回结果数量 (默认5): ").strip()
                k = int(k) if k.isdigit() else 5
                
                km.search_documents(package_name, query, k)
                
            elif cmd.lower() == 'list-apps':
                km.list_apps()
                
            elif cmd.lower() == 'list-docs':
                package_name = input("包名: ").strip()
                if package_name:
                    km.list_documents_for_app(package_name)
                else:
                    print("❌ 包名不能为空")
                    
            elif cmd.lower() == 'import':
                json_file = input("JSON文件路径: ").strip()
                if os.path.exists(json_file):
                    km.import_from_json(json_file)
                else:
                    print("❌ 文件不存在")
                    
            elif cmd.lower() == 'export':
                output_file = input("输出文件路径: ").strip()
                package_name = input("包名 (可选，留空导出全部): ").strip() or None
                km.export_to_json(output_file, package_name)
                
            else:
                print("❌ 未知命令，输入 'help' 查看可用命令")
                
        except KeyboardInterrupt:
            print("\n👋 再见!")
            break
        except Exception as e:
            print(f"❌ 错误: {e}")


def create_sample_json():
    """创建示例JSON文件"""
    sample_data = {
        "apps": [
            {
                "package_name": "com.tencent.mm",
                "app_name": "微信",
                "app_name_en": "WeChat",
                "description": "腾讯公司开发的即时通讯软件"
            },
            {
                "package_name": "com.eg.android.AlipayGphone",
                "app_name": "支付宝",
                "app_name_en": "Alipay",
                "description": "蚂蚁集团开发的移动支付平台"
            }
        ],
        "documents": [
            {
                "package_name": "com.tencent.mm",
                "app_name": "微信",
                "category": "基础操作",
                "title": "发送朋友圈",
                "content": "发送微信朋友圈需要以下步骤：1.点击导航栏底部的发现按钮，2.点击朋友圈，3.点击右上角拍照分享按钮，4.点击从相册选择，5.让用户选择图片，以及配置好朋友圈,结束工具调用。",
                "tags": ["朋友圈", "发送", "分享"]
            },
            {
                "package_name": "com.tencent.mm",
                "app_name": "微信",
                "category": "基础操作", 
                "title": "发送消息",
                "content": "发送微信消息的步骤：1.打开微信应用，2.点击要发送消息的联系人或群聊，3.在输入框中输入消息内容，4.点击发送按钮。",
                "tags": ["消息", "聊天", "发送"]
            }
        ]
    }
    
    with open("knowledge_sample.json", "w", encoding="utf-8") as f:
        json.dump(sample_data, f, ensure_ascii=False, indent=2)
    
    print("✅ 已创建示例文件: knowledge_sample.json")


def main():
    parser = argparse.ArgumentParser(description="手机操作助手知识库管理工具")
    parser.add_argument("--interactive", "-i", action="store_true", help="启动交互模式")
    parser.add_argument("--add-app", action="store_true", help="添加应用映射")
    parser.add_argument("--add-doc", action="store_true", help="添加帮助文档")
    parser.add_argument("--package", "-p", help="应用包名")
    parser.add_argument("--app-name", "-a", help="应用名称")
    parser.add_argument("--title", "-t", help="文档标题")
    parser.add_argument("--content", "-c", help="文档内容")
    parser.add_argument("--category", help="文档分类")
    parser.add_argument("--tags", help="文档标签 (逗号分隔)")
    parser.add_argument("--search", "-s", help="搜索关键词")
    parser.add_argument("--list-apps", action="store_true", help="列出所有应用")
    parser.add_argument("--list-docs", action="store_true", help="列出指定应用的文档")
    parser.add_argument("--import-json", help="从JSON文件导入")
    parser.add_argument("--export-json", help="导出到JSON文件")
    parser.add_argument("--create-sample", action="store_true", help="创建示例JSON文件")
    parser.add_argument("--db-path", default="mobile_agent_help.db", help="数据库文件路径")
    
    args = parser.parse_args()
    
    if args.create_sample:
        create_sample_json()
        return
        
    if args.interactive:
        interactive_mode()
        return
        
    km = KnowledgeManager(args.db_path)
    
    if args.add_app:
        if not args.package or not args.app_name:
            print("❌ 添加应用需要 --package 和 --app-name 参数")
            return
        km.add_package_mapping(args.package, args.app_name)
        
    elif args.add_doc:
        if not args.package or not args.title or not args.content:
            print("❌ 添加文档需要 --package, --title 和 --content 参数")
            return
        
        app_info = km.vector_db.get_app_by_package(args.package)
        if not app_info:
            print(f"❌ 未找到包名 {args.package} 的应用信息，请先添加应用映射")
            return
            
        tags = [tag.strip() for tag in args.tags.split(',')] if args.tags else None
        km.add_help_document(args.package, app_info['app_name'], args.title, 
                           args.content, args.category, tags)
        
    elif args.search:
        km.search_documents(args.package, args.search)
        
    elif args.list_apps:
        km.list_apps()
        
    elif args.list_docs:
        if not args.package:
            print("❌ 列出文档需要 --package 参数")
            return
        km.list_documents_for_app(args.package)
        
    elif args.import_json:
        km.import_from_json(args.import_json)
        
    elif args.export_json:
        km.export_to_json(args.export_json, args.package)
        
    else:
        parser.print_help()


if __name__ == "__main__":
    main()