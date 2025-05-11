#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import logging
import pandas as pd
from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for
from werkzeug.utils import secure_filename
import sqlite3
import json
from datetime import datetime

# 导入服务模块
from services.excel_service import ExcelService
from services.llm_service import LLMService
from services.image_service import ImageService
from services.task_service import TaskService
from database.db import init_db, get_db_connection

# 创建Flask应用
app = Flask(__name__)
app.config.from_pyfile('config.py')

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)



# 初始化数据库和服务
with app.app_context():
    # 初始化数据库
    init_db()
    
    # 确保task_logs表有response_text列
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # 检查列是否存在
        cursor.execute("PRAGMA table_info(task_logs)")
        columns = [column[1] for column in cursor.fetchall()]
        
        # 如果response_text列不存在，添加它
        if 'response_text' not in columns:
            logger.info("添加response_text列到task_logs表")
            cursor.execute("ALTER TABLE task_logs ADD COLUMN response_text TEXT")
            conn.commit()
    except Exception as e:
        logger.error(f"更新task_logs表结构时出错: {str(e)}")
    finally:
        conn.close()
    
    # 初始化服务作为app的属性
    app.excel_service = ExcelService()
    app.llm_service = LLMService()
    app.image_service = ImageService()
    app.task_service = TaskService(app.excel_service, app.llm_service, app.image_service)

# 路由：主页
@app.route('/')
def index():
    return render_template('index.html')

# 路由：上传Excel文件
@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': '没有文件'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': '没有选择文件'}), 400
    
    if file and '.' in file.filename and \
            file.filename.rsplit('.', 1)[1].lower() in ['xlsx', 'xls', 'csv']:
        filename = secure_filename(file.filename)
        temp_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(temp_path)
        
        try:
            # 解析Excel文件
            fields, preview_data = app.excel_service.parse_excel(temp_path)
            
            # 保存文件信息到数据库
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO excel_schemas (file_name, fields, file_path, created_at) VALUES (?, ?, ?, ?)",
                (filename, json.dumps(fields), temp_path, datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            )
            schema_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            return jsonify({
                'success': True,
                'schema_id': schema_id,
                'fields': fields,
                'preview': preview_data
            })
        except Exception as e:
            logger.error(f"Excel解析错误: {str(e)}")
            return jsonify({'error': f'Excel解析错误: {str(e)}'}), 500
    
    return jsonify({'error': '不支持的文件格式'}), 400

# 路由：开始处理任务
@app.route('/process', methods=['POST'])
def process_task():
    data = request.json
    
    # 验证请求数据
    required_fields = ['schema_id', 'prompt_template', 'concurrency']
    if not all(field in data for field in required_fields):
        return jsonify({'error': '缺少必要参数'}), 400
    
    try:
        # 创建任务
        task_id = app.task_service.create_task(
            schema_id=data['schema_id'],
            prompt_template=data['prompt_template'],
            concurrency=int(data['concurrency']),
            image_fields=data.get('image_fields', [])
        )
        
        # 启动处理任务
        app.task_service.start_task(task_id)
        
        return jsonify({
            'success': True,
            'task_id': task_id
        })
    except Exception as e:
        logger.error(f"创建任务错误: {str(e)}")
        return jsonify({'error': f'创建任务错误: {str(e)}'}), 500

# 路由：获取任务状态
@app.route('/task_status/<int:task_id>', methods=['GET'])
def task_status(task_id):
    try:
        status = app.task_service.get_task_status(task_id)
        return jsonify(status)
    except Exception as e:
        logger.error(f"获取任务状态错误: {str(e)}")
        return jsonify({'error': f'获取任务状态错误: {str(e)}'}), 500

# 路由：停止任务
@app.route('/stop_task/<int:task_id>', methods=['POST'])
def stop_task(task_id):
    try:
        app.task_service.stop_task(task_id)
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"停止任务错误: {str(e)}")
        return jsonify({'error': f'停止任务错误: {str(e)}'}), 500

# 路由：删除任务
@app.route('/delete_task/<int:task_id>', methods=['POST'])
def delete_task(task_id):
    try:
        app.task_service.delete_task(task_id)
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"删除任务错误: {str(e)}")
        return jsonify({'error': f'删除任务错误: {str(e)}'}), 500

# 路由：下载处理结果
@app.route('/download_result/<int:task_id>', methods=['GET'])
def download_result(task_id):
    try:
        result_path = app.task_service.get_task_result_path(task_id)
        if not result_path or not os.path.exists(result_path):
            return jsonify({'error': '结果文件不存在'}), 404
        
        return send_file(result_path, as_attachment=True)
    except Exception as e:
        logger.error(f"下载结果错误: {str(e)}")
        return jsonify({'error': f'下载结果错误: {str(e)}'}), 500

# 路由：获取结果预览数据
@app.route('/result_preview/<int:task_id>', methods=['GET'])
def result_preview(task_id):
    try:
        # 获取任务状态和结果路径
        task = app.task_service.get_task_status(task_id)
        if task['status'] != 'completed':
            return jsonify({'error': '任务尚未完成'}), 400
            
        result_path = app.task_service.get_task_result_path(task_id)
        if not result_path or not os.path.exists(result_path):
            return jsonify({'error': '结果文件不存在'}), 404
        
        # 读取结果文件（前10条记录）
        preview_data = []
        
        # 根据文件类型读取数据
        file_ext = os.path.splitext(result_path)[1].lower()
        if file_ext == '.csv':
            df = pd.read_csv(result_path, nrows=10)
        else:  # .xlsx
            df = pd.read_excel(result_path, nrows=10)
        
        # 获取结果列和行索引
        result_cols = [col for col in df.columns if '处理结果' in col or 'AI处理结果' in col]
        if result_cols:
            result_col = result_cols[0]  # 使用第一个匹配的结果列
            for i, row in df.iterrows():
                preview_data.append({
                    'row_index': i + 1,  # 行号（从1开始）
                    'result': str(row[result_col]) if not pd.isna(row[result_col]) else ''
                })
        
        return jsonify({
            'success': True,
            'preview_data': preview_data
        })
    except Exception as e:
        logger.error(f"获取结果预览错误: {str(e)}")
        return jsonify({'error': f'获取结果预览错误: {str(e)}'}), 500

# 路由：获取历史任务列表
@app.route('/history_tasks', methods=['GET'])
def history_tasks():
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        
        tasks, total = app.task_service.get_history_tasks(page, per_page)
        return jsonify({
            'tasks': tasks,
            'total': total,
            'page': page,
            'per_page': per_page
        })
    except Exception as e:
        logger.error(f"获取历史任务错误: {str(e)}")
        return jsonify({'error': f'获取历史任务错误: {str(e)}'}), 500

# 路由：历史任务页面
@app.route('/history')
def history():
    return render_template('history.html')

# 路由：API设置页面
@app.route('/api_settings')
def api_settings():
    return render_template('api_settings.html')

# 路由：获取任务实时处理结果
@app.route('/task_results/<int:task_id>', methods=['GET'])
def task_results(task_id):
    try:
        # 获取任务信息
        task = app.task_service.get_task_status(task_id)
        if not task:
            return jsonify({'error': f'找不到任务 {task_id}'}), 404
            
        # 获取最近处理的3条数据
        logs, _ = app.task_service.get_task_logs(task_id, limit=3)
        
        # 调试输出
        logger.info(f"获取到任务 {task_id} 的日志数量: {len(logs)}")
        
        # 构建响应数据
        results = []
        for log in logs:
            logger.debug(f"处理日志: {log}")
            if log['status'] == 'success':
                # 安全获取响应文本字段
                response_text = log.get('response_text', '')
                
                # 如果确实有响应文本，添加到结果中
                if response_text:
                    results.append({
                        'row_index': log['row_index'] + 1,  # 行号从1开始显示
                        'result': response_text
                    })
                    logger.info(f"添加处理结果 行:{log['row_index'] + 1}, 结果长度:{len(response_text)}")
        
        # 调试输出
        logger.info(f"返回结果数量: {len(results)}")
            
        return jsonify({
            'success': True,
            'results': results,
            'task_status': task['status'],
            'processed_count': task['processed_count'],
            'total_count': task['total_count']
        })
    except Exception as e:
        logger.error(f"获取任务实时结果错误: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({'error': f'获取任务实时结果错误: {str(e)}'}), 500

# 路由：获取API配置列表
@app.route('/api_configs', methods=['GET'])
def get_api_configs():
    try:
        configs = app.llm_service.get_api_configs()
        return jsonify(configs)
    except Exception as e:
        logger.error(f"获取API配置错误: {str(e)}")
        return jsonify({'error': f'获取API配置错误: {str(e)}'}), 500

# 路由：保存API配置
@app.route('/save_api_config', methods=['POST'])
def save_api_config():
    data = request.json
    try:
        config_id = app.llm_service.save_api_config(data)
        return jsonify({'success': True, 'config_id': config_id})
    except Exception as e:
        logger.error(f"保存API配置错误: {str(e)}")
        return jsonify({'error': f'保存API配置错误: {str(e)}'}), 500

# 路由：删除API配置
@app.route('/delete_api_config/<int:config_id>', methods=['POST'])
def delete_api_config(config_id):
    try:
        app.llm_service.delete_api_config(config_id)
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"删除API配置错误: {str(e)}")
        return jsonify({'error': f'删除API配置错误: {str(e)}'}), 500

# 路由：保存模板
@app.route('/save_template', methods=['POST'])
def save_template():
    data = request.json
    try:
        template_id = app.task_service.save_template(data['name'], data['content'])
        return jsonify({'success': True, 'template_id': template_id})
    except Exception as e:
        logger.error(f"保存模板错误: {str(e)}")
        return jsonify({'error': f'保存模板错误: {str(e)}'}), 500

# 路由：获取模板列表
@app.route('/templates', methods=['GET'])
def get_templates():
    try:
        templates = app.task_service.get_templates()
        return jsonify(templates)
    except Exception as e:
        logger.error(f"获取模板错误: {str(e)}")
        return jsonify({'error': f'获取模板错误: {str(e)}'}), 500

# 路由：删除模板
@app.route('/delete_template/<int:template_id>', methods=['POST'])
def delete_template(template_id):
    try:
        app.task_service.delete_template(template_id)
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"删除模板错误: {str(e)}")
        return jsonify({'error': f'删除模板错误: {str(e)}'}), 500

if __name__ == '__main__':
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    if not os.path.exists(app.config['RESULT_FOLDER']):
        os.makedirs(app.config['RESULT_FOLDER'])
    
    app.run(host='0.0.0.0', port=5000, debug=True)