#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sqlite3
from flask import current_app, g
import logging

logger = logging.getLogger(__name__)

def get_db_connection():
    """获取数据库连接"""
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(current_app.config['DATABASE'])
        db.row_factory = sqlite3.Row
    return db

def close_db_connection(e=None):
    """关闭数据库连接"""
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    """初始化数据库"""
    try:
        connection = sqlite3.connect(current_app.config['DATABASE'])
        cursor = connection.cursor()
        
        # 创建任务表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            schema_id INTEGER,
            status TEXT,
            total_count INTEGER,
            processed_count INTEGER,
            success_count INTEGER,
            error_count INTEGER,
            concurrency INTEGER,
            prompt_template TEXT,
            image_fields TEXT,
            result_path TEXT,
            created_at TEXT,
            started_at TEXT,
            completed_at TEXT
        )
        ''')
        
        # 创建模板表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            content TEXT,
            created_at TEXT
        )
        ''')
        
        # 创建API配置表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS api_configs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            type TEXT,
            url TEXT,
            api_key TEXT,
            model_name TEXT,
            other_params TEXT,
            created_at TEXT,
            is_default INTEGER DEFAULT 0,
            use_stream INTEGER DEFAULT 0
        )
        ''')
        
        # 创建Excel表结构表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS excel_schemas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_name TEXT,
            fields TEXT,
            file_path TEXT,
            created_at TEXT
        )
        ''')
        
        # 创建任务日志表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS task_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER,
            row_index INTEGER,
            status TEXT,
            error_message TEXT,
            processing_time REAL,
            token_count INTEGER,
            response_text TEXT,
            created_at TEXT,
            FOREIGN KEY (task_id) REFERENCES tasks (id)
        )
        ''')
        
        # 插入默认API配置
        cursor.execute('''
        INSERT OR IGNORE INTO api_configs (id, name, type, url, api_key, model_name, other_params, created_at, is_default)
        VALUES (1, '默认OpenAI配置', 'openai', 'https://api.openai.com/v1', '', 'gpt-3.5-turbo', '{"temperature": 0.7, "max_tokens": 2000}', CURRENT_TIMESTAMP, 1)
        ''')
        
        # 插入默认提示词模板
        cursor.execute('''
        INSERT OR IGNORE INTO templates (id, name, content, created_at)
        VALUES (1, '基础摘要模板', '请根据以下信息生成摘要：\n\n标题：{{标题}}\n内容：{{内容}}\n\n请提供一个简洁的摘要，不超过100字。', CURRENT_TIMESTAMP)
        ''')
        
        connection.commit()
        logger.info("数据库初始化成功")
    except Exception as e:
        logger.error(f"数据库初始化错误: {str(e)}")
    finally:
        connection.close()

def query_db(query, args=(), one=False):
    """查询数据库"""
    cursor = get_db_connection().execute(query, args)
    rv = cursor.fetchall()
    cursor.close()
    return (rv[0] if rv else None) if one else rv

def insert_db(query, args=()):
    """插入数据"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(query, args)
    last_id = cursor.lastrowid
    conn.commit()
    cursor.close()
    return last_id

def update_db(query, args=()):
    """更新数据"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(query, args)
    conn.commit()
    affected_rows = cursor.rowcount
    cursor.close()
    return affected_rows

def delete_db(query, args=()):
    """删除数据"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(query, args)
    conn.commit()
    affected_rows = cursor.rowcount
    cursor.close()
    return affected_rows