"""
scenarios 包 - 场景构建与验证模块

提供：
- 场景构建器：创建可配置的测试场景
- 场景验证器：使用RSS规则验证场景
- 场景数据：存储和管理场景数据

用法示例：
    from ads_safety_platform.scenarios import ScenarioBuilder, ScenarioValidator
    
    # 创建场景
    builder = ScenarioBuilder()
    scenario = builder.create_red_light_scenario()
    
    # 验证场景
    validator = ScenarioValidator()
    result = validator.validate(scenario)
"""

from .scenario_injector import (
    Scenario,
    ScenarioBuilder,
    ScenarioPresets,
    ScenarioType,
    TrafficLightState,
    VehicleConfig,
    TrafficLightConfig,
    PedestrianConfig,
)

from .scenario_validator import (
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