#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
paths.py - 项目路径配置
统一管理项目所有输出路径
"""

from pathlib import Path
import os


class ProjectPaths:
    """项目路径管理器"""
    
    def __init__(self, project_root: str = None):
        if project_root is None:
            # 默认使用backend/app为基准
            current = Path(__file__).resolve()
            project_root = current.parent.parent.parent
        
        self.project_root = Path(project_root)
        
        # 确保目录存在
        self.output_dir = self.project_root / 'output'
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.html_output_dir = self.output_dir / 'html'
        self.html_output_dir.mkdir(parents=True, exist_ok=True)
        
        self.anomalies_dir = self.output_dir / 'anomalies'
        self.anomalies_dir.mkdir(parents=True, exist_ok=True)
    
    @property
    def visualization_demo(self) -> Path:
        """可视化页面路径"""
        return self.html_output_dir / 'visualization_demo.html'
    
    @property
    def knowledge_graph_latest(self) -> Path:
        """最新的知识图谱HTML"""
        return self.html_output_dir / 'knowledge_graph_latest.html'
    
    def get_anomaly_path(self, anomaly_id: int, timestamp: str) -> Path:
        """获取异常详情页面路径"""
        ts = timestamp.replace(':', '-')[:14]
        return self.anomalies_dir / f'anomaly_{anomaly_id:03d}_{ts}.html'
    
    def get_kg_path(self, timestamp: str) -> Path:
        """获取知识图谱页面路径"""
        ts = timestamp.replace(':', '-').replace('-', '')[:14]
        return self.html_output_dir / f'knowledge_graph_{ts}.html'


# 全局实例
PATHS = ProjectPaths()