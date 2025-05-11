#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
from datetime import datetime
from database.db import query_db, insert_db, update_db, delete_db

class Task:
    """任务模型"""
    
    STATUS_PENDING = 'pending'
    STATUS_RUNNING = 'running'
    STATUS_COMPLETED = 'completed'
    STATUS_STOPPED = 'stopped'
    STATUS_ERROR = 'error'
    
    def __init__(self, id=None, name=None, schema_id=None, status=STATUS_PENDING,
                 total_count=0, processed_count=0, success_count=0, error_count=0,
                 concurrency=1, prompt_template='', image_fields=None, result_path=None,
                 created_at=None, started_at=None, completed_at=None):
        self.id = id
        self.name = name or f"任务-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        self.schema_id = schema_id
        self.status = status
        self.total_count = total_count
        self.processed_count = processed_count
        self.success_count = success_count
        self.error_count = error_count
        self.concurrency = concurrency
        self.prompt_template = prompt_template
        self.image_fields = image_fields or []
        self.result_path = result_path
        self.created_at = created_at or datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.started_at = started_at
        self.completed_at = completed_at
        # 保存处理结果的列表
        self.result_column = []
    
    @classmethod
    def from_row(cls, row):
        """从数据库行创建任务对象"""
        if not row:
            return None
        
        task = cls(
            id=row['id'],
            name=row['name'],
            schema_id=row['schema_id'],
            status=row['status'],
            total_count=row['total_count'],
            processed_count=row['processed_count'],
            success_count=row['success_count'],
            error_count=row['error_count'],
            concurrency=row['concurrency'],
            prompt_template=row['prompt_template'],
            image_fields=json.loads(row['image_fields']) if row['image_fields'] else [],
            result_path=row['result_path'],
            created_at=row['created_at'],
            started_at=row['started_at'],
            completed_at=row['completed_at']
        )
        return task
    
    def save(self):
        """保存任务到数据库"""
        if self.id:
            # 更新现有任务
            update_db(
                """UPDATE tasks SET name=?, schema_id=?, status=?, total_count=?, 
                processed_count=?, success_count=?, error_count=?, concurrency=?, 
                prompt_template=?, image_fields=?, result_path=?, started_at=?, completed_at=?
                WHERE id=?""",
                (
                    self.name, self.schema_id, self.status, self.total_count,
                    self.processed_count, self.success_count, self.error_count, 
                    self.concurrency, self.prompt_template, json.dumps(self.image_fields),
                    self.result_path, self.started_at, self.completed_at, self.id
                )
            )
            return self.id
        else:
            # 创建新任务
            self.id = insert_db(
                """INSERT INTO tasks (name, schema_id, status, total_count, processed_count,
                success_count, error_count, concurrency, prompt_template, image_fields,
                result_path, created_at, started_at, completed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    self.name, self.schema_id, self.status, self.total_count,
                    self.processed_count, self.success_count, self.error_count,
                    self.concurrency, self.prompt_template, json.dumps(self.image_fields),
                    self.result_path, self.created_at, self.started_at, self.completed_at
                )
            )
            return self.id
    
    @classmethod
    def get_by_id(cls, task_id):
        """根据ID获取任务"""
        row = query_db("SELECT * FROM tasks WHERE id = ?", (task_id,), one=True)
        return cls.from_row(row)
    
    @classmethod
    def get_all(cls, page=1, per_page=10):
        """获取所有任务，支持分页"""
        offset = (page - 1) * per_page
        rows = query_db(
            "SELECT * FROM tasks ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (per_page, offset)
        )
        total = query_db("SELECT COUNT(*) as count FROM tasks", one=True)['count']
        
        tasks = [cls.from_row(row) for row in rows]
        return tasks, total
    
    def delete(self):
        """删除任务"""
        if self.id:
            delete_db("DELETE FROM tasks WHERE id = ?", (self.id,))
            delete_db("DELETE FROM task_logs WHERE task_id = ?", (self.id,))
            return True
        return False
    
    def to_dict(self):
        """将任务转换为字典"""
        return {
            'id': self.id,
            'name': self.name,
            'schema_id': self.schema_id,
            'status': self.status,
            'total_count': self.total_count,
            'processed_count': self.processed_count,
            'success_count': self.success_count,
            'error_count': self.error_count,
            'concurrency': self.concurrency,
            'prompt_template': self.prompt_template,
            'image_fields': self.image_fields,
            'result_path': self.result_path,
            'created_at': self.created_at,
            'started_at': self.started_at,
            'completed_at': self.completed_at,
            'progress': int(self.processed_count / self.total_count * 100) if self.total_count > 0 else 0
        }


class Template:
    """提示词模板模型"""
    
    def __init__(self, id=None, name=None, content=None, created_at=None):
        self.id = id
        self.name = name
        self.content = content
        self.created_at = created_at or datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    @classmethod
    def from_row(cls, row):
        """从数据库行创建模板对象"""
        if not row:
            return None
        
        template = cls(
            id=row['id'],
            name=row['name'],
            content=row['content'],
            created_at=row['created_at']
        )
        return template
    
    def save(self):
        """保存模板到数据库"""
        if self.id:
            # 更新现有模板
            update_db(
                "UPDATE templates SET name=?, content=? WHERE id=?",
                (self.name, self.content, self.id)
            )
            return self.id
        else:
            # 创建新模板
            self.id = insert_db(
                "INSERT INTO templates (name, content, created_at) VALUES (?, ?, ?)",
                (self.name, self.content, self.created_at)
            )
            return self.id
    
    @classmethod
    def get_by_id(cls, template_id):
        """根据ID获取模板"""
        row = query_db("SELECT * FROM templates WHERE id = ?", (template_id,), one=True)
        return cls.from_row(row)
    
    @classmethod
    def get_all(cls):
        """获取所有模板"""
        rows = query_db("SELECT * FROM templates ORDER BY created_at DESC")
        templates = [cls.from_row(row) for row in rows]
        return templates
    
    def delete(self):
        """删除模板"""
        if self.id:
            delete_db("DELETE FROM templates WHERE id = ?", (self.id,))
            return True
        return False
    
    def to_dict(self):
        """将模板转换为字典"""
        return {
            'id': self.id,
            'name': self.name,
            'content': self.content,
            'created_at': self.created_at
        }


class APIConfig:
    """API配置模型"""
    
    def __init__(self, id=None, name=None, type='openai', url=None, api_key=None,
                 model_name=None, other_params=None, created_at=None, is_default=0, use_stream=0):
        self.id = id
        self.name = name
        self.type = type
        self.url = url
        self.api_key = api_key
        self.model_name = model_name
        self.other_params = other_params or {}
        self.created_at = created_at or datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.is_default = is_default
        self.use_stream = use_stream
    
    @classmethod
    def from_row(cls, row):
        """从数据库行创建API配置对象"""
        if not row:
            return None
        
        # 安全获取use_stream字段值，处理可能不存在的情况
        try:
            use_stream = row['use_stream']
        except (IndexError, KeyError):
            use_stream = 0
            
        config = cls(
            id=row['id'],
            name=row['name'],
            type=row['type'],
            url=row['url'],
            api_key=row['api_key'],
            model_name=row['model_name'],
            other_params=json.loads(row['other_params']) if row['other_params'] else {},
            created_at=row['created_at'],
            is_default=row['is_default'],
            use_stream=use_stream
        )
        return config
    
    def save(self):
        """保存API配置到数据库"""
        # 如果设置为默认，先重置其他配置
        if self.is_default:
            update_db("UPDATE api_configs SET is_default = 0")
        
        if self.id:
            # 更新现有配置
            update_db(
                """UPDATE api_configs SET name=?, type=?, url=?, api_key=?,
                model_name=?, other_params=?, is_default=?, use_stream=? WHERE id=?""",
                (
                    self.name, self.type, self.url, self.api_key,
                    self.model_name, json.dumps(self.other_params), self.is_default,
                    self.use_stream, self.id
                )
            )
            return self.id
        else:
            # 创建新配置
            self.id = insert_db(
                """INSERT INTO api_configs (name, type, url, api_key, model_name,
                other_params, created_at, is_default, use_stream) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    self.name, self.type, self.url, self.api_key, self.model_name,
                    json.dumps(self.other_params), self.created_at, self.is_default, self.use_stream
                )
            )
            return self.id
    
    @classmethod
    def get_by_id(cls, config_id):
        """根据ID获取API配置"""
        row = query_db("SELECT * FROM api_configs WHERE id = ?", (config_id,), one=True)
        return cls.from_row(row)
    
    @classmethod
    def get_default(cls):
        """获取默认API配置"""
        row = query_db("SELECT * FROM api_configs WHERE is_default = 1", one=True)
        return cls.from_row(row)
    
    @classmethod
    def get_all(cls):
        """获取所有API配置"""
        rows = query_db("SELECT * FROM api_configs ORDER BY created_at DESC")
        configs = [cls.from_row(row) for row in rows]
        return configs
    
    def delete(self):
        """删除API配置"""
        if self.id:
            delete_db("DELETE FROM api_configs WHERE id = ?", (self.id,))
            return True
        return False
    
    def to_dict(self):
        """将API配置转换为字典"""
        return {
            'id': self.id,
            'name': self.name,
            'type': self.type,
            'url': self.url,
            'api_key': self.api_key,
            'model_name': self.model_name,
            'other_params': self.other_params,
            'created_at': self.created_at,
            'is_default': self.is_default,
            'use_stream': self.use_stream
        }


class ExcelSchema:
    """Excel表结构模型"""
    
    def __init__(self, id=None, file_name=None, fields=None, file_path=None, created_at=None):
        self.id = id
        self.file_name = file_name
        self.fields = fields or []
        self.file_path = file_path
        self.created_at = created_at or datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    @classmethod
    def from_row(cls, row):
        """从数据库行创建Excel表结构对象"""
        if not row:
            return None
        
        schema = cls(
            id=row['id'],
            file_name=row['file_name'],
            fields=json.loads(row['fields']) if row['fields'] else [],
            file_path=row['file_path'],
            created_at=row['created_at']
        )
        return schema
    
    def save(self):
        """保存Excel表结构到数据库"""
        if self.id:
            # 更新现有表结构
            update_db(
                "UPDATE excel_schemas SET file_name=?, fields=?, file_path=? WHERE id=?",
                (self.file_name, json.dumps(self.fields), self.file_path, self.id)
            )
            return self.id
        else:
            # 创建新表结构
            self.id = insert_db(
                "INSERT INTO excel_schemas (file_name, fields, file_path, created_at) VALUES (?, ?, ?, ?)",
                (self.file_name, json.dumps(self.fields), self.file_path, self.created_at)
            )
            return self.id
    
    @classmethod
    def get_by_id(cls, schema_id):
        """根据ID获取Excel表结构"""
        row = query_db("SELECT * FROM excel_schemas WHERE id = ?", (schema_id,), one=True)
        return cls.from_row(row)
    
    def delete(self):
        """删除Excel表结构"""
        if self.id:
            delete_db("DELETE FROM excel_schemas WHERE id = ?", (self.id,))
            return True
        return False
    
    def to_dict(self):
        """将Excel表结构转换为字典"""
        return {
            'id': self.id,
            'file_name': self.file_name,
            'fields': self.fields,
            'file_path': self.file_path,
            'created_at': self.created_at
        }


class TaskLog:
    """任务日志模型"""
    
    STATUS_SUCCESS = 'success'
    STATUS_ERROR = 'error'
    
    def __init__(self, id=None, task_id=None, row_index=None, status=STATUS_SUCCESS,
                 error_message=None, processing_time=0, token_count=0, response_text=None, created_at=None):
        self.id = id
        self.task_id = task_id
        self.row_index = row_index
        self.status = status
        self.error_message = error_message
        self.processing_time = processing_time
        self.token_count = token_count
        self.response_text = response_text
        self.created_at = created_at or datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    @classmethod
    def from_row(cls, row):
        """从数据库行创建任务日志对象"""
        if not row:
            return None
        
        # SQLite Row对象没有get方法，我们需要检查字段是否存在
        response_text = None
        try:
            # 尝试获取response_text字段
            response_text = row['response_text']
        except (IndexError, KeyError):
            # 如果字段不存在则忽略错误
            pass
        
        log = cls(
            id=row['id'],
            task_id=row['task_id'],
            row_index=row['row_index'],
            status=row['status'],
            error_message=row['error_message'],
            processing_time=row['processing_time'],
            token_count=row['token_count'],
            response_text=response_text,
            created_at=row['created_at']
        )
        return log
    
    def save(self):
        """保存任务日志到数据库"""
        if self.id:
            # 更新现有日志
            update_db(
                """UPDATE task_logs SET task_id=?, row_index=?, status=?,
                error_message=?, processing_time=?, token_count=?, response_text=? WHERE id=?""",
                (
                    self.task_id, self.row_index, self.status,
                    self.error_message, self.processing_time, self.token_count,
                    self.response_text, self.id
                )
            )
            return self.id
        else:
            # 创建新日志
            self.id = insert_db(
                """INSERT INTO task_logs (task_id, row_index, status, error_message,
                processing_time, token_count, response_text, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    self.task_id, self.row_index, self.status, self.error_message,
                    self.processing_time, self.token_count, self.response_text, self.created_at
                )
            )
            return self.id
    
    @classmethod
    def get_task_logs(cls, task_id, page=1, per_page=100):
        """获取特定任务的日志，支持分页"""
        offset = (page - 1) * per_page
        rows = query_db(
            "SELECT * FROM task_logs WHERE task_id = ? ORDER BY row_index LIMIT ? OFFSET ?",
            (task_id, per_page, offset)
        )
        total = query_db(
            "SELECT COUNT(*) as count FROM task_logs WHERE task_id = ?",
            (task_id,), one=True
        )['count']
        
        logs = [cls.from_row(row) for row in rows]
        return logs, total
    
    @classmethod
    def get_task_logs_recent(cls, task_id, limit=10):
        """获取特定任务的最新日志"""
        rows = query_db(
            "SELECT * FROM task_logs WHERE task_id = ? ORDER BY id DESC LIMIT ?",
            (task_id, limit)
        )
        total = query_db(
            "SELECT COUNT(*) as count FROM task_logs WHERE task_id = ?",
            (task_id,), one=True
        )['count']
        
        logs = [cls.from_row(row) for row in rows]
        return logs, total
    
    def to_dict(self):
        """将任务日志转换为字典"""
        return {
            'id': self.id,
            'task_id': self.task_id,
            'row_index': self.row_index,
            'status': self.status,
            'error_message': self.error_message,
            'processing_time': self.processing_time,
            'token_count': self.token_count,
            'response_text': self.response_text,
            'created_at': self.created_at
        }