# Excel-LLM批处理系统

一个基于Flask的Web应用程序，用于批量处理Excel文件数据并通过大型语言模型(LLM)API进行处理，支持图片识别和处理功能。

## 功能概述

- 上传并解析Excel文件（支持.xlsx、.xls和.csv格式）
- 使用模板化提示词处理Excel数据
- 支持图片字段处理（将图片URL转换为base64并与文本一起提交给LLM）
- 支持多种LLM API，包括OpenAI兼容接口和阿里云通义千问VL
- 可配置并发处理，提高处理效率
- 实时显示处理进度和结果预览
- 保存和加载提示词模板
- 历史任务管理和结果下载
- API配置管理，支持多API切换

## 技术架构

### 后端

- **Web框架**: Flask
- **数据处理**: Pandas, NumPy
- **Excel处理**: openpyxl, xlrd
- **图片处理**: Pillow
- **数据库**: SQLite
- **并发处理**: concurrent.futures, threading
- **HTTP请求**: requests

### 前端

- **UI框架**: Bootstrap 5
- **JavaScript库**: jQuery, SweetAlert2
- **代码编辑器**: CodeMirror

## 系统结构

```
Excel-LLM批处理系统/
├── app.py                 # Flask应用主入口
├── config.py              # 应用配置
├── requirements.txt       # 依赖包列表
├── database/              # 数据库模块
│   ├── db.py              # 数据库连接和操作
│   └── models.py          # 数据模型
├── services/              # 服务模块
│   ├── excel_service.py   # Excel处理服务
│   ├── llm_service.py     # LLM API调用服务
│   ├── image_service.py   # 图片处理服务
│   └── task_service.py    # 任务管理服务
├── static/                # 静态资源
│   ├── css/               # CSS样式
│   └── js/                # JavaScript脚本
├── templates/             # HTML模板
│   ├── index.html         # 主页模板
│   ├── history.html       # 历史记录页面
│   ├── api_settings.html  # API设置页面
│   └── components/        # 组件模板
├── uploads/               # 上传文件存储目录
└── results/               # 处理结果存储目录
```

## 主要模块说明

### 服务模块

1. **Excel服务 (excel_service.py)**
   - 解析Excel文件获取字段和预览数据
   - 提取Excel数据
   - 处理提示词模板中的变量替换
   - 保存处理结果到新的Excel文件

2. **LLM服务 (llm_service.py)**
   - 支持多种LLM API接口（OpenAI兼容接口、阿里云通义千问VL等）
   - 管理API配置（URL、密钥、模型名称等）
   - 发送请求到LLM API并处理响应

3. **图片服务 (image_service.py)**
   - 下载图片并转换为base64编码
   - 优化图片大小和质量
   - 从Excel行数据中提取图片URL并处理

4. **任务服务 (task_service.py)**
   - 创建和管理处理任务
   - 实现并发处理逻辑
   - 跟踪任务进度和状态
   - 管理任务结果和日志

### 数据库模型

1. **Task**: 任务信息
2. **TaskLog**: 任务处理日志
3. **Template**: 提示词模板
4. **APIConfig**: API配置
5. **ExcelSchema**: Excel表结构信息

## 安装指南

### 系统要求

- Python 3.8+
- pip包管理器

### 安装步骤

1. 克隆或下载项目代码

2. 安装依赖包
   ```bash
   pip install -r requirements.txt
   ```

3. 创建上传和结果目录
   ```bash
   mkdir uploads results
   ```

4. 运行应用
   ```bash
   python app.py
   ```

5. 访问应用
   默认地址：http://localhost:5000

## 使用指南

### 1. 配置API设置

首先，访问"API设置"页面，配置您的LLM API信息：

- 支持OpenAI兼容的API和阿里云通义千问VL API
- 填写API访问URL、API密钥和模型名称
- 可以保存多个API配置，并设置默认配置
- 支持复制现有配置，快速创建类似配置而无需重新输入所有信息
- 支持流式输出模式，解决某些API（如阿里云通义千问）不支持HTTP调用的问题

### 2. 上传Excel文件

在主页上传Excel文件（支持.xlsx、.xls和.csv格式）：

- 系统会自动解析文件并显示字段列表和数据预览
- 支持中文等多种编码的CSV文件

### 3. 编写提示词模板

使用提示词编辑器编写模板：

- 点击左侧字段按钮可以在光标位置插入字段标记，格式为`{{字段名}}`
- 这些标记会在处理时被替换为实际的行数据值
- 可以保存常用模板以便重复使用

### 4. 配置图片字段和并发数

如果需要处理图片：

- 选择包含图片URL的字段
- 系统会自动下载图片并转换为base64格式提交给LLM

设置并发处理数量：
- 根据任务大小和API限制选择合适的并发数

### 5. 开始批处理

点击"开始批处理"按钮启动任务：

- 系统会显示实时进度和预计剩余时间
- 完成后可以下载处理结果Excel文件

### 6. 管理历史任务

在"历史记录"页面可以：

- 查看历史任务的状态和结果
- 下载历史任务的处理结果
- 删除不需要的历史任务

## 注意事项

- API密钥和配置信息存储在本地SQLite数据库中
- 处理大量数据时，建议适当控制并发数，避免API限流
- 图片处理会增加API调用的token消耗
- 如遇到"current user api does not support http call"错误，请在API配置中启用"流式输出"选项

## 许可证

本项目采用MIT许可证。详情请参阅LICENSE文件。

## 联系方式

如有问题或建议，请提交issue或联系项目维护者。

---

*Excel-LLM批处理系统 - 让Excel数据处理更智能*