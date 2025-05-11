#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import time
import threading
import queue
import concurrent.futures
import pandas as pd
import logging
from datetime import datetime
from flask import current_app, Flask
from database.models import Task, TaskLog, Template

logger = logging.getLogger(__name__)

class TaskService:
    """任务管理服务"""
    
    def __init__(self, excel_service, llm_service, image_service):
        """
        初始化任务服务
        
        Args:
            excel_service: Excel处理服务
            llm_service: LLM API调用服务
            image_service: 图片处理服务
        """
        self.excel_service = excel_service
        self.llm_service = llm_service
        self.image_service = image_service
        self.running_tasks = {}  # 正在运行的任务
        self.task_queues = {}    # 任务队列
        self.task_threads = {}   # 任务线程
        self.task_executors = {} # 任务执行器
        self.task_stop_events = {}  # 任务停止事件
        
        # 延迟加载配置
        self._result_folder = None
        
        # 保存Flask应用实例的引用
        self.app = None
        from app import app
        self.app = app
        
    @property
    def result_folder(self):
        """获取结果存储目录"""
        if self._result_folder is None:
            self._result_folder = current_app.config.get('RESULT_FOLDER', 'results')
        return self._result_folder
        self.image_service = image_service
        self.running_tasks = {}  # 正在运行的任务
        self.task_queues = {}    # 任务队列
        self.task_threads = {}   # 任务线程
        self.task_executors = {} # 任务执行器
        self.task_stop_events = {}  # 任务停止事件
    
    def create_task(self, schema_id, prompt_template, concurrency=1, image_fields=None):
        """
        创建新任务
        
        Args:
            schema_id: Excel schema ID
            prompt_template: 提示词模板
            concurrency: 并发数
            image_fields: 图片字段列表
            
        Returns:
            int: 任务ID
        """
        try:
            # 加载Excel数据
            df, fields = self.excel_service.get_excel_data(schema_id)
            
            # 验证图片字段
            if image_fields:
                for field in image_fields:
                    if field not in fields:
                        raise ValueError(f"图片字段 '{field}' 不存在于Excel文件中")
            
            # 创建任务记录
            task = Task(
                schema_id=schema_id,
                prompt_template=prompt_template,
                total_count=len(df),
                concurrency=concurrency,
                image_fields=image_fields or []
            )
            task_id = task.save()
            logger.info(f"创建任务成功: ID={task_id}, 总条数={len(df)}")
            
            return task_id
            
        except Exception as e:
            logger.error(f"创建任务失败: {str(e)}")
            raise
    
    def start_task(self, task_id):
        """
        启动任务处理
        
        Args:
            task_id: 任务ID
        """
        try:
            # 检查任务是否存在且未在运行
            if task_id in self.running_tasks:
                raise ValueError(f"任务 {task_id} 已经在运行")
            
            # 获取任务信息
            task = Task.get_by_id(task_id)
            if not task:
                raise ValueError(f"找不到ID为{task_id}的任务")
            
            # 标记任务为运行中
            task.status = Task.STATUS_RUNNING
            task.started_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            task.save()
            
            # 创建结果目录
            result_dir = os.path.join(self.result_folder, str(task_id))
            if not os.path.exists(result_dir):
                os.makedirs(result_dir)
            
            # 准备任务停止事件
            stop_event = threading.Event()
            self.task_stop_events[task_id] = stop_event
            
            # 启动任务线程
            thread = threading.Thread(
                target=self._process_task,
                args=(task_id, stop_event),
                daemon=True
            )
            thread.start()
            
            self.task_threads[task_id] = thread
            self.running_tasks[task_id] = task
            
            logger.info(f"任务 {task_id} 已启动，并发数: {task.concurrency}")
            
        except Exception as e:
            logger.error(f"启动任务 {task_id} 失败: {str(e)}")
            # 更新任务状态为错误
            task = Task.get_by_id(task_id)
            if task:
                task.status = Task.STATUS_ERROR
                task.save()
            raise
    
    def _process_task(self, task_id, stop_event):
        """
        处理任务的工作线程
        
        Args:
            task_id: 任务ID
            stop_event: 停止事件
        """
        # 在应用上下文中运行任务处理代码
        with self.app.app_context():
            try:
                # 获取任务信息
                task = Task.get_by_id(task_id)
                
                # 加载Excel数据
                df, fields = self.excel_service.get_excel_data(task.schema_id)
                
                # 初始化结果列
                task.result_column = [None] * len(df)
                
                # 创建任务队列
                task_queue = queue.Queue()
                self.task_queues[task_id] = task_queue
                
                # 添加所有行到队列
                for i in range(len(df)):
                    task_queue.put(i)
                
                # 创建线程池
                executor = concurrent.futures.ThreadPoolExecutor(max_workers=task.concurrency)
                self.task_executors[task_id] = executor
                
                # 创建进度跟踪变量
                processed = 0
                success = 0
                error = 0
                
                # 处理开始时间
                start_time = time.time()
                
                # 提交所有处理任务
                futures = []
                while not task_queue.empty() and not stop_event.is_set():
                    row_index = task_queue.get()
                    future = executor.submit(
                        self._process_row,
                        task_id,
                        df.iloc[row_index].to_dict(),
                        task.prompt_template,
                        task.image_fields,
                        row_index
                    )
                    futures.append((future, row_index))
                    
                    # 防止提交过多任务
                    if len(futures) >= task.concurrency * 2:
                        # 等待一些任务完成
                        for future, index in list(futures):
                            if future.done():
                                try:
                                    result, is_success = future.result()
                                    task.result_column[index] = result
                                    processed += 1
                                    if is_success:
                                        success += 1
                                    else:
                                        error += 1
                                    
                                    # 更新任务状态
                                    task.processed_count = processed
                                    task.success_count = success
                                    task.error_count = error
                                    task.save()
                                    
                                    futures.remove((future, index))
                                except Exception as e:
                                    logger.error(f"处理行 {index} 结果时出错: {str(e)}")
                                    
                        # 检查是否需要停止
                        if stop_event.is_set():
                            break
                
                # 等待所有任务完成
                for future, index in futures:
                    if not stop_event.is_set():
                        try:
                            result, is_success = future.result()
                            task.result_column[index] = result
                            processed += 1
                            if is_success:
                                success += 1
                            else:
                                error += 1
                        except Exception as e:
                            logger.error(f"处理行 {index} 结果时出错: {str(e)}")
                            error += 1
                            
                        # 更新任务状态
                        task.processed_count = processed
                        task.success_count = success
                        task.error_count = error
                        task.save()
                
                # 关闭线程池
                executor.shutdown(wait=False)
                
                # 检查是否被终止
                if stop_event.is_set():
                    task.status = Task.STATUS_STOPPED
                    task.save()
                    logger.info(f"任务 {task_id} 已停止")
                else:
                    # 生成结果文件
                    result_file = os.path.join(
                        self.result_folder,
                        str(task_id),
                        f"result_{datetime.now().strftime('%Y%m%d%H%M%S')}.xlsx"
                    )
                    self.excel_service.save_result(df, task.result_column, result_file)
                    
                    # 更新任务状态
                    task.status = Task.STATUS_COMPLETED
                    task.completed_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    task.result_path = result_file
                    task.save()
                    
                    logger.info(f"任务 {task_id} 已完成，结果保存到: {result_file}")
                
                # 清理资源
                if task_id in self.task_executors:
                    del self.task_executors[task_id]
                if task_id in self.task_queues:
                    del self.task_queues[task_id]
                if task_id in self.running_tasks:
                    del self.running_tasks[task_id]
                if task_id in self.task_threads:
                    del self.task_threads[task_id]
                if task_id in self.task_stop_events:
                    del self.task_stop_events[task_id]
                    
            except Exception as e:
                logger.error(f"任务 {task_id} 处理过程中出错: {str(e)}")
                
                # 更新任务状态为错误
                try:
                    task = Task.get_by_id(task_id)
                    if task:
                        task.status = Task.STATUS_ERROR
                        task.save()
                except:
                    # 如果无法更新任务状态，只记录日志
                    logger.error("无法更新任务状态")
            
            # 清理资源
            if task_id in self.task_executors:
                self.task_executors[task_id].shutdown(wait=False)
                del self.task_executors[task_id]
            if task_id in self.task_queues:
                del self.task_queues[task_id]
            if task_id in self.running_tasks:
                del self.running_tasks[task_id]
            if task_id in self.task_threads:
                del self.task_threads[task_id]
            if task_id in self.task_stop_events:
                del self.task_stop_events[task_id]
    
    def _process_row(self, task_id, row_data, prompt_template, image_fields, row_index):
        """
        处理单行数据
        
        Args:
            task_id: 任务ID
            row_data: 行数据
            prompt_template: 提示词模板
            image_fields: 图片字段列表
            row_index: 行索引
            
        Returns:
            tuple: (处理结果, 是否成功)
        """
        # 在应用上下文中执行数据库操作
        with self.app.app_context():
            try:
                log = TaskLog(task_id=task_id, row_index=row_index)
                
                # 检查行数据是否有效
                if row_data is None or not isinstance(row_data, dict) or len(row_data) == 0:
                    error_msg = f"行 {row_index} 数据无效或为空"
                    logger.warning(error_msg)
                    log.status = TaskLog.STATUS_ERROR
                    log.error_message = error_msg
                    log.save()
                    return error_msg, False
                
                # 处理空值行
                has_valid_data = False
                for field, value in row_data.items():
                    if value is not None and not (isinstance(value, str) and value.strip() == ""):
                        has_valid_data = True
                        break
                
                if not has_valid_data:
                    logger.warning(f"行 {row_index} 所有字段均为空值")
                
                # 处理提示词模板
                prompt = self.excel_service.process_template(prompt_template, row_data)
                
                # 处理图片数据
                image_data = None
                if image_fields:
                    try:
                        image_data = self.image_service.extract_image_data_from_row(row_data, image_fields)
                    except Exception as e:
                        logger.warning(f"处理图片数据时出错: {str(e)}")
                
                # 调用LLM API
                response_text, token_count, processing_time = self.llm_service.call_api(prompt, image_data)
                
                # 记录日志
                log.status = TaskLog.STATUS_SUCCESS
                log.processing_time = processing_time
                log.token_count = token_count
                log.response_text = response_text  # 保存处理结果到日志中
                log.save()
                
                return response_text, True
                
            except Exception as e:
                logger.error(f"处理行 {row_index} 时出错: {str(e)}")
                
                try:
                    # 记录错误日志
                    log = TaskLog(
                        task_id=task_id,
                        row_index=row_index,
                        status=TaskLog.STATUS_ERROR,
                        error_message=str(e)
                    )
                    log.save()
                except Exception as inner_e:
                    logger.error(f"记录错误日志失败: {str(inner_e)}")
                
                return f"处理错误: {str(e)}", False
    
    def stop_task(self, task_id):
        """
        停止正在运行的任务
        
        Args:
            task_id: 任务ID
        """
        try:
            if task_id not in self.running_tasks:
                raise ValueError(f"任务 {task_id} 未在运行")
            
            # 设置停止事件
            if task_id in self.task_stop_events:
                self.task_stop_events[task_id].set()
            
            # 关闭线程池
            if task_id in self.task_executors:
                self.task_executors[task_id].shutdown(wait=False)
            
            # 等待一段时间，让任务有机会清理
            time.sleep(1)
            
            # 强制更新任务状态
            task = Task.get_by_id(task_id)
            if task and task.status == Task.STATUS_RUNNING:
                task.status = Task.STATUS_STOPPED
                task.save()
            
            logger.info(f"任务 {task_id} 已停止")
            
            # 清理资源
            if task_id in self.task_executors:
                del self.task_executors[task_id]
            if task_id in self.task_queues:
                del self.task_queues[task_id]
            if task_id in self.running_tasks:
                del self.running_tasks[task_id]
            if task_id in self.task_threads:
                del self.task_threads[task_id]
            if task_id in self.task_stop_events:
                del self.task_stop_events[task_id]
            
        except Exception as e:
            logger.error(f"停止任务 {task_id} 时出错: {str(e)}")
            raise
    
    def delete_task(self, task_id):
        """
        删除任务
        
        Args:
            task_id: 任务ID
        """
        try:
            # 检查任务是否在运行
            if task_id in self.running_tasks:
                # 先停止任务
                self.stop_task(task_id)
            
            # 获取任务信息
            task = Task.get_by_id(task_id)
            if not task:
                raise ValueError(f"找不到ID为{task_id}的任务")
            
            # 删除结果文件
            if task.result_path and os.path.exists(task.result_path):
                try:
                    os.remove(task.result_path)
                except Exception as e:
                    logger.warning(f"删除结果文件时出错: {str(e)}")
            
            # 删除任务目录
            result_dir = os.path.join(current_app.config['RESULT_FOLDER'], str(task_id))
            if os.path.exists(result_dir):
                try:
                    for file in os.listdir(result_dir):
                        os.remove(os.path.join(result_dir, file))
                    os.rmdir(result_dir)
                except Exception as e:
                    logger.warning(f"删除任务目录时出错: {str(e)}")
            
            # 删除任务记录
            task.delete()
            logger.info(f"任务 {task_id} 已删除")
            
        except Exception as e:
            logger.error(f"删除任务 {task_id} 时出错: {str(e)}")
            raise
    
    def get_task_status(self, task_id):
        """
        获取任务状态
        
        Args:
            task_id: 任务ID
            
        Returns:
            dict: 任务状态信息
        """
        try:
            task = Task.get_by_id(task_id)
            if not task:
                raise ValueError(f"找不到ID为{task_id}的任务")
            
            task_dict = task.to_dict()
            
            # 计算预计剩余时间
            if task.status == Task.STATUS_RUNNING and task.processed_count > 0:
                if task.started_at:
                    start_time = datetime.strptime(task.started_at, '%Y-%m-%d %H:%M:%S')
                    now = datetime.now()
                    elapsed_seconds = (now - start_time).total_seconds()
                    if elapsed_seconds > 0:
                        # 计算处理速率
                        rate = task.processed_count / elapsed_seconds
                        if rate > 0:
                            # 预计剩余时间（秒）
                            remaining_items = task.total_count - task.processed_count
                            remaining_seconds = remaining_items / rate
                            
                            # 转换为可读格式
                            remaining_minutes = int(remaining_seconds / 60)
                            
                            task_dict['elapsed_time'] = int(elapsed_seconds)
                            task_dict['remaining_time'] = int(remaining_seconds)
                            task_dict['elapsed_time_text'] = self._format_time(elapsed_seconds)
                            task_dict['remaining_time_text'] = self._format_time(remaining_seconds)
            
            return task_dict
            
        except Exception as e:
            logger.error(f"获取任务 {task_id} 状态时出错: {str(e)}")
            raise
    
    def get_task_result_path(self, task_id):
        """
        获取任务结果文件路径
        
        Args:
            task_id: 任务ID
            
        Returns:
            str: 结果文件路径
        """
        try:
            task = Task.get_by_id(task_id)
            if not task:
                raise ValueError(f"找不到ID为{task_id}的任务")
            
            if not task.result_path or not os.path.exists(task.result_path):
                raise ValueError(f"任务 {task_id} 没有有效的结果文件")
            
            return task.result_path
            
        except Exception as e:
            logger.error(f"获取任务 {task_id} 结果路径时出错: {str(e)}")
            raise
    
    def get_history_tasks(self, page=1, per_page=10):
        """
        获取历史任务列表
        
        Args:
            page: 页码
            per_page: 每页条数
            
        Returns:
            tuple: (任务列表, 总数)
        """
        try:
            tasks, total = Task.get_all(page, per_page)
            return [task.to_dict() for task in tasks], total
            
        except Exception as e:
            logger.error(f"获取历史任务列表时出错: {str(e)}")
            raise
    
    def save_template(self, name, content):
        """
        保存提示词模板
        
        Args:
            name: 模板名称
            content: 模板内容
            
        Returns:
            int: 模板ID
        """
        try:
            template = Template(name=name, content=content)
            template_id = template.save()
            logger.info(f"模板 '{name}' 已保存，ID: {template_id}")
            return template_id
            
        except Exception as e:
            logger.error(f"保存模板时出错: {str(e)}")
            raise
    
    def get_templates(self):
        """
        获取所有模板
        
        Returns:
            list: 模板列表
        """
        try:
            templates = Template.get_all()
            return [template.to_dict() for template in templates]
            
        except Exception as e:
            logger.error(f"获取模板列表时出错: {str(e)}")
            raise
            
    def delete_template(self, template_id):
        """
        删除提示词模板
        
        Args:
            template_id: 模板ID
            
        Returns:
            bool: 是否删除成功
        """
        try:
            template = Template.get_by_id(template_id)
            if not template:
                raise ValueError(f"找不到ID为{template_id}的模板")
            
            result = template.delete()
            logger.info(f"模板 ID:{template_id} 已删除")
            return result
            
        except Exception as e:
            logger.error(f"删除模板时出错: {str(e)}")
            raise
            
    def get_task_logs(self, task_id, limit=10):
        """
        获取任务的最新处理日志
        
        Args:
            task_id: 任务ID
            limit: 返回的日志数量限制
            
        Returns:
            tuple: (日志列表, 总数)
        """
        try:
            # 获取任务处理日志
            logs, total = TaskLog.get_task_logs_recent(task_id, limit)
            
            # 将日志对象转换为字典
            log_dicts = []
            for log in logs:
                log_dict = log.to_dict()
                
                # 如果日志中没有响应文本，但处理成功了，尝试从result_column获取
                if log.status == TaskLog.STATUS_SUCCESS:
                    if log.response_text:
                        # 如果日志中有响应文本，直接使用
                        log_dict['response_text'] = log.response_text
                    else:
                        # 否则尝试从任务结果列表获取
                        task = Task.get_by_id(task_id)
                        if task and hasattr(task, 'result_column') and task.result_column and len(task.result_column) > log.row_index:
                            log_dict['response_text'] = task.result_column[log.row_index] or ''
                        else:
                            log_dict['response_text'] = '处理中...'
                elif log.status == TaskLog.STATUS_ERROR:
                    log_dict['response_text'] = log.error_message or '处理失败'
                
                log_dicts.append(log_dict)
            
            return log_dicts, total
            
        except Exception as e:
            logger.error(f"获取任务日志时出错: {str(e)}")
            raise
    
    @staticmethod
    def _format_time(seconds):
        """
        格式化时间
        
        Args:
            seconds: 秒数
            
        Returns:
            str: 格式化的时间字符串
        """
        minutes, seconds = divmod(int(seconds), 60)
        hours, minutes = divmod(minutes, 60)
        
        if hours > 0:
            return f"{hours}小时 {minutes}分钟"
        elif minutes > 0:
            return f"{minutes}分钟 {seconds}秒"
        else:
            return f"{seconds}秒"