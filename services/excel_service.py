#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import pandas as pd
import logging
from flask import current_app
from database.models import ExcelSchema

logger = logging.getLogger(__name__)

class ExcelService:
    """Excel文件处理服务"""
    
    def __init__(self):
        """初始化Excel服务"""
        pass
    
    def parse_excel(self, file_path):
        """
        解析Excel文件，获取字段和预览数据
        
        Args:
            file_path: Excel文件路径
            
        Returns:
            tuple: (字段列表, 预览数据)
        """
        try:
            logger.info(f"开始解析Excel文件: {file_path}")
            
            # 根据文件扩展名决定如何读取文件
            file_ext = os.path.splitext(file_path)[1].lower()
            
            if file_ext == '.csv':
                # 尝试不同编码读取CSV
                try:
                    df = pd.read_csv(file_path, encoding='utf-8', keep_default_na=True)
                except UnicodeDecodeError:
                    try:
                        df = pd.read_csv(file_path, encoding='gbk', keep_default_na=True)
                    except UnicodeDecodeError:
                        df = pd.read_csv(file_path, encoding='latin1', keep_default_na=True)
            else:  # .xlsx 或 .xls
                # 使用keep_default_na=True确保空值被正确处理为NaN
                df = pd.read_excel(file_path, keep_default_na=True)
            
            # 获取字段列表
            fields = df.columns.tolist()
            
            # 获取前5行作为预览数据
            preview_data = df.head(5).to_dict('records')
            
            # 处理空值和NaN，确保前端可以正确处理
            for row in preview_data:
                for key, value in row.items():
                    # 将NaN、None和空字符串统一处理为空字符串
                    if pd.isna(value) or value is None or (isinstance(value, str) and value.strip() == ''):
                        row[key] = ''
            
            # 确保字段名不包含空值
            valid_fields = []
            for field in fields:
                if field is not None and str(field).strip() != '':
                    valid_fields.append(str(field))
                else:
                    # 对于空字段名，使用一个默认值并记录日志
                    logger.warning(f"检测到空字段名，已替换为默认值")
                    valid_fields.append(f"未命名字段_{len(valid_fields)}")
            
            logger.info(f"成功解析Excel文件，获取到{len(valid_fields)}个字段")
            return valid_fields, preview_data
            
        except Exception as e:
            logger.error(f"解析Excel文件时出错: {str(e)}")
            raise
    
    def get_excel_data(self, schema_id):
        """
        根据schema_id获取Excel数据
        
        Args:
            schema_id: Excel schema的ID
            
        Returns:
            tuple: (DataFrame, 字段列表)
        """
        try:
            # 获取Excel schema
            schema = ExcelSchema.get_by_id(schema_id)
            if not schema:
                raise ValueError(f"找不到ID为{schema_id}的Excel schema")
            
            # 检查文件是否存在
            if not os.path.exists(schema.file_path):
                raise FileNotFoundError(f"找不到文件: {schema.file_path}")
            
            # 根据文件扩展名决定如何读取文件
            file_ext = os.path.splitext(schema.file_path)[1].lower()
            
            if file_ext == '.csv':
                # 尝试不同编码读取CSV
                try:
                    df = pd.read_csv(schema.file_path, encoding='utf-8', keep_default_na=True)
                except UnicodeDecodeError:
                    try:
                        df = pd.read_csv(schema.file_path, encoding='gbk', keep_default_na=True)
                    except UnicodeDecodeError:
                        df = pd.read_csv(schema.file_path, encoding='latin1', keep_default_na=True)
            else:  # .xlsx 或 .xls
                # 使用keep_default_na=True确保空值被正确处理为NaN
                df = pd.read_excel(schema.file_path, keep_default_na=True)
            
            # 确保字段名不包含空值
            valid_fields = []
            for field in schema.fields:
                if field is not None and str(field).strip() != '':
                    valid_fields.append(str(field))
                else:
                    # 对于空字段名，使用一个默认值
                    logger.warning(f"检测到空字段名，已替换为默认值")
                    valid_fields.append(f"未命名字段_{len(valid_fields)}")
            
            return df, valid_fields
            
        except Exception as e:
            logger.error(f"获取Excel数据时出错: {str(e)}")
            raise
            raise
    
    def save_result(self, df, result_column, result_file_path):
        """
        将处理结果保存到Excel文件
        
        Args:
            df: DataFrame对象
            result_column: 结果列数据
            result_file_path: 结果文件保存路径
            
        Returns:
            str: 结果文件路径
        """
        try:
            # 创建DataFrame的副本，避免修改原始数据
            df_copy = df.copy()
            
            # 确保结果列长度与DataFrame行数匹配
            if len(result_column) < len(df_copy):
                # 如果结果列短于数据行，填充None
                result_column = result_column + [None] * (len(df_copy) - len(result_column))
            elif len(result_column) > len(df_copy):
                # 如果结果列长于数据行，截断
                result_column = result_column[:len(df_copy)]
            
            # 确定结果列名称
            result_column_name = '处理结果'
            
            # 检查是否与原始数据中的列名重复
            if result_column_name in df_copy.columns:
                # 如果重复，则修改结果列名称
                logger.info(f"检测到原始数据中已存在'{result_column_name}'列，将结果列重命名为'AI{result_column_name}'")
                result_column_name = 'AI' + result_column_name
            
            # 创建新的DataFrame，将结果列和原始数据列合并
            result_df = pd.DataFrame({result_column_name: result_column})
            
            # 将原始数据列添加到结果DataFrame
            for col in df_copy.columns:
                result_df[col] = df_copy[col]
            
            # 创建目录（如果不存在）
            os.makedirs(os.path.dirname(result_file_path), exist_ok=True)
            
            # 决定保存格式
            file_ext = os.path.splitext(result_file_path)[1].lower()
            
            if file_ext == '.csv':
                result_df.to_csv(result_file_path, encoding='utf-8', index=False)
            else:  # .xlsx
                result_df.to_excel(result_file_path, index=False)
            
            logger.info(f"结果已保存到: {result_file_path}")
            return result_file_path
            
        except Exception as e:
            logger.error(f"保存结果时出错: {str(e)}")
            raise
    
    def process_template(self, template, row_data):
        """
        处理提示词模板，替换字段标记为实际值
        
        Args:
            template: 提示词模板
            row_data: 行数据
            
        Returns:
            str: 处理后的提示词
        """
        if row_data is None:
            logger.warning("收到空行数据进行模板处理")
            return template
            
        processed_template = template
        
        # 确保row_data是有效的字典
        if not isinstance(row_data, dict):
            logger.warning(f"行数据不是字典类型: {type(row_data)}")
            return template
            
        # 替换所有{{字段名}}的标记
        for field, value in row_data.items():
            if field is None or field == "":
                logger.warning("检测到空字段名")
                continue
                
            placeholder = f"{{{{{field}}}}}"
            
            # 将None值、NaN值和空字符串统一处理
            if value is None or pd.isna(value) or (isinstance(value, str) and value.strip() == ""):
                value = ""
            # 将数值转换为字符串
            elif isinstance(value, (int, float)):
                value = str(value)
            
            processed_template = processed_template.replace(placeholder, str(value))
        
        return processed_template