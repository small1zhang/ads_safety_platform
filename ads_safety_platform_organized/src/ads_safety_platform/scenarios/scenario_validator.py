#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scenario_validator.py - 场景验证器

功能：
1. 加载场景数据
2. 使用RSS规则进行验证
3. 生成验证报告
4. 对比预期违规和实际检测结果

用法：
    from ads_safety_platform.scenarios.scenario_injector import Scenario, ScenarioBuilder
    from ads_safety_platform.scenarios.scenario_validator import ScenarioValidator
    
    # 创建场景
    builder = ScenarioBuilder()
    scenario = builder.create_red_light_scenario()
    
    # 验证场景
    validator = ScenarioValidator()
    result = validator.validate(scenario)
    
    # 生成报告
    validator.generate_report(result, "report.html")
"""

import math
import json
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from datetime import datetime

# 添加项目路径
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from ads_safety_platform.scenarios.scenario_injector import (
    Scenario, VehicleConfig, TrafficLightConfig, PedestrianConfig, 
    ScenarioType, TrafficLightState
)

# 导入 RSS 规则模块
from ads_safety_platform.kg.rules.rss.longitudinal import (
    LongitudinalRSSModel, RSSLongitudinalParams
)
from ads_safety_platform.kg.rules.rss.lateral import (
    LateralRSSModel, RSSLateralParams
)
from ads_safety_platform.kg.rules.rss.intersection import (
    VehicleState, check_right_of_way_by_position, RCPPParams, IntersectionType
)
from ads_safety_platform.kg.rules.rss.risk_index import (
    RiskAssessmentModel, RiskParams, compute_risk_index
)


@dataclass
class Violation:
    """违规信息"""
    rule: str
    code: str
    level: str  # 'high', 'medium', 'low'
    message: str
    entities: List[str]
    details: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'rule': self.rule,
            'code': self.code,
            'level': self.level,
            'message': self.message,
            'entities': self.entities,
            'details': self.details
        }


@dataclass
class ValidationResult:
    """验证结果"""
    scenario_name: str
    scenario_type: str
    timestamp: str
    violations: List[Violation] = field(default_factory=list)
    risk_index: float = 0.0
    risk_level: str = "LOW"
    expected_violations: List[str] = field(default_factory=list)
    detected_violations: List[str] = field(default_factory=list)
    validation_passed: bool = True
    execution_time_ms: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'scenario_name': self.scenario_name,
            'scenario_type': self.scenario_type,
            'timestamp': self.timestamp,
            'violations': [v.to_dict() for v in self.violations],
            'risk_index': self.risk_index,
            'risk_level': self.risk_level,
            'expected_violations': self.expected_violations,
            'detected_violations': self.detected_violations,
            'validation_passed': self.validation_passed,
            'execution_time_ms': self.execution_time_ms
        }


class ScenarioValidator:
    """场景验证器"""
    
    def __init__(self):
        # 初始化 RSS 模型
        self.longitudinal_model = LongitudinalRSSModel(RSSLongitudinalParams())
        self.lateral_model = LateralRSSModel(RSSLateralParams())
        self.risk_model = RiskAssessmentModel(RiskParams())
        self.rcpp_params = RCPPParams()
    
    def validate(self, scenario: Scenario) -> ValidationResult:
        """验证场景"""
        import time
        start_time = time.time()
        
        result = ValidationResult(
            scenario_name=scenario.name,
            scenario_type=scenario.scenario_type.value,
            timestamp=datetime.now().isoformat(),
            expected_violations=scenario.expected_violations
        )
        
        # 转换自车数据
        ego = scenario.ego_vehicle
        ego_state = VehicleState(
            x=ego.x, y=ego.y, vx=ego.speed * math.cos(ego.yaw),
            vy=ego.speed * math.sin(ego.yaw), length=ego.length, width=ego.width
        )
        
        # 检查纵向安全
        long_violations = self._check_longitudinal_safety(ego, scenario.vehicles)
        result.violations.extend(long_violations)
        result.detected_violations.extend([v.rule for v in long_violations])
        
        # 检查横向安全
        lat_violations = self._check_lateral_safety(ego, scenario.vehicles)
        result.violations.extend(lat_violations)
        result.detected_violations.extend([v.rule for v in lat_violations])
        
        # 检查交通灯
        light_violations = self._check_traffic_lights(ego, scenario.traffic_lights)
        result.violations.extend(light_violations)
        result.detected_violations.extend([v.rule for v in light_violations])
        
        # 检查行人
        ped_violations = self._check_pedestrians(ego, scenario.pedestrians)
        result.violations.extend(ped_violations)
        result.detected_violations.extend([v.rule for v in ped_violations])
        
        # 检查交叉口
        if scenario.scenario_type == ScenarioType.INTERSECTION:
            intersection_violations = self._check_intersection(ego, scenario.vehicles)
            result.violations.extend(intersection_violations)
            result.detected_violations.extend([v.rule for v in intersection_violations])
        
        # 计算风险指数
        result.risk_index, result.risk_level = self._compute_risk_index(result.violations)
        
        # 检查验证是否通过
        result.validation_passed = self._check_validation_passed(
            result.expected_violations, result.detected_violations
        )
        
        result.execution_time_ms = (time.time() - start_time) * 1000
        
        return result
    
    def _check_longitudinal_safety(
        self, ego: VehicleConfig, vehicles: List[VehicleConfig]
    ) -> List[Violation]:
        """检查纵向安全规则"""
        violations = []
        
        ego_speed = ego.speed
        ego_x, ego_y = ego.x, ego.y
        
        for vehicle in vehicles:
            dx = vehicle.x - ego_x
            dy = vehicle.y - ego_y
            distance = math.sqrt(dx**2 + dy**2)
            
            # 只检查前方车辆（在自车前方且距离小于100米）
            if distance > 0 and distance < 100:
                # 计算相对角度
                angle = math.atan2(dy, dx)
                relative_angle = abs(angle - ego.yaw)
                
                # 如果车辆在自车前方（角度差小于90度）
                if abs(relative_angle) < math.pi/2:
                    other_speed = vehicle.speed
                    result = self.longitudinal_model.check_safe_distance(
                        ego_speed, other_speed, distance
                    )
                    
                    if not result.get('safe', True):
                        level = 'high' if result.get('margin', 0) < -5 else 'medium'
                        violations.append(Violation(
                            rule='RSS_LONGITUDINAL',
                            code='RSS-001',
                            level=level,
                            message=f'与车辆距离 {distance:.1f}m 低于最小安全距离 {result.get("d_min", 0):.1f}m',
                            entities=['ego', vehicle.vehicle_type],
                            details={
                                'd_min': result.get('d_min', 0),
                                'd_actual': distance,
                                'margin': result.get('margin', 0),
                                'ego_speed': ego_speed,
                                'other_speed': other_speed
                            }
                        ))
        
        return violations
    
    def _check_lateral_safety(
        self, ego: VehicleConfig, vehicles: List[VehicleConfig]
    ) -> List[Violation]:
        """检查横向安全规则"""
        violations = []
        
        ego_speed = ego.speed
        ego_x, ego_y = ego.x, ego.y
        
        for vehicle in vehicles:
            dx = vehicle.x - ego_x
            dy = vehicle.y - ego_y
            lateral_distance = abs(dy)  # 简化：假设y是横向距离
            
            # 检查横向安全距离
            if lateral_distance < 5.0:  # 5米内
                result = self.lateral_model.check_safe_lateral_distance(
                    ego_speed, vehicle.speed, lateral_distance
                )
                
                if not result.get('safe', True):
                    violations.append(Violation(
                        rule='RSS_LATERAL',
                        code='RSS-002',
                        level='high',
                        message=f'与车辆横向距离 {lateral_distance:.1f}m 低于安全距离',
                        entities=['ego', vehicle.vehicle_type],
                        details={
                            'lateral_distance': lateral_distance,
                            'ego_speed': ego_speed,
                            'other_speed': vehicle.speed
                        }
                    ))
        
        return violations
    
    def _check_traffic_lights(
        self, ego: VehicleConfig, traffic_lights: List[TrafficLightConfig]
    ) -> List[Violation]:
        """检查交通灯规则"""
        violations = []
        
        ego_x, ego_y = ego.x, ego.y
        
        for light in traffic_lights:
            if light.state == TrafficLightState.RED:
                dx = light.x - ego_x
                dy = light.y - ego_y
                distance = math.sqrt(dx**2 + dy**2)
                
                # 如果红灯在前方且距离小于15米
                if distance < 15:
                    violations.append(Violation(
                        rule='TRAFFIC_LIGHT',
                        code='R1-001',
                        level='high',
                        message=f'红灯未停车，距离 {distance:.1f}m',
                        entities=['ego', f'traffic_light_{light.x}_{light.y}'],
                        details={'distance': distance}
                    ))
        
        return violations
    
    def _check_pedestrians(
        self, ego: VehicleConfig, pedestrians: List[PedestrianConfig]
    ) -> List[Violation]:
        """检查行人安全规则"""
        violations = []
        
        ego_x, ego_y = ego.x, ego.y
        ego_speed = ego.speed
        
        for ped in pedestrians:
            dx = ped.x - ego_x
            dy = ped.y - ego_y
            distance = math.sqrt(dx**2 + dy**2)
            
            # 如果行人在前方且距离小于10米
            if distance < 10:
                # 计算相对速度
                relative_speed = ego_speed - ped.speed
                ttc = distance / relative_speed if relative_speed > 0 else float('inf')
                
                if ttc < 2.0:  # 2秒内可能碰撞
                    violations.append(Violation(
                        rule='PEDESTRIAN_SAFETY',
                        code='R2-001',
                        level='high',
                        message=f'行人距离 {distance:.1f}m，TTC {ttc:.1f}s',
                        entities=['ego', f'pedestrian_{ped.x}_{ped.y}'],
                        details={'distance': distance, 'ttc': ttc}
                    ))
        
        return violations
    
    def _check_intersection(
        self, ego: VehicleConfig, vehicles: List[VehicleConfig]
    ) -> List[Violation]:
        """检查交叉口规则"""
        violations = []
        
        ego_state = VehicleState(
            x=ego.x, y=ego.y, vx=ego.speed * math.cos(ego.yaw),
            vy=ego.speed * math.sin(ego.yaw), length=ego.length, width=ego.width
        )
        
        for vehicle in vehicles:
            other_state = VehicleState(
                x=vehicle.x, y=vehicle.y,
                vx=vehicle.speed * math.cos(vehicle.yaw),
                vy=vehicle.speed * math.sin(vehicle.yaw),
                length=vehicle.length, width=vehicle.width
            )
            
            # 检查右侧优先
            result = check_right_of_way_by_position(
                ego_state, other_state
            )
            
            if not result.get('has_right_of_way', True):
                violations.append(Violation(
                    rule='RIGHT_OF_WAY',
                    code='R3-001',
                    level='high',
                    message=f'右侧车辆有优先通行权，自车应让行',
                    entities=['ego', vehicle.vehicle_type],
                    details={'relative_position': result.get('relative_position', '')}
                ))
        
        return violations
    
    def _compute_risk_index(self, violations: List[Violation]) -> Tuple[float, str]:
        """计算风险指数"""
        if not violations:
            return 0.1, "LOW"
        
        high_count = sum(1 for v in violations if v.level == 'high')
        medium_count = sum(1 for v in violations if v.level == 'medium')
        
        risk_index = min(1.0, 0.3 + high_count * 0.2 + medium_count * 0.1)
        
        if risk_index >= 0.8:
            level = "CRITICAL"
        elif risk_index >= 0.6:
            level = "HIGH"
        elif risk_index >= 0.3:
            level = "MEDIUM"
        else:
            level = "LOW"
        
        return round(risk_index, 3), level
    
    def _check_validation_passed(
        self, expected: List[str], detected: List[str]
    ) -> bool:
        """检查验证是否通过"""
        # 如果没有预期违规，但检测到了违规，验证不通过
        if not expected and detected:
            return False
        
        # 如果有预期违规，但没有检测到，验证不通过
        if expected and not detected:
            return False
        
        # 检查预期违规是否都被检测到
        for exp in expected:
            if exp not in detected:
                return False
        
        return True
    
    def generate_report(self, result: ValidationResult, output_path: str) -> None:
        """生成验证报告HTML"""
        violations_html = ""
        for v in result.violations:
            violations_html += f'''
            <div class="violation {v.level}">
                <strong>[{v.code}] {v.rule}</strong><br>
                {v.message}<br>
                <small>实体: {', '.join(v.entities)}</small>
                <pre>{json.dumps(v.details, indent=2, ensure_ascii=False)}</pre>
            </div>
            '''
        
        expected_html = ""
        for exp in result.expected_violations:
            status = "✅" if exp in result.detected_violations else "❌"
            expected_html += f'<li>{status} {exp}</li>'
        
        detected_html = ""
        for det in result.detected_violations:
            status = "✅" if det in result.expected_violations else "⚠️"
            detected_html += f'<li>{status} {det}</li>'
        
        risk_class = result.risk_level.lower()
        validation_class = "pass" if result.validation_passed else "fail"
        
        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>场景验证报告 - {result.scenario_name}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #1a1a2e;
            color: #e0e0e0;
            padding: 20px;
            line-height: 1.6;
        }}
        .header {{
            background: rgba(0,0,0,0.3);
            padding: 20px;
            margin-bottom: 20px;
            border-radius: 10px;
            border-left: 4px solid #667eea;
        }}
        .section {{
            background: rgba(255,255,255,0.05);
            padding: 15px;
            margin: 15px 0;
            border-radius: 8px;
        }}
        .violation {{
            background: rgba(255,255,255,0.05);
            padding: 15px;
            margin: 10px 0;
            border-radius: 5px;
        }}
        .high {{ border-left: 4px solid #ff6b6b; }}
        .medium {{ border-left: 4px solid #ffd93d; }}
        .low {{ border-left: 4px solid #6bcb77; }}
        .badge-critical {{ background: #ff6b6b; color: white; padding: 5px 15px; border-radius: 5px; }}
        .badge-high {{ background: #ff9f43; color: white; padding: 5px 15px; border-radius: 5px; }}
        .badge-medium {{ background: #ffd93d; color: black; padding: 5px 15px; border-radius: 5px; }}
        .badge-low {{ background: #6bcb77; color: white; padding: 5px 15px; border-radius: 5px; }}
        .pass {{ color: #6bcb77; }}
        .fail {{ color: #ff6b6b; }}
        pre {{
            background: rgba(255,255,255,0.1);
            padding: 10px;
            border-radius: 5px;
            overflow-x: auto;
            margin-top: 10px;
        }}
        ul {{
            list-style: none;
            padding: 0;
        }}
        li {{
            padding: 5px 0;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🚗 场景验证报告</h1>
        <h2>{result.scenario_name}</h2>
        <p><strong>场景类型:</strong> {result.scenario_type}</p>
        <p><strong>时间戳:</strong> {result.timestamp}</p>
        <p><strong>执行时间:</strong> {result.execution_time_ms:.2f}ms</p>
    </div>
    
    <div class="section">
        <h2>📊 风险评估</h2>
        <p>风险指数: <span class="badge-{risk_class}">{result.risk_index} - {result.risk_level}</span></p>
        <p>验证结果: <span class="{validation_class}">{'✅ 通过' if result.validation_passed else '❌ 未通过'}</span></p>
    </div>
    
    <div class="section">
        <h2>⚠️ 检测到的违规 ({len(result.violations)} 个)</h2>
        {violations_html if violations_html else '<p>未检测到违规</p>'}
    </div>
    
    <div class="section">
        <h2>🎯 预期违规 vs 检测违规</h2>
        <h3>预期违规:</h3>
        <ul>{expected_html if expected_html else '<li>无预期违规</li>'}</ul>
        <h3>检测违规:</h3>
        <ul>{detected_html if detected_html else '<li>无检测违规</li>'}</ul>
    </div>
    
    <div class="section">
        <h2>📝 原始数据</h2>
        <pre>{json.dumps(result.to_dict(), indent=2, ensure_ascii=False)}</pre>
    </div>
</body>
</html>"""
        
        with open(output_path, 'w') as f:
            f.write(html)


if __name__ == "__main__":
    # 示例：验证所有预设场景
    from ads_safety_platform.scenarios.scenario_injector import ScenarioBuilder, ScenarioPresets
    
    builder = ScenarioBuilder()
    validator = ScenarioValidator()
    
    # 获取预设场景
    presets = ScenarioPresets.get_preset_scenarios()
    
    # 验证每个场景
    import os
    output_dir = "scenarios/data/reports"
    os.makedirs(output_dir, exist_ok=True)
    
    print("验证预设场景...")
    print("=" * 60)
    
    for i, scenario in enumerate(presets):
        scenario.timestamp = f"2026-08-24T20:00:{i*10:02d}.000000"
        
        result = validator.validate(scenario)
        
        # 保存报告
        report_path = f"{output_dir}/report_{i+1:02d}.html"
        validator.generate_report(result, report_path)
        
        status = "✅" if result.validation_passed else "❌"
        print(f"{status} 场景 {i+1}: {scenario.name}")
        print(f"   违规数: {len(result.violations)}")
        print(f"   风险等级: {result.risk_level}")
        print(f"   报告: {report_path}")
        print()
    
    print(f"已生成 {len(presets)} 个场景验证报告到 {output_dir}/")