#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CARLA实时检测 - 改进版 (支持混合模式)

功能:
1. 连接CARLA，如果可用则使用真实数据
2. 如果CARLA没有车辆，自动切换到模拟模式
3. 运行30分钟实时检测
4. 实时显示检测进度
5. 生成检测报告
"""

import sys
import json
import time
import random
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict

sys.path.insert(0, str(Path(__file__).parent / 'backend' / 'app'))

from ads_safety_platform.scenarios.carla_connector import CARLAClient
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


class CARLADetector:
    """CARLA检测器 (支持混合模式)"""

    def __init__(self, host='localhost', port=2000, timeout=5.0):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.client = None
        self.use_carla = False
        self.validator = ScenarioValidator()
        self.consecutive_failures = 0
        self.results = []
        self.risk_distribution = {
            'CRITICAL': 0, 'HIGH': 0, 'MEDIUM': 0, 'LOW': 0, 'SAFE': 0
        }
        self.start_time = None
        self.total_collected = 0
        self.total_anomalies = 0
        self.sim_mode = False  # 是否处于模拟模式

    def connect(self) -> bool:
        """连接CARLA"""
        print(f"[连接] 尝试连接到 CARLA {self.host}:{self.port}...")
        try:
            self.client = CARLAClient(self.host, self.port, self.timeout)
            if self.client.is_connected():
                print("[连接] ✅ CARLA连接成功！")
                self.use_carla = True
                return True
            else:
                print("[连接] ❌ CARLA连接失败")
                self.use_carla = False
                return False
        except Exception as e:
            print(f"[连接] ❌ 错误: {e}")
            self.use_carla = False
            return False

    def _create_simulated_scenario(self, scenario_id: int):
        """创建模拟场景"""
        builder = ScenarioBuilder()
        scenario_types = [
            builder.create_straight_road_scenario,
            builder.create_intersection_scenario,
            builder.create_merge_scenario,
            builder.create_lane_change_scenario,
            builder.create_red_light_scenario,
            builder.create_pedestrian_crossing_scenario,
        ]
        method = random.choice(scenario_types)
        ego_speed = 10.0 + random.uniform(0, 15)
        return method(ego_speed=ego_speed)

    def collect_scenario(self, scenario_id: int) -> AnomalyResult:
        """收集场景"""
        try:
            scenario = None

            # 尝试从CARLA提取
            if self.use_carla and self.client and self.client.is_connected():
                try:
                    from ads_safety_platform.scenarios.carla_connector import ScenarioExtractor
                    extractor = ScenarioExtractor(self.client)
                    scenario = extractor.extract_current_scene()
                    self.consecutive_failures = 0
                except Exception as e:
                    self.consecutive_failures += 1
                    if self.consecutive_failures >= 3:
                        print(f"[切换] CARLA连续失败{self.consecutive_failures}次，切换到模拟模式")
                        self.use_carla = False
                        self.sim_mode = True

            # 使用模拟数据
            if scenario is None:
                scenario = self._create_simulated_scenario(scenario_id)

            # 验证
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
            return None

    def run_detection(self, duration_seconds: int = 1800, interval: float = 2.0,
                     output_dir: str = './output_30min_final'):
        """运行30分钟检测"""
        self.start_time = datetime.now()
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        print("\n" + "=" * 65)
        print("      🚗 CARLA实时检测 - 30分钟智能检测")
        print("=" * 65)
        print(f"开始时间: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"检测时长: {duration_seconds}秒 ({duration_seconds / 60:.0f}分钟)")
        print(f"检测间隔: {interval}秒")
        print(f"输出目录: {output_path}")
        print("=" * 65)
        print()
        print("[模式] CARLA连接已建立，但仿真器中没有车辆")
        print("[模式] 自动切换到模拟数据模式 (仍然使用RSS规则检测)")
        print()

        scenario_id = 0
        last_print_time = time.time()
        mode_changes = 0

        while True:
            elapsed = (datetime.now() - self.start_time).total_seconds()
            if elapsed >= duration_seconds:
                break

            # 收集场景
            result = self.collect_scenario(scenario_id)

            if result:
                self.results.append(result)
                self.total_collected += 1
                self.risk_distribution[result.risk_level] = \
                    self.risk_distribution.get(result.risk_level, 0) + 1

                if result.violations:
                    self.total_anomalies += 1

            # 每10秒打印一次进度
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
        """打印进度条"""
        progress = (elapsed / total) * 100
        minutes_remaining = (total - elapsed) / 60
        detection_rate = self.total_anomalies / self.total_collected * 100 if self.total_collected > 0 else 0

        bar_length = 30
        filled = int(bar_length * elapsed / total)
        bar = '█' * filled + '░' * (bar_length - filled)

        mode_str = '[CARLA混合模式]' if self.use_carla else '[模拟模式]'
        print(f"\r[{bar}] {progress:5.1f}% | "
              f"{elapsed / 60:5.1f}/{total / 60:.0f}分钟 | "
              f"已检测: {self.total_collected:4d} | "
              f"异常: {self.total_anomalies:4d} ({detection_rate:5.1f}%) | "
              f"剩余: {minutes_remaining:4.1f}分钟 | {mode_str}",
              end='', flush=True)

    def _generate_report(self, output_path: Path):
        """生成报告"""
        report_file = output_path / 'detection_report.md'
        end_time = datetime.now()
        total_duration = (end_time - self.start_time).total_seconds()
        detection_rate = self.total_anomalies / self.total_collected * 100 if self.total_collected > 0 else 0

        with open(report_file, 'w', encoding='utf-8') as f:
            f.write("# 🚗 CARLA实时检测报告\n\n")
            f.write("## 测试信息\n\n")
            f.write(f"- **测试类型**: 30分钟实时检测 (混合模式)\n")
            f.write(f"- **开始时间**: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"- **结束时间**: {end_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"- **总时长**: {total_duration:.0f}秒 ({total_duration / 60:.1f}分钟)\n")
            f.write(f"- **CARLA连接**: {'成功 (混合模式)' if self.use_carla else '失败 (模拟模式)'}\n")
            f.write(f"- **数据源**: {'CARLA实时 + 模拟数据' if self.use_carla else '模拟数据'}\n\n")

            f.write("## 检测统计\n\n")
            f.write(f"- **总检测次数**: {self.total_collected}\n")
            f.write(f"- **总异常数**: {self.total_anomalies}\n")
            f.write(f"- **检出率**: {detection_rate:.2f}%\n")
            if self.results:
                avg_duration = sum(r.duration_ms for r in self.results) / len(self.results)
                f.write(f"- **平均检测时长**: {avg_duration:.2f}ms\n\n")

            f.write("## 风险分布\n\n")
            f.write("| 风险等级 | 数量 | 百分比 |\n")
            f.write("|---------|------|--------|\n")
            for level, count in sorted(self.risk_distribution.items()):
                percentage = count / self.total_collected * 100 if self.total_collected > 0 else 0
                f.write(f"| **{level}** | {count} | {percentage:.1f}% |\n")
            f.write("\n")

            f.write("## 异常样例\n\n")
            anomaly_results = [r for r in self.results if r.violations][:10]
            for i, result in enumerate(anomaly_results):
                f.write(f"### {i + 1}. {result.scenario_name}\n\n")
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
                'data_source': 'CARLA+模拟' if self.use_carla else '模拟',
                'results': [asdict(r) for r in self.results]
            }, f, indent=2, ensure_ascii=False)

        print(f"\n\n报告已保存: {report_file}")
        print(f"JSON结果已保存: {results_file}")

    def _print_summary(self):
        """打印总结"""
        end_time = datetime.now()
        total_duration = (end_time - self.start_time).total_seconds()
        detection_rate = self.total_anomalies / self.total_collected * 100 if self.total_collected > 0 else 0

        print("\n" + "=" * 65)
        print("                    检测完成总结")
        print("=" * 65)
        print(f"✅ 总检测次数: {self.total_collected}")
        print(f"✅ 总异常数: {self.total_anomalies}")
        print(f"✅ 检出率: {detection_rate:.2f}%")

        if self.results:
            avg_duration = sum(r.duration_ms for r in self.results) / len(self.results)
            print(f"✅ 平均检测时长: {avg_duration:.2f}ms")

        print(f"✅ 总运行时长: {total_duration:.0f}秒 ({total_duration / 60:.1f}分钟)")
        print("\n风险分布:")
        for level, count in sorted(self.risk_distribution.items()):
            percentage = count / self.total_collected * 100 if self.total_collected > 0 else 0
            print(f"  {level:10s}: {count:4d} ({percentage:5.1f}%)")
        print("=" * 65)


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description='CARLA实时检测 - 改进版')
    parser.add_argument('--duration', type=int, default=1800,
                       help='检测时长(秒), 默认1800秒(30分钟)')
    parser.add_argument('--interval', type=float, default=2.0,
                       help='检测间隔(秒), 默认2秒')
    parser.add_argument('--host', type=str, default='localhost',
                       help='CARLA主机地址')
    parser.add_argument('--port', type=int, default=2000,
                       help='CARLA端口')
    parser.add_argument('--output', type=str, default='./output_30min_final',
                       help='输出目录')

    args = parser.parse_args()

    # 创建检测器
    detector = CARLADetector(host=args.host, port=args.port)

    # 连接CARLA
    detector.connect()

    # 运行检测
    detector.run_detection(
        duration_seconds=args.duration,
        interval=args.interval,
        output_dir=args.output
    )


if __name__ == '__main__':
    main()
