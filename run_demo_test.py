#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CARLA实时检测演示脚本 (演示模式)

当CARLA中没有车辆时，使用模拟数据展示检测效果
"""

import sys
import json
import time
import random
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict

sys.path.insert(0, str(Path(__file__).parent / 'backend' / 'app'))

from ads_safety_platform.scenarios.scenario_validator import ScenarioValidator
from ads_safety_platform.scenarios.scenario_injector import ScenarioBuilder


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
    violations: list
    risk_index: float
    risk_level: str
    duration_ms: float


class CARLADemoTester:
    """CARLA演示测试器"""
    
    def __init__(self):
        self.validator = ScenarioValidator()
        self.results = []
        self.risk_distribution = {
            'CRITICAL': 0, 'HIGH': 0, 'MEDIUM': 0, 'LOW': 0, 'SAFE': 0
        }
        self.start_time = None
        self.total_collected = 0
        self.total_anomalies = 0
    
    def create_demo_scenario(self, scenario_id: int):
        """创建演示场景"""
        builder = ScenarioBuilder()
        
        # 随机选择场景类型
        scenario_types = [
            ('直行道路', self._create_straight_road),
            ('交叉口', self._create_intersection),
            ('合流', self._create_merge),
            ('车道变换', self._create_lane_change),
            ('红灯', self._create_red_light),
            ('行人', self._create_pedestrian),
        ]
        
        # 根据ID选择场景类型，模拟真实分布
        weights = [0.18, 0.15, 0.15, 0.12, 0.20, 0.20]
        scenario_type = random.choices(
            [s[0] for s in scenario_types],
            weights=weights
        )[0]
        
        for name, creator in scenario_types:
            if name == scenario_type:
                return creator(scenario_id, builder)
        
        return self._create_straight_road(scenario_id, builder)
    
    def _create_straight_road(self, sid: int, builder: ScenarioBuilder):
        """创建直行道路场景"""
        ego_speed = 15.0 + random.uniform(0, 10)
        scenario = builder.create_straight_road_scenario(
            ego_speed=ego_speed,
            num_vehicles=3
        )
        scenario.name = f"直行道路场景_{sid}"
        return scenario
    
    def _create_intersection(self, sid: int, builder: ScenarioBuilder):
        """创建交叉口场景"""
        ego_speed = 12.0 + random.uniform(0, 8)
        scenario = builder.create_intersection_scenario(
            ego_speed=ego_speed,
            distance_to_intersection=15.0
        )
        scenario.name = f"交叉口场景_{sid}"
        return scenario
    
    def _create_merge(self, sid: int, builder: ScenarioBuilder):
        """创建合流场景"""
        ego_speed = 12.0 + random.uniform(0, 6)
        scenario = builder.create_merge_scenario(
            ego_speed=ego_speed,
            merge_distance=20.0
        )
        scenario.name = f"合流场景_{sid}"
        return scenario
    
    def _create_lane_change(self, sid: int, builder: ScenarioBuilder):
        """创建车道变换场景"""
        ego_speed = 14.0 + random.uniform(0, 6)
        scenario = builder.create_lane_change_scenario(
            ego_speed=ego_speed
        )
        scenario.name = f"车道变换场景_{sid}"
        return scenario
    
    def _create_red_light(self, sid: int, builder: ScenarioBuilder):
        """创建红灯违规场景"""
        ego_speed = 18.0 + random.uniform(0, 8)
        scenario = builder.create_red_light_scenario(
            ego_speed=ego_speed,
            distance_to_light=8.0
        )
        scenario.name = f"红灯违规场景_{sid}"
        return scenario
    
    def _create_pedestrian(self, sid: int, builder: ScenarioBuilder):
        """创建行人横穿场景"""
        ego_speed = 10.0 + random.uniform(0, 6)
        scenario = builder.create_pedestrian_crossing_scenario(
            ego_speed=ego_speed,
            distance_to_crossing=6.0
        )
        scenario.name = f"行人横穿场景_{sid}"
        return scenario
    
    def run_demo(self, duration_seconds: int = 1800,
                interval: float = 2.0,
                output_dir: str = './output_30min_demo'):
        """运行演示测试"""
        self.start_time = datetime.now()
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        print("\n" + "="*65)
        print("      🚗 CARLA异常检测框架演示 - 30分钟实时检测")
        print("="*65)
        print(f"开始时间: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"检测时长: {duration_seconds}秒 ({duration_seconds/60:.0f}分钟)")
        print(f"检测间隔: {interval}秒")
        print(f"输出目录: {output_path}")
        print("="*65 + "\n")
        
        scenario_id = 0
        last_print_time = time.time()
        print("开始检测...\n")
        
        while True:
            elapsed = (datetime.now() - self.start_time).total_seconds()
            
            if elapsed >= duration_seconds:
                break
            
            # 创建演示场景
            scenario = self.create_demo_scenario(scenario_id)
            
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
            
            self.results.append(result)
            self.total_collected += 1
            self.risk_distribution[result.risk_level] = \
                self.risk_distribution.get(result.risk_level, 0) + 1
            
            if result.violations:
                self.total_anomalies += 1
            
            # 每10秒打印进度
            current_time = time.time()
            if current_time - last_print_time >= 10:
                self._print_progress(elapsed, duration_seconds)
                last_print_time = current_time
            
            scenario_id += 1
            time.sleep(interval)
        
        # 生成报告
        self._generate_report(output_path)
        self._print_summary()
    
    def _print_progress(self, elapsed: float, total: float):
        """打印进度"""
        progress = (elapsed / total) * 100
        minutes_remaining = (total - elapsed) / 60
        detection_rate = self.total_anomalies / self.total_collected * 100 if self.total_collected > 0 else 0
        
        bar_length = 30
        filled = int(bar_length * elapsed / total)
        bar = '█' * filled + '░' * (bar_length - filled)
        
        print(f"\r[{bar}] {progress:5.1f}% | "
              f"已运行 {elapsed/60:.1f}/{total/60:.0f}分钟 | "
              f"已检测 {self.total_collected}个 | "
              f"发现 {self.total_anomalies}个异常 ({detection_rate:.1f}%)", end='', flush=True)
    
    def _generate_report(self, output_path: Path):
        """生成报告"""
        report_file = output_path / 'demo_test_report.md'
        end_time = datetime.now()
        total_duration = (end_time - self.start_time).total_seconds()
        detection_rate = self.total_anomalies / self.total_collected * 100 if self.total_collected > 0 else 0
        
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write("# 🚗 CARLA异常检测框架演示报告\n\n")
            f.write("## 测试信息\n\n")
            f.write(f"- **测试模式**: 演示模式 (模拟数据)\n")
            f.write(f"- **开始时间**: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"- **结束时间**: {end_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"- **总时长**: {total_duration:.0f}秒 ({total_duration/60:.1f}分钟)\n")
            f.write(f"- **检测频率**: 每2秒一次\n\n")
            
            f.write("## 检测统计\n\n")
            f.write(f"- **总检测次数**: {self.total_collected}\n")
            f.write(f"- **总异常数**: {self.total_anomalies}\n")
            f.write(f"- **检出率**: {detection_rate:.2f}%\n")
            
            if self.results:
                avg_duration = sum(r.duration_ms for r in self.results) / len(self.results)
                f.write(f"- **平均检测时长**: {avg_duration:.2f}ms\n\n")
            else:
                f.write("\n")
            
            f.write("## 风险分布\n\n")
            for level, count in sorted(self.risk_distribution.items()):
                percentage = count / self.total_collected * 100 if self.total_collected > 0 else 0
                f.write(f"- **{level}**: {count} ({percentage:.1f}%)\n")
            
            f.write("\n## 异常样例\n\n")
            anomaly_results = [r for r in self.results if r.violations][:10]
            for i, result in enumerate(anomaly_results):
                f.write(f"### {i+1}. {result.scenario_name}\n\n")
                f.write(f"- 时间: {result.timestamp}\n")
                f.write(f"- 风险等级: {result.risk_level}\n")
                f.write(f"- 风险指数: {result.risk_index:.3f}\n")
                f.write(f"- 违规数: {len(result.violations)}\n")
                for v in result.violations[:3]:
                    f.write(f"  - {v.get('message', 'Unknown')}\n")
                f.write("\n")
        
        # 保存JSON
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
        
        print("\n" + "="*65)
        print("                    检测完成总结")
        print("="*65)
        print(f"✅ 总检测次数: {self.total_collected}")
        print(f"✅ 总异常数: {self.total_anomalies}")
        print(f"✅ 检出率: {detection_rate:.2f}%")
        
        if self.results:
            avg_duration = sum(r.duration_ms for r in self.results) / len(self.results)
            print(f"✅ 平均检测时长: {avg_duration:.2f}ms")
        
        print(f"✅ 总运行时长: {total_duration:.0f}秒 ({total_duration/60:.1f}分钟)")
        print("\n风险分布:")
        for level, count in sorted(self.risk_distribution.items()):
            percentage = count / self.total_collected * 100 if self.total_collected > 0 else 0
            print(f"  {level:10s}: {count:4d} ({percentage:5.1f}%)")
        print("="*65)


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='CARLA异常检测演示')
    parser.add_argument('--duration', type=int, default=1800, 
                       help='检测时长(秒), 默认1800秒(30分钟)')
    parser.add_argument('--interval', type=float, default=2.0,
                       help='检测间隔(秒), 默认2秒')
    parser.add_argument('--output', type=str, default='./output_30min_demo',
                       help='输出目录')
    
    args = parser.parse_args()
    
    tester = CARLADemoTester()
    tester.run_demo(
        duration_seconds=args.duration,
        interval=args.interval,
        output_dir=args.output
    )


if __name__ == '__main__':
    main()
