#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RSS 规则验证示例

本示例展示如何使用场景模块来验证 RSS 规则。

功能：
1. 创建不同类型的场景
2. 使用 RSS 规则验证场景
3. 生成验证报告

用法：
    python examples/rss_verification/demo.py
"""

import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scenarios.builders import (
    ScenarioBuilder,
    ScenarioValidator,
    ScenarioPresets,
    ScenarioType
)


def demo_basic_usage():
    """基础用法示例"""
    print("=" * 60)
    print("基础用法示例")
    print("=" * 60)
    
    # 创建场景构建器
    builder = ScenarioBuilder()
    
    # 创建一个直行道路场景
    scenario = builder.create_straight_road_scenario(
        ego_speed=20.0,  # 超速
        num_vehicles=3,
        road_length=80.0
    )
    
    print(f"场景名称: {scenario.name}")
    print(f"场景类型: {scenario.scenario_type.value}")
    print(f"自车速度: {scenario.ego_vehicle.speed} m/s")
    print(f"车辆数量: {len(scenario.vehicles)}")
    print(f"预期违规: {scenario.expected_violations}")
    
    # 验证场景
    validator = ScenarioValidator()
    result = validator.validate(scenario)
    
    print(f"\n验证结果:")
    print(f"  违规数量: {len(result.violations)}")
    print(f"  风险指数: {result.risk_index}")
    print(f"  风险等级: {result.risk_level}")
    print(f"  验证通过: {result.validation_passed}")
    
    # 显示违规详情
    print(f"\n检测到的违规:")
    for v in result.violations:
        print(f"  [{v.code}] {v.rule}: {v.message}")


def demo_all_preset_scenarios():
    """验证所有预设场景"""
    print("\n" + "=" * 60)
    print("验证所有预设场景")
    print("=" * 60)
    
    builder = ScenarioBuilder()
    validator = ScenarioValidator()
    
    # 获取所有预设场景
    presets = ScenarioPresets.get_preset_scenarios()
    
    for i, scenario in enumerate(presets, 1):
        scenario.timestamp = f"2026-08-24T21:00:{i*10:02d}.000000"
        result = validator.validate(scenario)
        
        status = "✅" if result.validation_passed else "❌"
        print(f"{status} 场景 {i}: {scenario.name}")
        print(f"   类型: {scenario.scenario_type.value}")
        print(f"   违规数: {len(result.violations)}")
        print(f"   风险等级: {result.risk_level}")
        
        for v in result.violations:
            print(f"     - [{v.code}] {v.rule}")
        print()


def demo_custom_scenario():
    """创建自定义场景"""
    print("=" * 60)
    print("自定义场景示例")
    print("=" * 60)
    
    from scenarios.builders import VehicleConfig, TrafficLightConfig, TrafficLightState
    
    builder = ScenarioBuilder()
    
    # 创建自定义场景
    ego = VehicleConfig(
        x=0, y=0, speed=15.0, yaw=0,
        vehicle_type="vehicle.ego", role="ego"
    )
    
    # 添加车辆
    vehicles = [
        VehicleConfig(x=20, y=0, speed=10.0, yaw=0, vehicle_type="vehicle.npc_0"),
        VehicleConfig(x=40, y=0, speed=12.0, yaw=0, vehicle_type="vehicle.npc_1"),
    ]
    
    # 添加交通灯
    traffic_lights = [
        TrafficLightConfig(x=15, y=0, state=TrafficLightState.RED),
    ]
    
    scenario = builder.create_custom_scenario(
        name="自定义场景",
        ego_config=ego,
        vehicle_configs=vehicles,
        traffic_light_configs=traffic_lights,
        description="自车超速接近红灯",
        expected_violations=["RSS_LONGITUDINAL", "TRAFFIC_LIGHT"]
    )
    
    # 验证
    validator = ScenarioValidator()
    result = validator.validate(scenario)
    
    print(f"场景: {scenario.name}")
    print(f"预期违规: {scenario.expected_violations}")
    print(f"检测违规: {result.detected_violations}")
    print(f"验证通过: {result.validation_passed}")


def demo_generate_reports():
    """生成验证报告"""
    print("\n" + "=" * 60)
    print("生成验证报告")
    print("=" * 60)
    
    builder = ScenarioBuilder()
    validator = ScenarioValidator()
    
    # 创建场景
    scenario = builder.create_red_light_scenario(
        ego_speed=15.0,
        distance_to_light=8.0
    )
    scenario.timestamp = "2026-08-24T22:00:00.000000"
    
    # 验证
    result = validator.validate(scenario)
    
    # 生成报告
    import os
    output_dir = "examples/rss_verification/output"
    os.makedirs(output_dir, exist_ok=True)
    
    report_path = f"{output_dir}/red_light_report.html"
    validator.generate_report(result, report_path)
    
    print(f"报告已生成: {report_path}")
    print(f"场景: {scenario.name}")
    print(f"违规数: {len(result.violations)}")
    print(f"风险等级: {result.risk_level}")


def main():
    """运行所有示例"""
    print("RSS 规则验证示例")
    print("=" * 60)
    
    # 基础用法
    demo_basic_usage()
    
    # 验证所有预设场景
    demo_all_preset_scenarios()
    
    # 自定义场景
    demo_custom_scenario()
    
    # 生成报告
    demo_generate_reports()
    
    print("=" * 60)
    print("所有示例运行完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()