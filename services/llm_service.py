#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import time
import base64
import requests
import logging
import sys
import platform
from flask import current_app
from database.models import APIConfig

# 导入OpenAI客户端库
try:
    from openai import OpenAI
    OPENAI_CLIENT_AVAILABLE = True
except ImportError:
    OPENAI_CLIENT_AVAILABLE = False
    logging.warning("OpenAI客户端库未安装，请使用pip install openai安装。")

logger = logging.getLogger(__name__)

class LLMService:
    """大语言模型API调用服务 - 重构版"""
    
    def __init__(self):
        """初始化LLM服务"""
        # 添加调试模式标志，从应用配置中获取
        self.debug_mode = False
        # 初始化时尝试从应用配置获取调试模式
        try:
            from flask import current_app
            self.debug_mode = current_app.config.get('DEBUG', False)
        except:
            # 未在Flask上下文中或无法获取配置时，默认为非调试模式
            pass
            
        # 添加配置缓存
        self._config_cache = {}          # ID为键的配置缓存
        self._default_config_cache = None  # 默认配置缓存
        self._cache_expiry = {}          # 缓存过期时间
        
        # 添加客户端连接池
        self._client_pool = {}           # 客户端连接池
        self._client_last_used = {}      # 客户端最后使用时间
    
    def get_api_configs(self):
        """
        获取所有API配置
        
        Returns:
            list: API配置列表
        """
        configs = APIConfig.get_all()
        return [config.to_dict() for config in configs]
    
    def get_default_api_config(self):
        """
        获取默认API配置
        
        Returns:
            dict: 默认API配置
        """
        config = APIConfig.get_default()
        if not config:
            raise ValueError("未找到默认API配置")
        return config
    
    def save_api_config(self, config_data):
        """
        保存API配置
        
        Args:
            config_data: 配置数据
            
        Returns:
            int: 配置ID
        """
        try:
            config_id = config_data.get('id')
            
            if config_id:
                # 更新现有配置
                config = APIConfig.get_by_id(config_id)
                if not config:
                    raise ValueError(f"找不到ID为{config_id}的API配置")
            else:
                # 创建新配置
                config = APIConfig()
            
            # 更新配置属性
            config.name = config_data.get('name')
            config.type = config_data.get('type')
            config.url = config_data.get('url')
            config.api_key = config_data.get('api_key')
            config.model_name = config_data.get('model_name')
            
            # 处理其他参数
            other_params = config_data.get('other_params')
            if isinstance(other_params, str):
                try:
                    other_params = json.loads(other_params)
                except:
                    other_params = {}
            config.other_params = other_params or {}
            
            # 设置是否为默认配置
            config.is_default = 1 if config_data.get('is_default') else 0
            
            # 设置是否使用流式输出
            config.use_stream = 1 if config_data.get('use_stream') else 0
            
            # 保存配置
            config_id = config.save()
            
            logger.info(f"成功保存API配置: {config.name}")
            return config_id
            
        except Exception as e:
            logger.error(f"保存API配置时出错: {str(e)}")
            raise
    
    def delete_api_config(self, config_id):
        """
        删除API配置
        
        Args:
            config_id: 配置ID
            
        Returns:
            bool: 是否成功删除
        """
        try:
            config = APIConfig.get_by_id(config_id)
            if not config:
                raise ValueError(f"找不到ID为{config_id}的API配置")
            
            # 不允许删除唯一的配置
            configs = APIConfig.get_all()
            if len(configs) <= 1:
                raise ValueError("不能删除唯一的API配置")
            
            # 如果删除的是默认配置，则将另一个配置设为默认
            if config.is_default:
                for other_config in configs:
                    if other_config.id != config_id:
                        other_config.is_default = 1
                        other_config.save()
                        break
            
            result = config.delete()
            logger.info(f"成功删除API配置: {config.name}")
            return result
            
        except Exception as e:
            logger.error(f"删除API配置时出错: {str(e)}")
            raise
    
    def call_api(self, prompt, image_data=None, config_id=None):
        """
        统一的LLM API调用方法
        
        Args:
            prompt: 提示词
            image_data: 图片数据（base64编码）
            config_id: API配置ID（为None则使用默认配置）
            
        Returns:
            tuple: (响应文本, token数量, 处理时间)
        """
        # 获取API配置
        try:
            config = self._get_config(config_id)
            
            # 验证是否安装了OpenAI客户端库
            if not OPENAI_CLIENT_AVAILABLE:
                raise ImportError("OpenAI客户端库未安装，请使用pip install openai安装。")
            
            # 从配置获取重试参数
            retry_count = current_app.config.get('API_RETRY_COUNT', 3)
            timeout = current_app.config.get('API_REQUEST_TIMEOUT', 30)
            retry_delay = current_app.config.get('API_RETRY_DELAY', 2)
            
            # 开始计时
            start_time = time.time()
            
            # 构建消息内容
            messages = self._build_messages(prompt, image_data)
            
            # 确定是否应该使用流式输出
            use_stream = self._should_use_stream(config)
            
            # 构建API请求参数
            api_params = self._build_api_params(config, messages, use_stream)
            
            # 尝试多次调用API
            for attempt in range(retry_count):
                try:
                    # 对于流式请求设置更长的超时时间
                    call_timeout = timeout * 2 if use_stream else timeout
                    
                    # 使用OpenAI客户端库调用API
                    response_text, token_count = self._call_with_client(config, api_params, call_timeout)
                    
                    # 计算处理时间
                    processing_time = time.time() - start_time
                    return response_text, token_count, processing_time
                    
                except Exception as e:
                    error_type = type(e).__name__
                    error_details = str(e)
                    logger.error(f"API调用失败 (尝试 {attempt+1}/{retry_count}): [{error_type}] {error_details}")
                    
                    # 记录当前尝试的请求信息
                    base_url = self._get_base_url(config)
                    logger.error(f"请求详情: BaseURL={base_url}, 模型={config.model_name}, 流式={use_stream}")
                    
                    if attempt < retry_count - 1:
                        logger.info(f"将在 {retry_delay} 秒后重试...")
                        time.sleep(retry_delay)
                    else:
                        # 最后一次尝试失败，抛出更详细的错误
                        raise
                        
        except Exception as e:
            error_type = type(e).__name__
            error_details = str(e)
            
            logger.error(f"调用API时出错: [{error_type}] {error_details}")
            
            # 添加排查建议
            if "timeout" in error_details.lower():
                logger.error("排查建议: API响应超时，请检查网络连接或增加超时时间")
            elif "connection" in error_details.lower():
                logger.error("排查建议: 无法连接到API服务器，请检查网络连接和API基础URL是否正确")
            
            raise
    
    def _get_config(self, config_id):
        """
        获取API配置对象（带缓存）
        
        Args:
            config_id: 配置ID，为None则返回默认配置
            
        Returns:
            APIConfig: API配置对象
        """
        import time
        current_time = time.time()
        
        # 检查是否使用默认配置
        if not config_id:
            # 如果缓存存在且未过期
            if (self._default_config_cache and
                'default' in self._cache_expiry and
                current_time - self._cache_expiry['default'] < 60):  # 缓存1分钟
                return self._default_config_cache
                
            config = APIConfig.get_default()
            if not config:
                raise ValueError("未找到默认API配置")
                
            # 更新缓存
            self._default_config_cache = config
            self._cache_expiry['default'] = current_time
            return config
        
        # 检查ID配置缓存
        cache_key = f"id_{config_id}"
        if (cache_key in self._config_cache and
            cache_key in self._cache_expiry and
            current_time - self._cache_expiry[cache_key] < 60):  # 缓存1分钟
            return self._config_cache[cache_key]
            
        # 从数据库获取
        config = APIConfig.get_by_id(config_id)
        if not config:
            raise ValueError(f"找不到ID为{config_id}的API配置")
            
        # 更新缓存
        self._config_cache[cache_key] = config
        self._cache_expiry[cache_key] = current_time
        return config
    
    def _get_base_url(self, config):
        """
        获取API基础URL
        
        Args:
            config: API配置对象
            
        Returns:
            str: API基础URL
        """
        # 记录API配置信息
        logger.info(f"正在获取API基础URL - 类型: {config.type}, 模型: {config.model_name}, URL: {config.url}")
        
        # 直接返回配置的URL
        return config.url
    
    def _should_use_stream(self, config):
        """
        判断是否应该使用流式输出
        
        Args:
            config: API配置对象
            
        Returns:
            bool: 是否使用流式输出
        """
        # 直接返回配置中的流式输出设置
        return config.use_stream == 1
        
    def _extract_error_details(self, error):
        """
        提取错误的详细信息
        
        Args:
            error: 异常对象
            
        Returns:
            tuple: (错误类型, 错误详情, 状态码, 响应文本)
        """
        error_type = type(error).__name__
        error_details = str(error)
        
        # 提取状态码
        status_code = getattr(error, 'status_code', 'N/A')
        
        # 提取响应文本
        response_text = getattr(error, 'response', {})
        if hasattr(response_text, 'text'):
            response_text = response_text.text
        elif hasattr(response_text, 'json'):
            try:
                response_text = json.dumps(response_text.json())
            except:
                response_text = str(response_text)
        else:
            response_text = str(response_text)
            
        return error_type, error_details, status_code, response_text
    
    def _build_messages(self, prompt, image_data=None):
        """
        构建API请求的消息内容，包括文本和图片
        
        Args:
            prompt: 提示词
            image_data: 图片数据（base64编码）
            
        Returns:
            list: 消息列表
        """
        # 添加系统消息
        messages = [
            {"role": "system", "content": "You are a helpful assistant."}
        ]
        
        # 根据API类型处理用户消息格式
        if image_data:
            # 处理带图片的多模态请求
            content = [{"type": "text", "text": prompt}]
            
            # 处理图片数据
            if isinstance(image_data, list):
                # 处理多张图片
                for img in image_data:
                    if img:
                        image_content = self._process_image(img)
                        if image_content:
                            content.append(image_content)
            elif image_data:
                # 处理单张图片
                image_content = self._process_image(image_data)
                if image_content:
                    content.append(image_content)
                    logger.info(f"添加了1张图片到请求中")
            
            # 添加用户消息
            messages.append({"role": "user", "content": content})
        else:
            # 处理纯文本请求 - 简化格式
            messages.append({"role": "user", "content": prompt})
        
        logger.info(f"构建消息: {json.dumps(messages, ensure_ascii=False)[:200]}...")
        return messages
    
    def _process_image(self, image_data):
        """
        处理图片数据，转换为API可接受的格式
        
        Args:
            image_data: 图片数据（base64编码或URL）
            
        Returns:
            dict: 图片内容对象
        """
        try:
            if isinstance(image_data, str) and image_data.startswith('data:image'):
                # 已经是base64格式
                image_url = image_data
            else:
                # 需要转换为base64
                image_url = f"data:image/jpeg;base64,{image_data}"
            
            return {
                "type": "image_url",
                "image_url": {"url": image_url}
            }
        except Exception as e:
            logger.error(f"处理图片数据时出错: {str(e)}")
            return None
    
    def _build_api_params(self, config, messages, use_stream):
        """
        构建API请求参数
        
        Args:
            config: API配置对象
            messages: 消息内容
            use_stream: 是否使用流式输出
            
        Returns:
            dict: API请求参数
        """
        # 阿里云模型名称映射（可能需要转换模型名称）
        aliyun_model_map = {
            "qwen-turbo-latest": "qwen-turbo",
            "qwen-plus-latest": "qwen-plus",
            "qwen-max-latest": "qwen-max",
            # 可以根据实际情况添加更多映射
        }
        
        # 如果是阿里云API并且模型名在映射表中，使用映射的模型名
        model_name = config.model_name
        if ("dashscope" in config.url.lower() or "aliyun" in config.url.lower()) and model_name in aliyun_model_map:
            model_name = aliyun_model_map[model_name]
            logger.info(f"已将模型名称 '{config.model_name}' 映射为 '{model_name}'")
        
        # 构建基本参数
        params = {
            "model": model_name,
            "messages": messages,
            "stream": use_stream
        }
        
        # 如果使用流式输出，添加stream_options参数
        if use_stream:
            params["stream_options"] = {"include_usage": True}
        
        # 添加其他参数
        if config.other_params:
            for key, value in config.other_params.items():
                if key != "stream" and key != "stream_options":  # 避免冲突
                    params[key] = value
        
        # 记录完整参数（排除敏感信息）
        safe_params = {k: v for k, v in params.items() if k != "messages"}
        safe_params["messages"] = f"[包含 {len(messages)} 条消息]"
        logger.info(f"API请求参数: {json.dumps(safe_params, ensure_ascii=False)}")
        
        return params
    
    def _get_client(self, config, timeout):
        """
        从连接池获取客户端或创建新客户端
        
        Args:
            config: API配置对象
            timeout: 超时时间
            
        Returns:
            OpenAI: 客户端实例
        """
        import time
        base_url = self._get_base_url(config)
        client_key = f"{base_url}_{config.api_key}"
        current_time = time.time()
        
        # 检查连接池中是否有可用客户端
        if (client_key in self._client_pool and
            current_time - self._client_last_used.get(client_key, 0) < 120):  # 改为2分钟内使用过的客户端
            self._client_last_used[client_key] = current_time
            logger.debug(f"使用连接池中的客户端: {client_key[:20]}...")
            return self._client_pool[client_key]
        
        # 创建新客户端
        # 记录详细的连接信息
        logger.info(f"准备创建OpenAI客户端 - 模型: {config.model_name}, API类型: {config.type}")
        logger.info(f"连接参数 - BaseURL: {base_url}, Timeout: {timeout}")
        
        # 添加更多的连接信息便于调试
        connection_options = {
            "api_key": f"sk-...{config.api_key[-4:]}" if config.api_key else None,
            "base_url": base_url,
            "timeout": timeout
        }
        logger.info(f"连接选项: {json.dumps(connection_options, ensure_ascii=False)}")
        
        # 添加环境信息诊断（仅在调试模式下）
        if self.debug_mode:
            logger.info(f"Python版本: {sys.version}")
            logger.info(f"操作系统: {platform.platform()}")
            
            try:
                import openai
                logger.info(f"OpenAI库版本: {openai.__version__}")
            except (ImportError, AttributeError):
                logger.info("无法检测OpenAI库版本")
        
        # 为阿里云达世界API设置更合适的参数
        client_options = {
            "api_key": config.api_key,
            "base_url": base_url,
        }
        
        # 只有当timeout不是None时才添加
        if timeout:
            client_options["timeout"] = timeout * 2  # 增加超时时间
            
        # 根据API类型添加特定参数
        if config.type and config.type.lower() == "openai":
            # 标准OpenAI API不需要额外设置
            pass
        elif "dashscope" in base_url.lower() or "aliyun" in base_url.lower():
            # 阿里云达世界API特定配置
            client_options["default_headers"] = {
                "User-Agent": "Python/OpenAI-Compatible-Client",
                "Accept": "application/json",
                "Content-Type": "application/json"
            }
            # 对阿里云API，可能需要禁用某些功能
            client_options["max_retries"] = 1  # 降低重试次数
            
        # 只在调试模式执行网络诊断
        if self.debug_mode:
            try:
                import socket
                host = base_url.split("//")[-1].split("/")[0]
                logger.info(f"正在进行DNS解析: {host}")
                ip_info = socket.gethostbyname_ex(host)
                logger.info(f"DNS解析结果: {ip_info}")
            except Exception as dns_error:
                logger.warning(f"网络诊断失败: {str(dns_error)}")
                
        # 创建客户端
        logger.info(f"创建客户端，选项: {json.dumps({k: v for k, v in client_options.items() if k != 'api_key'}, ensure_ascii=False)}")
        client = OpenAI(**client_options)
        
        # 更新连接池
        self._client_pool[client_key] = client
        self._client_last_used[client_key] = current_time
        
        # 清理过期连接
        self._cleanup_clients()
        
        return client
        
    def _cleanup_clients(self):
        """
        清理超过10分钟未使用的客户端连接
        """
        import time
        current_time = time.time()
        expired_keys = []
        
        # 找出过期的客户端
        for key, last_used in self._client_last_used.items():
            if current_time - last_used > 180:  # 改为3分钟未使用就过期
                expired_keys.append(key)
        
        # 从连接池中移除
        for key in expired_keys:
            if key in self._client_pool:
                logger.debug(f"清理过期客户端: {key[:20]}...")
                del self._client_pool[key]
            if key in self._client_last_used:
                del self._client_last_used[key]
    
    def _call_with_client(self, config, params, timeout):
        """
        使用OpenAI客户端库调用API
        
        Args:
            config: API配置对象
            params: API请求参数
            timeout: 超时时间
            
        Returns:
            tuple: (响应文本, token数量)
        """
        try:
            # 记录请求参数
            logger.info(f"请求参数 - Stream: {params.get('stream', False)}, Stream Options: {params.get('stream_options', None)}")
            
            # 从连接池获取客户端
            client = self._get_client(config, timeout)
            
            # 根据是否使用流式输出选择不同的处理方式
            if params.get("stream", False):
                # 流式输出处理
                return self._handle_streaming_response(client, params)
            else:
                # 非流式输出处理
                return self._handle_normal_response(client, params)
                
        except Exception as e:
            error_type = type(e).__name__
            error_details = str(e)
            # 重新获取base_url，避免未定义的问题
            
            base_url = self._get_base_url(config)
            connection_info = f"BaseURL: {base_url}, API类型: {config.type}, 模型: {config.model_name}"
            logger.error(f"创建OpenAI客户端时出错: [{error_type}] {error_details}")
            logger.error(f"连接信息: {connection_info}")
            
            # 增加更详细的网络错误诊断
            if "connection" in error_details.lower() or "apiconnection" in error_type.lower():
                # 尝试执行简单网络诊断
                try:
                    # 检查是否可以连接到目标服务器
                    import requests
                    import urllib.parse
                    
                    parsed_url = urllib.parse.urlparse(base_url)
                    base_domain = f"{parsed_url.scheme}://{parsed_url.netloc}"
                    
                    logger.info(f"正在尝试通过requests直接访问服务器基础域名: {base_domain}")
                    
                    # 使用简单GET请求测试连接
                    test_response = requests.get(
                        base_domain,
                        timeout=timeout,
                        headers={"User-Agent": "Connection-Test"}
                    )
                    
                    logger.info(f"连接测试结果 - 状态码: {test_response.status_code}")
                    logger.info(f"响应头: {dict(test_response.headers)}")
                    
                    # 尝试添加错误建议
                    if test_response.status_code >= 400:
                        logger.error(f"服务器可连接但返回错误状态码: {test_response.status_code}")
                        logger.error("建议: 检查API密钥是否正确，或联系API提供商确认服务状态")
                    else:
                        logger.info("服务器基础连接正常，问题可能在于API路径或认证参数")
                        
                except Exception as net_error:
                    net_error_type = type(net_error).__name__
                    logger.error(f"基础网络诊断失败: [{net_error_type}] {str(net_error)}")
                    logger.error("建议: 检查网络连接、防火墙设置或代理配置")
            
            # 直接抛出原始错误并添加更多排查建议
            error_msg = f"API连接错误 [{error_type}]: {error_details}"
            if "apikey" in error_details.lower() or "authorization" in error_details.lower():
                error_msg += " - 建议检查API密钥是否正确"
            elif "timeout" in error_details.lower():
                error_msg += " - 建议检查网络连接并增加超时时间"
            elif "connection" in error_details.lower():
                error_msg += " - 建议检查网络连接和防火墙设置，或联系网络管理员"
            
            raise ValueError(error_msg)
    
    def _handle_normal_response(self, client, params):
        """
        处理非流式响应
        
        Args:
            client: OpenAI客户端
            params: API请求参数
            
        Returns:
            tuple: (响应文本, token数量)
        """
        try:
            # 调用API获取响应
            response = client.chat.completions.create(**params)
            
            # 提取响应文本
            response_text = response.choices[0].message.content
            
            # 获取token数量
            token_count = 0
            if hasattr(response, "usage") and response.usage:
                token_count = response.usage.total_tokens
            
            return response_text, token_count
            
        except Exception as e:
            error_type = type(e).__name__
            error_details = str(e)
            
            # 提取错误详情
            error_type, error_details, status_code, response_text = self._extract_error_details(e)
                
            logger.error(f"处理非流式响应时出错: [{error_type}] {error_details}")
            logger.error(f"响应状态码: {status_code}, 响应内容: {response_text}")
            
            if "timeout" in error_details.lower():
                raise ValueError(f"API请求超时: {error_details}")
            elif "connection" in error_details.lower():
                raise ValueError(f"API连接失败 [{error_type}]: {error_details} - 请检查网络连接和API基础URL")
            elif status_code != 'N/A':
                raise ValueError(f"API请求失败 [HTTP {status_code}]: {error_details} - {response_text}")
            else:
                raise ValueError(f"API调用失败 [{error_type}]: {error_details}")
    
    
    def _handle_streaming_response(self, client, params):
        """
        处理流式响应
        
        Args:
            client: OpenAI客户端
            params: API请求参数
            
        Returns:
            tuple: (响应文本, token数量)
        """
        try:
            # 记录流式请求的详细信息
            logger.info(f"发送流式请求 - 模型: {params.get('model', 'unknown')}")
            logger.info(f"请求参数: {json.dumps({k: v for k, v in params.items() if k != 'messages'}, ensure_ascii=False)}")
            messages_info = f"消息数量: {len(params.get('messages', []))}"
            if params.get('messages') and len(params.get('messages')) > 0:
                first_msg = params.get('messages')[0]
                role = first_msg.get('role', 'unknown')
                content_sample = str(first_msg.get('content', ''))[:50] + "..." if len(str(first_msg.get('content', ''))) > 50 else str(first_msg.get('content', ''))
                messages_info += f", 第一条消息: {role} - {content_sample}"
            logger.info(messages_info)
            
            # 使用try-except捕获详细异常
            try:
                # 调用API获取流式响应
                logger.info("开始调用API（流式模式）...")
                # 为达世界API设置默认超时时间更长一些
                response_stream = client.chat.completions.create(**params)
                logger.info("API调用成功（流式模式）")
            except Exception as api_error:
                logger.error(f"API调用异常详情: [{type(api_error).__name__}] {str(api_error)}")
                # 尝试获取更多异常信息
                if hasattr(api_error, "__dict__"):
                    logger.error(f"异常属性: {str({k: str(v) for k, v in api_error.__dict__.items() if k != 'request' and k != 'response'})}")
                    
                    # 增加详细的请求信息
                    if hasattr(api_error, "request"):
                        req = api_error.request
                        logger.error(f"请求方法: {req.method if hasattr(req, 'method') else 'Unknown'}")
                        logger.error(f"请求URL: {req.url if hasattr(req, 'url') else 'Unknown'}")
                        logger.error(f"请求头: {str({k: v for k, v in req.headers.items() if k.lower() != 'authorization'}) if hasattr(req, 'headers') else 'Unknown'}")
                raise
            
            # 收集所有内容（使用列表而非字符串拼接，提高效率）
            content_chunks = []
            token_count = 0
            
            # 记录流式响应开始
            logger.info("开始接收流式响应...")
            
            try:
                chunks_received = 0
                for chunk in response_stream:
                    chunks_received += 1
                    
                    # 添加详细的chunk处理日志（仅在调试模式下，降低记录频率）
                    if self.debug_mode and (chunks_received <= 2 or chunks_received % 100 == 0):
                        logger.debug(f"处理第{chunks_received}个响应块")
                    
                    # 处理不同格式的chunk
                    if hasattr(chunk, 'choices') and chunk.choices:
                        choice = chunk.choices[0]
                        
                        # 处理delta格式（OpenAI标准）
                        if hasattr(choice, 'delta') and hasattr(choice.delta, 'content') and choice.delta.content is not None:
                            content_chunks.append(choice.delta.content)
                        
                        # 处理message格式（某些API使用）
                        elif hasattr(choice, 'message') and hasattr(choice.message, 'content') and choice.message.content is not None:
                            content_chunks.append(choice.message.content)
                    
                    # 提取token使用情况（如果可用）
                    if hasattr(chunk, 'usage') and chunk.usage:
                        token_count = chunk.usage.total_tokens
                
                # 一次性拼接所有内容，提高效率
                full_content = ''.join(content_chunks)
                
                # 记录流式响应完成
                logger.info(f"流式响应接收完成，共处理{chunks_received}个响应块，收集到{len(full_content)}字符")
                
                # 如果没有提取到token数量，则估算
                if token_count == 0:
                    token_count = len(full_content.split()) * 1.3  # 估算token数量
            except Exception as chunk_error:
                # 捕获并记录处理单个chunk时的错误，但继续处理
                error_type = type(chunk_error).__name__
                error_message = str(chunk_error)
                logger.error(f"处理响应块时出错: [{error_type}] {error_message}")
                
                # 对于连接中断的特定错误，添加更多诊断信息
                if "RemoteProtocolError" in error_type or "ConnectionError" in error_type or "ChunkedEncodingError" in error_type:
                    logger.warning("检测到连接中断，这可能是由于服务器提前关闭了连接")
                    logger.info(f"已成功接收{chunks_received}个响应块，将尝试使用已收集的内容")
                
                # 如果已经收集了一些内容，继续返回已收集的内容
                if not content_chunks:
                    logger.error("未收集到任何内容，无法返回部分结果")
                    raise
                
                # 发生错误时也尝试拼接已收集的内容
                full_content = ''.join(content_chunks)
                logger.info(f"尽管连接中断，但成功拼接了{len(full_content)}个字符的内容")
            
            return full_content, int(token_count)
            
        except Exception as e:
            error_type = type(e).__name__
            error_details = str(e)
            
            # 提取错误详情
            error_type, error_details, status_code, response_text = self._extract_error_details(e)
                
            logger.error(f"处理流式响应时出错: [{error_type}] {error_details}")
            logger.error(f"响应状态码: {status_code}, 响应内容: {response_text}")
            
            if "timeout" in error_details.lower():
                raise ValueError(f"API流式请求超时: {error_details}")
            elif "connection" in error_details.lower():
                raise ValueError(f"API流式连接失败 [{error_type}]: {error_details} - 请检查网络连接和API基础URL")
            elif status_code != 'N/A':
                raise ValueError(f"API流式请求失败 [HTTP {status_code}]: {error_details} - {response_text}")
            else:
                raise ValueError(f"API流式调用失败 [{error_type}]: {error_details}")