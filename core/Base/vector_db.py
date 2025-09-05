import sqlite3
import numpy as np
from typing import List, Dict, Optional
import requests
import os
import logging
import json

class MobileAgentVectorDB:
    def __init__(self, db_path: str = "mobile_agent_help.db", api_key: str = None):
        self.db_path = db_path
        self.api_key = api_key
        self.embedding_url = os.getenv("openai_baseurl") + "/embeddings"
        self.rerank_url = os.getenv("openai_baseurl") + "/rerank"
        self.logger = logging.getLogger(__name__)
        self._init_db()
        
    def _init_db(self):
        """初始化数据库 - 支持包名和帮助文档"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 主帮助文档表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS help_documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                package_name TEXT NOT NULL,
                app_name TEXT NOT NULL,
                category TEXT,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                tags TEXT,
                embedding BLOB NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(package_name, title)
            )
        ''')
        
        # 操作方法表（保留原有功能）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS operations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                package_name TEXT NOT NULL,
                app_name TEXT NOT NULL,
                query TEXT NOT NULL,
                method TEXT NOT NULL,
                embedding BLOB NOT NULL,
                UNIQUE(package_name, query)
            )
        ''')
        
        # 包名映射表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS package_mapping (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                package_name TEXT UNIQUE NOT NULL,
                app_name TEXT NOT NULL,
                app_name_en TEXT,
                description TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def _get_embedding(self, text: str) -> np.ndarray:
        """使用SiliconFlow API获取embedding"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": os.getenv("embeding_model"),
            "input": text
        }
        
        try:
            response = requests.post(self.embedding_url, json=payload, headers=headers, timeout=10)
            response.raise_for_status()
            result = response.json()
            embedding = np.array(result['data'][0]['embedding'], dtype=np.float32)
            return embedding
        except Exception as e:
            self.logger.error(f"Error getting embedding: {e}")
            return np.zeros(1024, dtype=np.float32)
    
    def add_package_mapping(self, package_name: str, app_name: str, app_name_en: str = None, description: str = None):
        """添加包名映射"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO package_mapping (package_name, app_name, app_name_en, description)
                VALUES (?, ?, ?, ?)
            ''', (package_name, app_name, app_name_en, description))
            conn.commit()
            self.logger.info(f"Added package mapping: {package_name} -> {app_name}")
        except Exception as e:
            self.logger.error(f"Error adding package mapping: {e}")
        finally:
            conn.close()
    
    def add_help_document(self, package_name: str, app_name: str, title: str, content: str, 
                         category: str = None, tags: List[str] = None):
        """添加帮助文档"""
        # 创建用于embedding的文本：包含所有相关信息
        embedding_text = f"{app_name} {package_name} {title} {content}"
        if category:
            embedding_text += f" {category}"
        if tags:
            embedding_text += f" {' '.join(tags)}"
            
        embedding = self._get_embedding(embedding_text)
        embedding_blob = embedding.tobytes()
        
        tags_str = json.dumps(tags) if tags else None
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO help_documents 
                (package_name, app_name, category, title, content, tags, embedding)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (package_name, app_name, category, title, content, tags_str, embedding_blob))
            conn.commit()
            self.logger.info(f"Added help document for {package_name}: {title}")
        except Exception as e:
            self.logger.error(f"Error adding help document: {e}")
        finally:
            conn.close()
    
    def search_help_documents(self, package_name: str = None, query: str = "", 
                            category: str = None, k: int = 5) -> List[Dict]:
        """通过包名和query搜索帮助文档"""
        # 构建搜索文本
        search_parts = []
        if package_name:
            search_parts.append(package_name)
        if query:
            search_parts.append(query)
        if category:
            search_parts.append(category)
            
        search_text = " ".join(search_parts)
        search_embedding = self._get_embedding(search_text)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 构建SQL查询
        sql = 'SELECT package_name, app_name, category, title, content, tags, embedding FROM help_documents'
        params = []
        
        where_conditions = []
        if package_name:
            where_conditions.append('package_name = ?')
            params.append(package_name)
        if category:
            where_conditions.append('category = ?')
            params.append(category)
            
        if where_conditions:
            sql += ' WHERE ' + ' AND '.join(where_conditions)
        
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        conn.close()
        
        if not rows:
            return []
        
        # 计算相似度
        candidates = []
        for row in rows:
            pkg_name, app_name, cat, title, content, tags_str, embedding_blob = row
            stored_embedding = np.frombuffer(embedding_blob, dtype=np.float32)
            
            # 计算余弦相似度
            if np.linalg.norm(search_embedding) > 0 and np.linalg.norm(stored_embedding) > 0:
                cosine_similarity = np.dot(search_embedding, stored_embedding) / (
                    np.linalg.norm(search_embedding) * np.linalg.norm(stored_embedding)
                )
            else:
                cosine_similarity = 0.0
            
            tags = json.loads(tags_str) if tags_str else []
            
            candidates.append({
                "package_name": pkg_name,
                "app_name": app_name,
                "category": cat,
                "title": title,
                "content": content,
                "tags": tags,
                "similarity": float(cosine_similarity)
            })
        
        # 按相似度排序
        candidates.sort(key=lambda x: x["similarity"], reverse=True)
        
        # 使用rerank进一步优化（如果有多个结果）
        if len(candidates) > 1:
            candidates = self._rerank_help_results(search_text, candidates)
        
        return candidates[:k]
    
    def _rerank_help_results(self, query: str, candidates: List[Dict]) -> List[Dict]:
        """对帮助文档结果重排序"""
        if len(candidates) <= 1:
            return candidates
            
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # 准备文档列表
        documents = []
        for candidate in candidates:
            doc_text = f"{candidate['title']} {candidate['content']}"
            documents.append(doc_text)
        
        payload = {
            "model": os.getenv("reranker_model"),
            "query": query,
            "documents": documents
        }
        
        try:
            response = requests.post(self.rerank_url, json=payload, headers=headers, timeout=10)
            response.raise_for_status()
            result = response.json()
            
            # 按rerank分数重新排序
            reranked_candidates = []
            for item in result['results']:
                idx = item['index']
                score = item['relevance_score']
                candidate = candidates[idx].copy()
                candidate['rerank_score'] = score
                reranked_candidates.append(candidate)
            
            reranked_candidates.sort(key=lambda x: x['rerank_score'], reverse=True)
            return reranked_candidates
            
        except Exception as e:
            self.logger.error(f"Error in reranking help results: {e}")
            return candidates
    
    def get_app_by_package(self, package_name: str) -> Optional[Dict]:
        """通过包名获取应用信息"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT app_name, app_name_en, description FROM package_mapping WHERE package_name = ?', 
                      (package_name,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                "package_name": package_name,
                "app_name": row[0],
                "app_name_en": row[1],
                "description": row[2]
            }
        return None
    
    def get_all_packages(self) -> List[str]:
        """获取所有包名 - 修复缺失的方法"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT DISTINCT package_name FROM package_mapping')
        packages = [row[0] for row in cursor.fetchall()]
        conn.close()
        return packages
    
    def get_all_apps(self) -> List[str]:
        """获取所有应用名称"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT DISTINCT app_name FROM package_mapping')
        apps = [row[0] for row in cursor.fetchall()]
        conn.close()
        return apps

class MobileAgentHelper:
    def __init__(self, db_path: str = "mobile_agent_help.db"):
        self.vector_db = MobileAgentVectorDB(db_path, api_key="sk-lfujyclxvxhjhrulsokiuyfdnqefbcuojuafrtpdxewtrpyi")
        self.logger = logging.getLogger(__name__)
        
        # 初始化样本数据 - 修复了方法调用
        if not self.vector_db.get_all_packages():
            self.load_sample_data()
    
    def get_help(self, package_name: str, query: str, category: str = None) -> str:
        """获取帮助信息 - 主要接口"""
        results = self.vector_db.search_help_documents(package_name, query, category, k=3)
        
        if not results:
            app_info = self.vector_db.get_app_by_package(package_name)
            app_name = app_info['app_name'] if app_info else package_name
            return f"抱歉，我没有找到关于{app_name}({package_name})中'{query}'的帮助信息。"
        
        best_result = results[0]
        relevance_score = best_result.get("rerank_score", best_result.get("similarity", 0))
        
        # 去掉分数阈值
        if relevance_score < 0:
            app_info = self.vector_db.get_app_by_package(package_name)
            app_name = app_info['app_name'] if app_info else package_name
            return f"抱歉，我不确定如何在{app_name}中{query}。"
        
        # 格式化返回结果
        response = f"**{best_result['title']}**\n\n{best_result['content']}"
        
        # 如果有多个相关结果，提供额外信息
        if len(results) > 1 and results[1].get("similarity", 0) > 0.5:
            response += f"\n\n**相关帮助:**\n- {results[1]['title']}"
        
        return response
    
    def load_sample_data(self):
        """加载样本数据"""
        # 包名映射
        package_mappings = [
            ("com.tencent.mm", "微信", "WeChat", "腾讯公司开发的即时通讯软件"),
            ("com.eg.android.AlipayGphone", "支付宝", "Alipay", "蚂蚁集团开发的移动支付平台"),
            ("com.taobao.taobao", "淘宝", "Taobao", "阿里巴巴集团开发的购物平台"),
            ("com.android.settings", "设置", "Settings", "Android系统设置应用"),
        ]
        
        for pkg_name, app_name, app_name_en, desc in package_mappings:
            self.vector_db.add_package_mapping(pkg_name, app_name, app_name_en, desc)
        
        # 帮助文档
        help_docs = [
            # 微信帮助文档
            ("com.tencent.mm", "微信", "基础操作", "如何发送朋友圈", 
             "发送微信朋友圈需要以下步骤，1.点击导航栏底部的发现按钮，2，点击朋友圈，3.点击右上角拍照分享按钮，4，点击从相册选择，5.选择图片,6.点击完成按钮，7.(检查是否有输入框)输入朋友圈内容，8.点击发送按钮，结束工具调用。", 
             ["消息", "聊天", "发送"]),
            
        ]
        
        for pkg_name, app_name, category, title, content, tags in help_docs:
            self.vector_db.add_help_document(pkg_name, app_name, title, content, category, tags)
        
        self.logger.info("Loaded sample help data for mobile agent")
    
    def get_app_description(self, package_name: str) -> str:
        """获取应用描述"""
        app_info = self.vector_db.get_app_by_package(package_name)
        return app_info.get('description', "") if app_info else ""
    
    def list_app_actions(self, package_name: str) -> List[str]:
        """列出应用支持的操作"""
        results = self.vector_db.search_help_documents(package_name=package_name, k=20)
        return [result['title'] for result in results] if results else []
    
    def get_action_knowledge(self, package_name: str, action_id: str) -> str:
        """获取特定操作的知识"""
        return self.get_help(package_name=package_name, query=action_id)


