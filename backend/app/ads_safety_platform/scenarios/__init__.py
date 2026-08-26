"""
scenarios 包 - 场景模块

结构：
- builders/ : 场景构建器和验证器
- presets/ : 预设场景配置
- data/ : 场景数据文件
- templates/ : 场景模板

用法：
    from scenarios.builders import ScenarioBuilder, ScenarioValidator
    from scenarios.presets import get_preset_scenarios
"""

from .builders import (
    Scenario,
    ScenarioBuilder,
    ScenarioPresets,
    ScenarioType,
    TrafficLightState,
    VehicleConfig,
    TrafficLightConfig,
    PedestrianConfig,
    ScenarioValidator,
    Violation,
    ValidationResult,
)

__all__ = [
    'Scenario',
    'ScenarioBuilder',
    'ScenarioPresets',
    'ScenarioType',
    'TrafficLightState',
    'VehicleConfig',
    'TrafficLightConfig',
    'PedestrianConfig',
    'ScenarioValidator',
    'Violation',
    'ValidationResult',
]

__version__ = '1.0.0'