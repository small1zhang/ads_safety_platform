#!/usr/bin/env python3
"""
setup.py - 项目安装配置
"""

from setuptools import setup, find_packages

setup(
    name='ads_safety_platform',
    version='1.0.0',
    description='自动驾驶安全验证平台 - 集成CARLA、RSS规则检测与知识图谱',
    author='ZCode Agent',
    packages=find_packages(where='src'),
    package_dir={'': 'src'},
    python_requires='>=3.8',
    install_requires=[
        'numpy>=1.20.0',
        'matplotlib>=3.4.0',
        'networkx>=2.6.0',
    ],
    extras_require={
        'dev': [
            'pytest>=6.0',
            'pytest-cov>=2.0',
            'black>=21.0',
            'flake8>=3.9',
        ],
    },
    entry_points={
        'console_scripts': [
            'ads-run-realtime=ads_safety_platform.realtime_multi_anomaly_demo:main',
            'ads-run-carla=ads_safety_platform.run_carla_scenario:main',
            'ads-verify-safety=ads_safety_platform.safety_judge:main',
        ],
    },
)