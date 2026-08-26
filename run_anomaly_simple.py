#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CARLA异常注入检测 - 使用现有车辆
"""

import sys
import time
import random
import math
import json
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict

sys.path.insert(0, str(Path(__file__).parent / 'backend' / 'app'))

import carla
from ads_safety_platform.scenarios.scenario_validator import ScenarioValidator
from ads_safety_platform.scenarios.scenario_injector import ScenarioBuilder


@dataclass
class AnomalyResult:
    scenario_id: int
    scenario_name: str
    timestamp: str
    anomaly_type: str
    ego_x: float
    ego_y: float
    ego_speed: float
    vehicle_count: int
    violations: list
    risk_index: float
    risk_level: str
    duration_ms: float


class AnomalyDetector:
    def __init__(self, host='localhost', port=2000):
        self.host = host
        self.port = port
        self.client = carla.Client(host, port)
        self.client.set_timeout(10)
        self.world = self.client.get_world()
        self.validator = ScenarioValidator()
        self.ego_vehicle = None
        self.npc_vehicles = []
        self.results = []
        self.risk_distribution = {'CRITICAL': 0, 'HIGH': 0, 'MEDIUM': 0, 'LOW': 0, 'SAFE': 0}
        self.anomaly_stats = {'sudden_brake': 0, 'tailgating': 0, 'close_call': 0}
        self.violation_stats = {}
        self.start_time = None
        self.total_collected = 0
        self.total_violations = 0

    def get_speed(self, vehicle):
        v = vehicle.get_velocity()
        return math.sqrt(v.x**2 + v.y**2 + v.z**2)

    def setup_vehicles(self):
        """使用现有车辆"""
        vehicles = list(self.world.get_actors().filter('vehicle.*'))
        print(f"[设置] 世界中有 {len(vehicles)} 辆车")

        if len(vehicles) == 0:
            print("[错误] 没有可用车辆!")
            return False

        # 第一辆作为ego
        self.ego_vehicle = vehicles[0]
        print(f"[设置] Ego: {self.ego_vehicle.type_id} (ID: {self.ego_vehicle.id})")

        # 其他作为NPC
        for v in vehicles[1:]:
            self.npc_vehicles.append(v)
        print(f"[设置] NPC: {len(self.npc_vehicles)} 辆")
        return True

    def inject_anomaly(self):
        """注入异常"""
        if not self.npc_vehicles:
            return None

        anomaly_type = random.choice(['sudden_brake', 'tailgating', 'close_call'])
        npc = random.choice(self.npc_vehicles)

        try:
            if anomaly_type == 'sudden_brake':
                # 急刹车
                control = carla.VehicleControl(brake=1.0, throttle=0)
                npc.apply_control(control)
                self.anomaly_stats['sudden_brake'] += 1

            elif anomaly_type == 'tailgating':
                # 跟车过近
                ego_t = self.ego_vehicle.get_transform()
                npc_t = npc.get_transform()
                # 移动到ego后方近距离
                new_loc = carla.Location(
                    ego_t.location.x + random.uniform(5, 10),  # ego后方
                    ego_t.location.y + random.uniform(-1, 1),
                    ego_t.location.z
                )
                npc.set_location(new_loc)
                control = carla.VehicleControl(throttle=1.0)
                npc.apply_control(control)
                self.anomaly_stats['tailgating'] += 1

            elif anomaly_type == 'close_call':
                # 横向近距离
                ego_t = self.ego_vehicle.get_transform()
                new_loc = carla.Location(
                    ego_t.location.x + random.uniform(-5, 5),
                    ego_t.location.y + random.uniform(3, 6),  # ego侧方
                    ego_t.location.z
                )
                npc.set_location(new_loc)
                self.anomaly_stats['close_call'] += 1

            print(f"[注入] ⚠️ {anomaly_type} - NPC{npc.id}")
            return anomaly_type
        except Exception as e:
            print(f"[注入] 失败: {e}")
            return None

    def collect_and_detect(self, scenario_id):
        """收集场景并检测"""
        try:
            ego_t = self.ego_vehicle.get_transform()
            ego_speed = self.get_speed(self.ego_vehicle)
            all_vehicles = list(self.world.get_actors().filter('vehicle.*'))

            # 构建场景
            builder = ScenarioBuilder()
            scenario = builder.create_straight_road_scenario(ego_speed=ego_speed, num_vehicles=len(all_vehicles))
            scenario.ego_vehicle.x = ego_t.location.x
            scenario.ego_vehicle.y = ego_t.location.y
            scenario.ego_vehicle.speed = ego_speed
            scenario.ego_vehicle.yaw = ego_t.rotation.yaw

            # 添加NPC
            for veh in all_vehicles:
                if veh.id != self.ego_vehicle.id:
                    t = veh.get_transform()
                    speed = self.get_speed(veh)
                    scenario.vehicles.append(
                        type('VehicleConfig', (), {
                            'x': t.location.x, 'y': t.location.y, 'z': t.location.z,
                            'speed': speed, 'yaw': t.rotation.yaw,
                            'vehicle_type': 'vehicle.npc', 'role': 'npc'
                        })()
                    )

            # RSS检测
            start = time.time()
            result = self.validator.validate(scenario)
            duration_ms = (time.time() - start) * 1000

            violations = [v.to_dict() for v in result.violations]

            return AnomalyResult(
                scenario_id=scenario_id,
                scenario_name=f"检测_{scenario_id}",
                timestamp=datetime.now().isoformat(),
                anomaly_type='normal',
                ego_x=ego_t.location.x,
                ego_y=ego_t.location.y,
                ego_speed=ego_speed,
                vehicle_count=len(all_vehicles),
                violations=violations,
                risk_index=result.risk_index,
                risk_level=result.risk_level,
                duration_ms=duration_ms
            )
        except Exception as e:
            print(f"[错误] {scenario_id}: {e}")
            return None

    def run(self, duration=600, interval=1.0, output='./output_10min_anomaly'):
        """运行检测"""
        self.start_time = datetime.now()
        Path(output).mkdir(exist_ok=True)

        print("\n" + "="*60)
        print("  🚗 CARLA异常注入检测 - RSS规则验证")
        print("="*60)
        print(f"时长: {duration}秒 | 间隔: {interval}秒 | 注入概率: 40%")
        print("="*60 + "\n")

        if not self.setup_vehicles():
            return

        scenario_id = 0
        last_inject = 0
        last_print = time.time()

        while True:
            elapsed = (datetime.now() - self.start_time).total_seconds()
            if elapsed >= duration:
                break

            # 每5-8秒注入异常
            if elapsed - last_inject > random.uniform(5, 8) and random.random() < 0.4:
                self.inject_anomaly()
                last_inject = elapsed

            # 检测
            result = self.collect_and_detect(scenario_id)
            if result:
                self.results.append(result)
                self.total_collected += 1
                self.risk_distribution[result.risk_level] += 1

                if result.violations:
                    self.total_violations += len(result.violations)
                    for v in result.violations:
                        rule = v.get('rule_id', 'unknown')
                        self.violation_stats[rule] = self.violation_stats.get(rule, 0) + 1

            # 进度
            if time.time() - last_print >= 5:
                pct = elapsed / duration * 100
                rate = self.total_violations / max(1, self.total_collected) * 100
                print(f"\r[{pct:5.1f}%] 检测:{self.total_collected} 违规:{self.total_violations} ({rate:.1f}%) 剩余:{(duration-elapsed)/60:.1f}分钟", end='')
                last_print = time.time()

            scenario_id += 1
            time.sleep(interval)

        # 报告
        self.generate_report(output)
        self.print_summary()

    def generate_report(self, output):
        """生成报告"""
        output_path = Path(output)
        end_time = datetime.now()
        duration = (end_time - self.start_time).total_seconds()
        rate = self.total_violations / max(1, self.total_collected) * 100

        # Markdown报告
        with open(output_path / 'report.md', 'w') as f:
            f.write("# 🚗 CARLA异常注入检测报告\n\n")
            f.write(f"## 测试信息\n\n")
            f.write(f"- 测试时长: {duration:.0f}秒 ({duration/60:.1f}分钟)\n")
            f.write(f"- 总检测: {self.total_collected}\n")
            f.write(f"- 违规总数: {self.total_violations}\n")
            f.write(f"- 违规率: {rate:.2f}%\n\n")

            f.write("## 注入统计\n\n")
            for k, v in self.anomaly_stats.items():
                f.write(f"- {k}: {v}次\n")

            f.write("\n## RSS违规统计\n\n")
            f.write("| 规则 | 次数 |\n|------|------|\n")
            for rule, count in sorted(self.violation_stats.items(), key=lambda x: -x[1]):
                f.write(f"| {rule} | {count} |\n")

            f.write("\n## 风险分布\n\n")
            f.write("| 等级 | 数量 | 占比 |\n|------|------|------|\n")
            for level in ['SAFE', 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL']:
                count = self.risk_distribution.get(level, 0)
                pct = count / max(1, self.total_collected) * 100
                f.write(f"| {level} | {count} | {pct:.1f}% |\n")

            f.write("\n## 违规样例\n\n")
            for r in [x for x in self.results if x.violations][:10]:
                f.write(f"### {r.scenario_name}\n\n")
                f.write(f"- 时间: {r.timestamp}\n")
                f.write(f"- 等级: {r.risk_level}\n")
                for v in r.violations[:3]:
                    f.write(f"  - {v.get('message', v.get('rule_id', '?'))}\n")
                f.write("\n")

        # JSON
        with open(output_path / 'results.json', 'w') as f:
            json.dump({
                'duration': duration,
                'total_collected': self.total_collected,
                'total_violations': self.total_violations,
                'violation_rate': rate,
                'anomaly_stats': self.anomaly_stats,
                'violation_stats': self.violation_stats,
                'risk_distribution': self.risk_distribution,
                'results': [asdict(r) for r in self.results if r.violations]
            }, f, indent=2)

        print(f"\n\n✅ 报告已保存: {output_path}")

    def print_summary(self):
        """打印总结"""
        print("\n" + "="*60)
        print("              检测完成")
        print("="*60)
        print(f"总检测: {self.total_collected} | 违规: {self.total_violations}")
        print(f"\n注入统计:")
        for k, v in self.anomaly_stats.items():
            print(f"  {k}: {v}次")
        print(f"\nRSS违规统计:")
        for rule, count in sorted(self.violation_stats.items(), key=lambda x: -x[1])[:10]:
            print(f"  {rule}: {count}次")
        print(f"\n风险分布:")
        for level, count in self.risk_distribution.items():
            print(f"  {level}: {count}")
        if self.total_violations > 0:
            print(f"\n✅ RSS规则验证成功! 检测到 {self.total_violations} 个违规")
        else:
            print(f"\n⚠️ 未检测到违规")
        print("="*60)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--duration', type=int, default=600)
    parser.add_argument('--interval', type=float, default=1.0)
    parser.add_argument('--output', default='./output_10min_anomaly')
    args = parser.parse_args()

    detector = AnomalyDetector()
    detector.run(duration=args.duration, interval=args.interval, output=args.output)
