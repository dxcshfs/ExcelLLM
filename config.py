#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
from pathlib import Path

# 应用基本目录
BASE_DIR = Path(__file__).resolve().parent

# 上传文件保存目录
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# 处理结果保存目录
RESULT_FOLDER = os.path.join(BASE_DIR, 'results')
if not os.path.exists(RESULT_FOLDER):
    os.makedirs(RESULT_FOLDER)

# 数据库配置
DATABASE = os.path.join(BASE_DIR, 'excell_llm.db')

# 文件上传配置
MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 最大上传文件大小：50MB
ALLOWED_EXTENSIONS = {'xlsx', 'xls', 'csv'}

# LLM API请求配置
API_REQUEST_TIMEOUT = 30  # 请求超时时间（秒）
API_RETRY_COUNT = 3       # 请求失败重试次数
API_RETRY_DELAY = 2       # 重试间隔（秒）

# 图片处理配置
DEFAULT_USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
IMAGE_DOWNLOAD_TIMEOUT = 10  # 图片下载超时时间（秒）
MAX_IMAGE_SIZE = 4 * 1024 * 1024  # 最大图片大小：4MB
SUPPORTED_IMAGE_FORMATS = ['jpg', 'jpeg', 'png', 'gif', 'webp']