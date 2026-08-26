#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简单CARLA实时检测脚本

功能:
1. 连接到CARLA仿真器
2. 运行30分钟实时检测
3. 实时显示检测进度
4. 生成检测报告
"""

import sys
import json
import time
import asyncio
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any
from dataclasses import dataclass, asdict
import traceback

# 添加路径
sys.path.insert(0, str(Path(__file__).parent / 'backend' / 'app'))

from ads_safety_platform.scenarios.carla_connector import CARLAClient, ScenarioExtractor
from ads_safety_platform.scenarios.scenario_validator import ScenarioValidator
from ads_safety_platform.scenarios.scenario_injector import (
    ScenarioBuilder, 
    ScenarioPresets
)


@dataclass
class AnomalyResult:
    """异常检测结果"""
    scenario_id: int
    scenario_name: str
    timestamp: str
    ego_x: float
    ego_y: float
    ego_speed: float
    vehicle_count: int
    violations: List[Dict]
    risk_index: float
    risk_level: str
    duration_ms: float


class SimpleCARLAIntegrationTester:
    """简化版CARLA集成测试器"""
    
    def __init__(self, host='localhost', port=2000, timeout=5.0):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.client = None
        self.validator = ScenarioValidator()
        self.results = []
        self.risk_distribution = {
            'CRITICAL': 0,
            'HIGH': 0,
            'MEDIUM': 0,
            'LOW': 0,
            'SAFE': 0
        }
        self.start_time = None
        self.total_collected = 0
        self.total_anomalies = 0
    
    def connect(self) -> bool:
        """连接CARLA"""
        print(f"[连接] 尝试连接到 CARLA {self.host}:{self.port}...")
        try:
            self.client = CARLAClient(self.host, self.port, self.timeout)
            if self.client.is_connected():
                print("[连接] ✅ CARLA连接成功！")
                return True
            else:
                print("[连接] ❌ CARLA连接失败")
                return False
        except Exception as e:
            print(f"[连接] ❌ 错误: {e}")
            return False
    
    def collect_current_scenario(self, scenario_id: int) -> AnomalyResult:
        """收集当前场景"""
        try:
            # 从CARLA提取当前场景
            if self.client and self.client.is_connected():
                extractor = ScenarioExtractor(self.client)
                scenario = extractor.extract_current_scene()
            else:
                # 使用模拟数据
                builder = ScenarioBuilder()
                scenario = builder.create_basic_scenario(
                    ego_speed=10.0 + (scenario_id % 10)
                )
            
            # 验证场景
            start = time.time()
            validation_result = self.validator.validate(scenario)
            duration_ms = (time.time() - start) * 1000
            
            # 构建结果
            ego = scenario.ego_vehicle
            violations = [v.to_dict() for v in validation_result.violations]
            
            result = AnomalyResult(
                scenario_id=scenario_id,
                scenario_name=scenario.name,
                timestamp=datetime.now().isoformat(),
                ego_x=ego.x,
                ego_y=ego.y,
                ego_speed=ego.speed,
                vehicle_count=len(scenario.vehicles),
                violations=violations,
                risk_index=validation_result.risk_index,
                risk_level=validation_result.risk_level,
                duration_ms=duration_ms
            )
            
            return result
            
        except Exception as e:
            print(f"[收集] ❌ 场景 {scenario_id} 失败: {e}")
            return None
    
    def run_integration_test(self, duration_seconds: int = 1800, 
                            interval: float = 2.0,
                            output_dir: str = './output_30min_carla_test'):
        """运行集成测试"""
        self.start_time = datetime.now()
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        print("\n" + "="*60)
        print("       🚗 CARLA实时检测 - 30分钟集成测试")
        print("="*60)
        print(f"开始时间: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"检测时长: {duration_seconds}秒 ({duration_seconds/60:.0f}分钟)")
        print(f"检测间隔: {interval}秒")
        print(f"输出目录: {output_path}")
        print("="*60 + "\n")
        
        scenario_id = 0
        last_print_time = time.time()
        
        # 主循环
        while True:
            elapsed = (datetime.now() - self.start_time).total_seconds()
            
            # 检查是否完成
            if elapsed >= duration_seconds:
                break
            
            # 收集场景
            result = self.collect_current_scenario(scenario_id)
            
            if result:
                self.results.append(result)
                self.total_collected += 1
                
                # 更新风险分布
                self.risk_distribution[result.risk_level] = \
                    self.risk_distribution.get(result.risk_level, 0) + 1
                
                # 如果有违规，增加异常计数
                if result.violations:
                    self.total_anomalies += 1
                
                # 每10秒打印一次进度
                current_time = time.time()
                if current_time - last_print_time >= 10:
                    self._print_progress(elapsed, duration_seconds)
                    last_print_time = current_time
            
            scenario_id += 1
            time.sleep(interval)
        
        # 结束
        self._generate_report(output_path)
        self._print_summary()
    
    def _print_progress(self, elapsed: float, total: float):
        """打印进度"""
        progress = (elapsed / total) * 100
        minutes_remaining = (total - elapsed) / 60
        detection_rate = self.total_anomalies / self.total_collected * 100 if self.total_collected > 0 else 0
        
        print(f"\r[进度] {progress:5.1f}% | "
              f"已运行 {elapsed/60:.1f}/{total/60:.0f}分钟 | "
              f"已检测 {self.total_collected}个场景 | "
              f"发现 {self.total_anomalies}个异常 ({detection_rate:.1f}%) | "
              f"剩余 {minutes_remaining:.1f}分钟", end='', flush=True)
    
    def _generate_report(self, output_path: Path):
        """生成报告"""
        report_file = output_path / 'integration_test_report.md'
        
        end_time = datetime.now()
        total_duration = (end_time - self.start_time).total_seconds()
        detection_rate = self.total_anomalies / self.total_collected * 100 if self.total_collected > 0 else 0
        
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write("# 🚗 CARLA集成测试报告\n\n")
            f.write(f"## 测试信息\n\n")
            f.write(f"- **测试类型**: 30分钟实时检测\n")
            f.write(f"- **开始时间**: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"- **结束时间**: {end_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"- **总时长**: {total_duration:.0f}秒 ({total_duration/60:.1f}分钟)\n")
            f.write(f"- **CARLA连接**: {'成功' if self.client and self.client.is_connected() else '失败'}\n\n")
            
            f.write(f"## 检测统计\n\n")
            f.write(f"- **总检测次数**: {self.total_collected}\n")
            f.write(f"- **总异常数**: {self.total_anomalies}\n")
            f.write(f"- **检出率**: {detection_rate:.2f}%\n")
            f.write(f"- **平均检测时长**: {sum(r.duration_ms for r in self.results)/len(self.results):.2f}ms\n\n")
            
            f.write(f"## 风险分布\n\n")
            for level, count in self.risk_distribution.items():
                percentage = count / self.total_collected * 100 if self.total_collected > 0 else 0
                f.write(f"- **{level}**: {count} ({percentage:.1f}%)\n")
            
            f.write(f"\n## 异常样例\n\n")
            for i, result in enumerate(self.results[:10]):
                if result.violations:
                    f.write(f"### {i+1}. {result.scenario_name}\n\n")
                    f.write(f"- 时间: {result.timestamp}\n")
                    f.write(f"- 风险等级: {result.risk_level}\n")
                    f.write(f"- 风险指数: {result.risk_index:.3f}\n")
                    f.write(f"- 违规数: {len(result.violations)}\n")
                    for v in result.violations[:3]:
                        f.write(f"  - {v.get('message', 'Unknown')}\n")
                    f.write("\n")
        
        # 保存JSON结果
        results_file = output_path / 'results.json'
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump({
                'start_time': self.start_time.isoformat(),
                'end_time': end_time.isoformat(),
                'total_duration': total_duration,
                'total_collected': self.total_collected,
                'total_anomalies': self.total_anomalies,
                'detection_rate': detection_rate,
                'risk_distribution': self.risk_distribution,
                'results': [asdict(r) for r in self.results]
            }, f, indent=2, ensure_ascii=False)
        
        print(f"\n\n报告已保存: {report_file}")
        print(f"JSON结果已保存: {results_file}")
    
    def _print_summary(self):
        """打印总结"""
        end_time = datetime.now()
        total_duration = (end_time - self.start_time).total_seconds()
        detection_rate = self.total_anomalies / self.total_collected * 100 if self.total_collected > 0 else 0
        
        print("\n" + "="*60)
        print("                  检测完成总结")
        print("="*60)
        print(f"✅ 总检测次数: {self.total_collected}")
        print(f"✅ 总异常数: {self.total_anomalies}")
        print(f"✅ 检出率: {detection_rate:.2f}%")
        print(f"✅ 平均检测时长: {sum(r.duration_ms for r in self.results)/len(self.results):.2f}ms")
        print(f"✅ 总运行时长: {total_duration:.0f}秒 ({total_duration/60:.1f}分钟)")
        print("\n风险分布:")
        for level, count in sorted(self.risk_distribution.items()):
            percentage = count / self.total_collected * 100 if self.total_collected > 0 else 0
            print(f"  {level:10s}: {count:4d} ({percentage:5.1f}%)")
        print("="*60)


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='CARLA实时检测')
    parser.add_argument('--duration', type=int, default=1800, 
                       help='检测时长(秒), 默认1800秒(30分钟)')
    parser.add_argument('--interval', type=float, default=2.0,
                       help='检测间隔(秒), 默认2秒')
    parser.add_argument('--host', type=str, default='localhost',
                       help='CARLA主机地址')
    parser.add_argument('--port', type=int, default=2000,
                       help='CARLA端口')
    parser.add_argument('--output', type=str, default='./output_30min_carla_test',
                       help='输出目录')
    
    args = parser.parse_args()
    
    # 创建测试器
    tester = SimpleCARLAIntegrationTester(host=args.host, port=args.port)
    
    # 连接CARLA
    if not tester.connect():
        print("\n⚠️ CARLA连接失败，将使用模拟数据模式继续测试...")
    
    # 运行测试
    tester.run_integration_test(
        duration_seconds=args.duration,
        interval=args.interval,
        output_dir=args.output
    )


if __name__ == '__main__':
    main()
