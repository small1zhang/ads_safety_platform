#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
backend/app/config.py - 配置管理
"""

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """应用配置"""
    
    # CARLA 配置
    carla_host: str = "localhost"
    carla_port: int = 2000
    carla_timeout: float = 5.0
    
    # 检测配置
    detect_interval: float = 1.0
    max_scenarios: int = 1000
    
    # 输出配置
    output_dir: str = "/home/aisecurity/01_ZHB/output"
    temp_dir: str = "/tmp"
    
    # 风险阈值
    risk_threshold_critical: float = 0.7
    risk_threshold_high: float = 0.4
    risk_threshold_medium: float = 0.2
    
    # 数据库配置
    database_url: Optional[str] = "sqlite:///./data/safety.db"
    
    class Config:
        env_file = ".env"
        case_sensitive = False


# 全局配置实例
settings = Settings()