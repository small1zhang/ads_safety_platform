"""
ads_safety_platform_kg.py - 集成知识图谱的自动驾驶安全平台
融合现有物理引擎与 kg_core 时空知识图谱架构
"""
import sys
import os
import math
import time
from typing import Dict, Any, List, Optional

# 添加 kg_core 到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ads_safety_platform.kg.extraction import ExtractionPipeline
from ads_safety_platform.kg.scenario import SnapshotBuilder
from ads_safety_platform.kg.behavior import RelationDebouncer
from ads_safety_platform.kg.rules import RuleEnforcer
from ads_safety_platform.kg.dynamic import IncrementalEngine
from ads_safety_platform.kg.storage import JSONSerializer
from ads_safety_platform.kg.explanation import ExplanationGenerator


class SafetyPlatformKG:
    """
    增强版自动驾驶安全平台
    融合物理引擎与知识图谱推理
    """
    
    def __init__(self, enable_kg: bool = True, 
                 enable_persistence: bool = False,
                 output_dir: str = "kg_output"):
        """
        初始化平台
        
        参数:
            enable_kg: 是否启用知识图谱增强
            enable_persistence: 是否启用持久化
            output_dir: 输出目录
        """
        self.enable_kg = enable_kg
        
        # 提取器
        self.extraction_pipeline = ExtractionPipeline()
        
        # 场景构建器
        self.snapshot_builder = SnapshotBuilder()
        
        # 行为层
        self.debouncer = RelationDebouncer()
        
        # 规则引擎
        self.rule_enforcer = RuleEnforcer()
        
        # 增量更新引擎
        self.incremental_engine = IncrementalEngine()
        
        # 存储器
        self.serializer = JSONSerializer(output_dir) if enable_persistence else None
        
        # 可解释性报告生成器
        self.report_generator = ExplanationGenerator()
        
        # 状态
        self.frame_count = 0
        self.enable_persistence = enable_persistence
        
        print(f"✅ SafetyPlatformKG 初始化完成")
        print(f"   - 知识图谱增强: {'启用' if enable_kg else '禁用'}")
        print(f"   - 持久化: {'启用' if enable_persistence else '禁用'}")
    
    def process_frame(self, raw_frame_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理单帧数据
        
        参数:
            raw_frame_data: 原始帧数据（来自 CARLA 或离线数据）
        
        返回:
            增强版结果字典
        """
        start_time = time.time()
        self.frame_count += 1
        
        result = {
            'frame_id': self.frame_count,
            'risk_level': 0,  # SAFE
            'risk_level_str': 'SAFE',
            'violations': [],
            'kg_enhanced': self.enable_kg,
        }
        
        if not self.enable_kg:
            # 仅使用物理引擎（兼容现有代码）
            return self._process_with_physics_only(raw_frame_data)
        
        # ========== Phase 1: 数据提取 ==========
        extracted_data = self.extraction_pipeline.process_frame(raw_frame_data)
        
        # ========== Phase 2: 场景快照构建 ==========
        snapshot = self.snapshot_builder.build_snapshot(extracted_data)
        
        # ========== Phase 3: 增量图更新 ==========
        delta = self.incremental_engine.process_frame(extracted_data)
        
        # ========== Phase 4: 规则引擎检查 ==========
        violations = self.rule_enforcer.enforce(snapshot)
        
        # ========== Phase 5: 可解释性报告 ==========
        if violations:
            report = self.report_generator.generate_report(
                snapshot=snapshot,
                violations=violations,
                frame_id=self.frame_count,
            )
            result['explanation_report'] = report
            result['risk_level'] = report.get('risk_level', 0)
            result['risk_level_str'] = report.get('risk_level_str', 'SAFE')
        
        result['violations'] = violations
        result['delta_summary'] = delta.summary()
        
        # ========== Phase 6: 持久化 ==========
        if self.enable_persistence and self.serializer:
            self.serializer.serialize_frame(extracted_data, self.frame_count)
            self.serializer.serialize_delta(delta, self.frame_count)
        
        elapsed = time.time() - start_time
        result['processing_time_ms'] = elapsed * 1000
        
        return result
    
    def _process_with_physics_only(self, raw_frame_data: Dict[str, Any]) -> Dict[str, Any]:
        """仅使用物理引擎处理（兼容模式）"""
        # 提取车辆信息
        vehicles = raw_frame_data.get('vehicles', [])
        traffic_lights = raw_frame_data.get('traffic_lights', [])
        
        violations = []
        
        # 简化的物理检查
        ego = next((v for v in vehicles if v.get('role_name') == 'ego'), None)
        if ego:
            # 检查闯红灯
            for tl in traffic_lights:
                if tl.get('state') == 'Red':
                    dx = tl.get('x', 0) - ego.get('x', 0)
                    dy = tl.get('y', 0) - ego.get('y', 0)
                    distance = math.sqrt(dx**2 + dy**2)
                    speed = math.sqrt(
                        ego.get('vx', 0)**2 + ego.get('vy', 0)**2
                    )
                    
                    if distance < 5.0 and speed > 2.0:
                        violations.append({
                            'rule_code': 'R2_RED_LIGHT',
                            'severity': 'CRITICAL',
                            'message': f'自车在红灯附近行驶',
                            'evidence': {'distance': distance, 'speed': speed},
                        })
        
        risk_level = 2 if violations else 0
        
        return {
            'frame_id': self.frame_count,
            'risk_level': risk_level,
            'risk_level_str': 'UNSAFE' if risk_level == 2 else 'SAFE',
            'violations': violations,
            'kg_enhanced': False,
        }
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            'total_frames': self.frame_count,
            'kg_enabled': self.enable_kg,
            'persistence_enabled': self.enable_persistence,
        }


def create_platform(enable_kg: bool = True, 
                    enable_persistence: bool = False) -> SafetyPlatformKG:
    """工厂函数：创建安全平台"""
    return SafetyPlatformKG(
        enable_kg=enable_kg,
        enable_persistence=enable_persistence,
    )


if __name__ == '__main__':
    # 演示使用
    print("=" * 60)
    print("自动驾驶安全平台 (KG增强版)")
    print("=" * 60)
    
    # 创建平台
    platform = create_platform(enable_kg=True, enable_persistence=True)
    
    # 模拟帧数据
    frame_data = {
        'vehicles': [
            {
                'entity_id': 'veh_1',
                'type_id': 'vehicle.tesla.model3',
                'role_name': 'ego',
                'location': {'x': 0, 'y': 0, 'z': 0},
                'velocity': {'x': 0.21, 'y': 5.28, 'z': 0},
                'transform': {'yaw': 90.0},
                'control': {'throttle': 0.5, 'brake': 0.0, 'steer': 0.0},
            },
            {
                'entity_id': 'veh_2',
                'type_id': 'vehicle.bmw.grandtourer',
                'role_name': 'npc',
                'location': {'x': 0.5, 'y': 10, 'z': 0},
                'velocity': {'x': 0.1, 'y': 8, 'z': 0},
                'transform': {'yaw': 90.0},
                'control': {'throttle': 0.3, 'brake': 0.0, 'steer': 0.0},
            },
        ],
        'traffic_lights': [
            {'entity_id': 'tl_1', 'location': {'x': 50, 'y': 50, 'z': 0.15}, 'state': 'Green'},
        ],
    }
    
    # 处理多帧
    for i in range(3):
        print(f"\n{'='*60}")
        print(f"处理第 {i+1} 帧")
        print('='*60)
        
        result = platform.process_frame(frame_data)
        
        print(f"帧ID: {result['frame_id']}")
        print(f"风险等级: {result['risk_level_str']}")
        print(f"违规数量: {len(result['violations'])}")
        print(f"处理时间: {result.get('processing_time_ms', 0):.2f}ms")
        
        if 'explanation_report' in result:
            report = result['explanation_report']
            print(f"自然语言描述: {report['natural_language'][:100]}...")
    
    # 打印统计
    print(f"\n{'='*60}")
    print("统计信息:")
    print(f"  总帧数: {platform.get_statistics()['total_frames']}")
    print(f"  KG增强: {platform.get_statistics()['kg_enabled']}")
    print(f"  持久化: {platform.get_statistics()['persistence_enabled']}")
    print('='*60)