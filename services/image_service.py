#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import io
import time
import base64
import requests
from PIL import Image
import logging
from flask import current_app

logger = logging.getLogger(__name__)

class ImageService:
    """图片处理服务"""
    
    def __init__(self):
        """初始化图片服务"""
        # 延迟配置加载，避免应用上下文问题
        self._user_agent = None
        self._download_timeout = None
        self._max_size = None
        self._supported_formats = None

    @property
    def user_agent(self):
        """获取User-Agent"""
        if self._user_agent is None:
            self._user_agent = current_app.config.get('DEFAULT_USER_AGENT', 'Mozilla/5.0')
        return self._user_agent

    @property
    def download_timeout(self):
        """获取下载超时时间"""
        if self._download_timeout is None:
            self._download_timeout = current_app.config.get('IMAGE_DOWNLOAD_TIMEOUT', 10)
        return self._download_timeout

    @property
    def max_size(self):
        """获取最大图片大小"""
        if self._max_size is None:
            self._max_size = current_app.config.get('MAX_IMAGE_SIZE', 4 * 1024 * 1024)
        return self._max_size

    @property
    def supported_formats(self):
        """获取支持的图片格式"""
        if self._supported_formats is None:
            self._supported_formats = current_app.config.get('SUPPORTED_IMAGE_FORMATS',
                                                       ['jpg', 'jpeg', 'png', 'gif', 'webp'])
        return self._supported_formats
    
    def download_image_to_base64(self, image_url):
        """
        下载图片并转换为base64编码
        
        Args:
            image_url: 图片URL
            
        Returns:
            str: base64编码的图片数据
        """
        try:
            # 如果URL已经是base64数据，直接返回
            if image_url.startswith('data:image'):
                # 已经是base64格式，提取base64部分
                if ',' in image_url:
                    return image_url.split(',', 1)[1]
                return image_url

            # 构建请求头
            headers = {
                'User-Agent': self.user_agent,
                'Accept': 'image/webp,image/*,*/*;q=0.8',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Referer': image_url
            }
            
            # 下载图片
            response = requests.get(image_url, headers=headers, timeout=self.download_timeout, stream=True)
            response.raise_for_status()
            
            # 检查内容类型
            content_type = response.headers.get('Content-Type', '')
            if not content_type.startswith('image/'):
                raise ValueError(f"不是有效的图片内容类型: {content_type}")
            
            # 检查内容大小
            content_length = int(response.headers.get('Content-Length', 0))
            if content_length > self.max_size:
                raise ValueError(f"图片太大: {content_length} 字节, 最大允许 {self.max_size} 字节")
            
            # 读取内容并优化图片
            img_data = response.content
            img_base64 = self.optimize_image(img_data)
            
            return img_base64
            
        except requests.RequestException as e:
            logger.error(f"下载图片时出错: {str(e)}")
            raise ValueError(f"图片下载失败: {str(e)}")
        except Exception as e:
            logger.error(f"处理图片时出错: {str(e)}")
            raise
    
    def optimize_image(self, img_data, max_width=1024, max_height=1024, 
                      quality=85, target_format='JPEG'):
        """
        优化图片大小和质量
        
        Args:
            img_data: 图片数据
            max_width: 最大宽度
            max_height: 最大高度
            quality: JPEG压缩质量（1-100）
            target_format: 目标格式（JPEG, PNG等）
            
        Returns:
            str: base64编码的优化图片
        """
        try:
            # 打开图片
            img = Image.open(io.BytesIO(img_data))
            
            # 判断是否需要调整大小
            width, height = img.size
            if width > max_width or height > max_height:
                # 计算调整比例
                ratio = min(max_width / width, max_height / height)
                new_width = int(width * ratio)
                new_height = int(height * ratio)
                img = img.resize((new_width, new_height), Image.LANCZOS)
            
            # 转换为RGB模式（如果是RGBA）
            if img.mode == 'RGBA':
                background = Image.new('RGB', img.size, (255, 255, 255))
                background.paste(img, mask=img.split()[3])  # 使用alpha通道作为蒙版
                img = background
            elif img.mode != 'RGB':
                img = img.convert('RGB')
            
            # 保存到内存中
            buffer = io.BytesIO()
            img.save(buffer, format=target_format, quality=quality, optimize=True)
            buffer.seek(0)
            
            # 转换为base64
            img_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
            
            logger.info(f"图片已优化，原始大小: {len(img_data)} 字节，优化后: {len(buffer.getvalue())} 字节")
            return img_base64
            
        except Exception as e:
            logger.error(f"优化图片时出错: {str(e)}")
            # 如果优化失败，返回原始图片的base64编码
            return base64.b64encode(img_data).decode('utf-8')
    
    def download_multiple_images(self, image_urls):
        """
        批量下载多个图片并转换为base64
        
        Args:
            image_urls: 图片URL列表
            
        Returns:
            list: base64编码的图片数据列表
        """
        result = []
        errors = []
        
        for i, url in enumerate(image_urls):
            try:
                if not url:  # 跳过空URL
                    result.append(None)
                    continue
                
                # 下载并转换图片
                base64_data = self.download_image_to_base64(url)
                result.append(base64_data)
                
                # 避免频繁请求
                if i < len(image_urls) - 1:
                    time.sleep(0.5)
                    
            except Exception as e:
                logger.error(f"处理图片 {url} 时出错: {str(e)}")
                errors.append(f"图片 {url}: {str(e)}")
                result.append(None)
        
        if errors:
            logger.warning(f"有 {len(errors)} 个图片处理失败: {errors}")
        
        return result
    
    def extract_image_data_from_row(self, row_data, image_fields):
        """
        从行数据中提取图片URL并下载转换
        
        Args:
            row_data: 行数据字典
            image_fields: 图片字段列表
            
        Returns:
            list: base64编码的图片数据列表
        """
        if not image_fields:
            return []
        
        # 提取图片URL
        image_urls = []
        for field in image_fields:
            if field in row_data:
                url = str(row_data.get(field, ''))
                if url:
                    image_urls.append(url)
                else:
                    image_urls.append(None)
            else:
                image_urls.append(None)
        
        # 下载并转换图片
        if image_urls:
            return self.download_multiple_images(image_urls)
        
        return []