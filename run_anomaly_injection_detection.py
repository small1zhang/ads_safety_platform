#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CARLA异常注入检测 - 验证RSS规则有效性

功能:
1. 自动创建危险场景（急刹车、违规变道、交叉口冲突）
2. 动态注入异常NPC行为
3. 实时RSS检测
4. 验证规则有效性
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
    """异常检测结果"""
    scenario_id: int
    scenario_name: str
    timestamp: str
    anomaly_type: str  # 注入的异常类型
    ego_x: float
    ego_y: float
    ego_speed: float
    vehicle_count: int
    violations: list
    risk_index: float
    risk_level: str
    duration_ms: float


class AnomalyInjectionDetector:
    """异常注入检测器 - 用于验证RSS规则"""

    def __init__(self, host='localhost', port=2000, timeout=10.0):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.client = None
        self.world = None
        self.blueprint_library = None
        self.ego_vehicle = None
        self.npc_vehicles = []
        self.validator = ScenarioValidator()
        self.results = []
        self.risk_distribution = {
            'CRITICAL': 0, 'HIGH': 0, 'MEDIUM': 0, 'LOW': 0, 'SAFE': 0
        }
        self.anomaly_stats = {
            'sudden_brake': 0,
            'illegal_lane_change': 0,
            'intersection_conflict': 0,
            'tailgating': 0,
            'speeding': 0,
            'red_light_violation': 0,
        }
        self.violation_stats = {}
        self.start_time = None
        self.total_collected = 0
        self.total_anomalies = 0
        self.total_violations = 0

    def connect(self) -> bool:
        """连接CARLA"""
        print(f"[连接] 连接到 CARLA {self.host}:{self.port}...")
        try:
            self.client = carla.Client(self.host, self.port)
            self.client.set_timeout(self.timeout)
            self.world = self.client.get_world()
            self.blueprint_library = self.world.get_blueprint_library()
            print(f"[连接] ✅ CARLA连接成功! 地图: {self.world.get_map().name}")
            return True
        except Exception as e:
            print(f"[连接] ❌ CARLA连接失败: {e}")
            return False

    def get_vehicle_speed(self, vehicle):
        """获取车辆速度(m/s)"""
        v = vehicle.get_velocity()
        return math.sqrt(v.x**2 + v.y**2 + v.z**2)

    def spawn_vehicles(self, ego_count=1, npc_count=4):
        """Spawn车辆"""
        print(f"\n[创建] 创建 {npc_count} 辆NPC车辆...")

        spawn_points = list(self.world.get_map().get_spawn_points())
        random.shuffle(spawn_points)

        # Spawn NPC
        spawned = 0
        for i, sp in enumerate(spawn_points[:npc_count]):
            try:
                npc_bp = random.choice(self.blueprint_library.filter('vehicle.*'))
                npc = self.world.spawn_actor(npc_bp, sp)

                # 随机初始速度
                tm = self.client.get_trafficmanager(self.port + 200 + i)
                npc.set_autopilot(True, self.port + 200 + i)

                self.npc_vehicles.append({
                    'actor': npc,
                    'type': 'normal',
                    'initial_speed': random.uniform(8, 15),
                    'target_lane': sp.lane_id if hasattr(sp, 'lane_id') else 0,
                    'behavior': 'normal'
                })
                spawned += 1
            except Exception as e:
                print(f"[创建] NPC {i} 失败: {e}")

        # Spawn Ego - 尝试多个位置
        if spawn_points:
            ego_spawned = False
            for sp_idx, sp in enumerate(spawn_points[:10]):  # 尝试前10个spawn点
                try:
                    ego_bp = self.blueprint_library.find('vehicle.tesla.model3')
                    if not ego_bp:
                        ego_bp = self.blueprint_library.filter('vehicle.*')[0]
                    ego_bp.set_attribute('role_name', 'ego')
                    self.ego_vehicle = self.world.spawn_actor(ego_bp, sp)
                    self.ego_vehicle.set_autopilot(True, self.port + 300)
                    print(f"[创建] ✅ Ego车辆已创建 (ID: {self.ego_vehicle.id}) at spawn点{sp_idx}")
                    ego_spawned = True
                    break
                except Exception as e:
                    continue

            if not ego_spawned:
                # 使用现有车辆作为ego
                existing_vehicles = list(self.world.get_actors().filter('vehicle.*'))
                if existing_vehicles:
                    self.ego_vehicle = existing_vehicles[0]
                    print(f"[使用] 使用现有车辆作为Ego (ID: {self.ego_vehicle.id})")

        print(f"[创建] ✅ 已创建 {spawned} 辆NPC + 1辆Ego")
        return spawned

    def inject_sudden_brake(self, npc_index):
        """注入异常: 前车急刹"""
        if npc_index < len(self.npc_vehicles):
            npc = self.npc_vehicles[npc_index]['actor']
            try:
                # 急刹车控制
                control = carla.VehicleControl()
                control.brake = 1.0  # 最大刹车
                control.throttle = 0.0
                npc.apply_control(control)
                self.npc_vehicles[npc_index]['behavior'] = 'sudden_brake'
                self.anomaly_stats['sudden_brake'] += 1
                print(f"[注入] ⚠️ NPC{npc_index} 急刹车!")
            except Exception as e:
                print(f"[注入] 急刹车失败: {e}")

    def inject_illegal_lane_change(self, npc_index):
        """注入异常: 违规变道"""
        if npc_index < len(self.npc_vehicles):
            npc = self.npc_vehicles[npc_index]['actor']
            try:
                # 快速变道
                transform = npc.get_transform()
                transform.location.x += random.uniform(-3, 3)  # 横向移动
                control = carla.VehicleControl()
                control.steer = random.uniform(-0.5, 0.5)  # 转向
                control.throttle = 0.3
                npc.apply_control(control)
                self.npc_vehicles[npc_index]['behavior'] = 'illegal_lane_change'
                self.anomaly_stats['illegal_lane_change'] += 1
                print(f"[注入] ⚠️ NPC{npc_index} 违规变道!")
            except Exception as e:
                print(f"[注入] 变道失败: {e}")

    def inject_tailgating(self, npc_index, ego_distance=5):
        """注入异常: 跟车过近"""
        if npc_index < len(self.npc_vehicles) and self.ego_vehicle:
            npc = self.npc_vehicles[npc_index]['actor']
            ego_t = self.ego_vehicle.get_transform()
            try:
                # 移动到ego前方近距离
                new_loc = carla.Location(
                    ego_t.location.x - ego_distance,  # ego前方
                    ego_t.location.y + random.uniform(-2, 2),
                    ego_t.location.z
                )
                new_t = carla.Transform(new_loc, ego_t.rotation)
                npc.set_location(new_loc)

                # 设置高速度
                control = carla.VehicleControl()
                control.throttle = 1.0
                npc.apply_control(control)

                self.npc_vehicles[npc_index]['behavior'] = 'tailgating'
                self.anomaly_stats['tailgating'] += 1
                print(f"[注入] ⚠️ NPC{npc_index} 跟车过近 (距离{ego_distance}m)!")
            except Exception as e:
                print(f"[注入] 跟车设置失败: {e}")

    def inject_speeding(self, npc_index):
        """注入异常: 超速行驶"""
        if npc_index < len(self.npc_vehicles):
            npc = self.npc_vehicles[npc_index]['actor']
            try:
                control = carla.VehicleControl()
                control.throttle = 1.0  # 最大油门
                npc.apply_control(control)
                self.npc_vehicles[npc_index]['behavior'] = 'speeding'
                self.anomaly_stats['speeding'] += 1
                print(f"[注入] ⚠️ NPC{npc_index} 超速行驶!")
            except Exception as e:
                print(f"[注入] 超速设置失败: {e}")

    def inject_intersection_conflict(self):
        """注入异常: 交叉口冲突"""
        # 让两辆车同时进入交叉口
        if len(self.npc_vehicles) >= 2:
            try:
                # 获取交叉口位置
                map = self.world.get_map()
                waypoints = map.generate_waypoints(3)
                if waypoints:
                    intersection_point = waypoints[len(waypoints)//2].transform.location
                else:
                    intersection_point = carla.Location(0, 0, 0)

                # 移动NPC到交叉口
                for i in range(min(2, len(self.npc_vehicles))):
                    npc = self.npc_vehicles[i]['actor']
                    new_loc = carla.Location(
                        intersection_point.x + random.uniform(-10, 10),
                        intersection_point.y + random.uniform(-10, 10),
                        intersection_point.z + 1
                    )
                    npc.set_location(new_loc)
                    self.npc_vehicles[i]['behavior'] = 'intersection_conflict'

                self.anomaly_stats['intersection_conflict'] += 1
                print(f"[注入] ⚠️ 交叉口冲突场景已设置!")
            except Exception as e:
                print(f"[注入] 交叉口设置失败: {e}")

    def inject_anomaly_randomly(self):
        """随机注入异常"""
        anomaly_types = [
            ('sudden_brake', lambda: self.inject_sudden_brake(random.randint(0, len(self.npc_vehicles)-1))),
            ('illegal_lane_change', lambda: self.inject_illegal_lane_change(random.randint(0, len(self.npc_vehicles)-1))),
            ('tailgating', lambda: self.inject_tailgating(random.randint(0, len(self.npc_vehicles)-1), random.uniform(3, 8))),
            ('speeding', lambda: self.inject_speeding(random.randint(0, len(self.npc_vehicles)-1))),
            ('intersection_conflict', self.inject_intersection_conflict),
        ]

        # 30%概率注入异常
        if random.random() < 0.30:
            anomaly_type, action = random.choice(anomaly_types)
            action()
            return anomaly_type
        return None

    def collect_scenario(self, scenario_id: int, anomaly_type: str = None) -> AnomalyResult:
        """收集场景并进行RSS检测"""
        try:
            if not self.ego_vehicle:
                return None

            # 获取ego状态
            ego_transform = self.ego_vehicle.get_transform()
            ego_speed = self.get_vehicle_speed(self.ego_vehicle)

            # 获取所有车辆
            all_vehicles = list(self.world.get_actors().filter('vehicle.*'))

            # 构建RSS场景
            builder = ScenarioBuilder()
            scenario = builder.create_straight_road_scenario(
                ego_speed=ego_speed,
                num_vehicles=len(all_vehicles)
            )

            # 更新ego位置
            scenario.ego_vehicle.x = ego_transform.location.x
            scenario.ego_vehicle.y = ego_transform.location.y
            scenario.ego_vehicle.speed = ego_speed
            scenario.ego_vehicle.yaw = ego_transform.rotation.yaw

            # 添加NPC到场景
            for veh in all_vehicles:
                if veh.id != self.ego_vehicle.id:
                    t = veh.get_transform()
                    v = veh.get_velocity()
                    speed = self.get_vehicle_speed(veh)

                    # 检查是否在危险距离
                    dx = t.location.x - ego_transform.location.x
                    dy = t.location.y - ego_transform.location.y
                    distance = math.sqrt(dx**2 + dy**2)

                    # 注入违规预期
                    expected_violations = []
                    if self.npc_vehicles:
                        for npc_info in self.npc_vehicles:
                            if npc_info['actor'].id == veh.id:
                                behavior = npc_info.get('behavior', 'normal')
                                if behavior == 'sudden_brake':
                                    expected_violations.append('RSS_LONGITUDINAL')
                                elif behavior == 'illegal_lane_change':
                                    expected_violations.append('RSS_LATERAL')

                    scenario.vehicles.append(
                        type('VehicleConfig', (), {
                            'x': t.location.x,
                            'y': t.location.y,
                            'z': t.location.z,
                            'speed': speed,
                            'yaw': t.rotation.yaw,
                            'vehicle_type': 'vehicle.npc',
                            'role': 'npc',
                            'expected_violations': expected_violations
                        })()
                    )

            # RSS检测
            start = time.time()
            validation_result = self.validator.validate(scenario)
            duration_ms = (time.time() - start) * 1000

            # 构建结果
            violations = [v.to_dict() for v in validation_result.violations]

            result = AnomalyResult(
                scenario_id=scenario_id,
                scenario_name=f"异常注入_{scenario_id}",
                timestamp=datetime.now().isoformat(),
                anomaly_type=anomaly_type or 'normal',
                ego_x=ego_transform.location.x,
                ego_y=ego_transform.location.y,
                ego_speed=ego_speed,
                vehicle_count=len(all_vehicles),
                violations=violations,
                risk_index=validation_result.risk_index,
                risk_level=validation_result.risk_level,
                duration_ms=duration_ms
            )

            return result

        except Exception as e:
            print(f"[收集] ❌ 场景 {scenario_id} 失败: {e}")
            import traceback
            traceback.print_exc()
            return None

    def cleanup(self):
        """清理"""
        print("\n[清理] 销毁车辆...")
        for npc_info in self.npc_vehicles:
            if npc_info['actor'].is_alive:
                npc_info['actor'].destroy()
        if self.ego_vehicle and self.ego_vehicle.is_alive:
            self.ego_vehicle.destroy()
        print("[清理] ✅ 完成")

    def run_detection(self, duration_seconds: int = 600, interval: float = 1.0,
                     output_dir: str = './output_10min_anomaly_test'):
        """运行10分钟异常注入检测"""
        self.start_time = datetime.now()
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        print("\n" + "=" * 65)
        print("     🚗 CARLA异常注入检测 - 验证RSS规则有效性")
        print("=" * 65)
        print(f"开始时间: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"检测时长: {duration_seconds}秒 ({duration_seconds / 60:.0f}分钟)")
        print(f"检测间隔: {interval}秒")
        print(f"异常注入概率: 30%")
        print("=" * 65 + "\n")

        # 创建车辆
        self.spawn_vehicles(npc_count=4)

        print("\n[开始] 开始异常注入检测...\n")

        scenario_id = 0
        last_print_time = time.time()
        last_anomaly_time = time.time()

        while True:
            elapsed = (datetime.now() - self.start_time).total_seconds()
            if elapsed >= duration_seconds:
                break

            # 定期注入异常（每5-10秒）
            if elapsed - last_anomaly_time > random.uniform(5, 10):
                anomaly_type = self.inject_anomaly_randomly()
                last_anomaly_time = elapsed

            # 收集并检测
            result = self.collect_scenario(scenario_id)

            if result:
                self.results.append(result)
                self.total_collected += 1
                self.risk_distribution[result.risk_level] = \
                    self.risk_distribution.get(result.risk_level, 0) + 1

                if result.violations:
                    self.total_anomalies += 1
                    self.total_violations += len(result.violations)

                    # 统计违规类型
                    for v in result.violations:
                        v_type = v.get('rule_id', 'unknown')
                        self.violation_stats[v_type] = self.violation_stats.get(v_type, 0) + 1

            # 每5秒打印进度
            current_time = time.time()
            if current_time - last_print_time >= 5:
                self._print_progress(elapsed, duration_seconds)
                last_print_time = current_time

            scenario_id += 1
            time.sleep(interval)

        # 清理
        self.cleanup()

        # 生成报告
        self._generate_report(output_path)
        self._print_summary()

    def _print_progress(self, elapsed: float, total: float):
        """打印进度"""
        progress = (elapsed / total) * 100
        minutes_remaining = (total - elapsed) / 60
        detection_rate = self.total_anomalies / self.total_collected * 100 if self.total_collected > 0 else 0

        bar_length = 25
        filled = int(bar_length * elapsed / total)
        bar = '█' * filled + '░' * (bar_length - filled)

        print(f"\r[{bar}] {progress:5.1f}% | "
              f"{elapsed / 60:.1f}/{total / 60:.0f}分钟 | "
              f"已检测: {self.total_collected:4d} | "
              f"违规: {self.total_violations:3d} ({detection_rate:4.1f}%) | "
              f"剩余: {minutes_remaining:.1f}分钟",
              end='', flush=True)

    def _generate_report(self, output_path: Path):
        """生成报告"""
        report_file = output_path / 'anomaly_test_report.md'
        end_time = datetime.now()
        total_duration = (end_time - self.start_time).total_seconds()
        detection_rate = self.total_anomalies / self.total_collected * 100 if self.total_collected > 0 else 0

        with open(report_file, 'w', encoding='utf-8') as f:
            f.write("# 🚗 CARLA异常注入检测报告 - RSS规则验证\n\n")
            f.write(f"## 测试信息\n\n")
            f.write(f"- **测试类型**: 异常注入检测\n")
            f.write(f"- **目的**: 验证RSS规则有效性\n")
            f.write(f"- **开始时间**: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"- **结束时间**: {end_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"- **总时长**: {total_duration:.0f}秒 ({total_duration / 60:.1f}分钟)\n\n")

            f.write(f"## 检测统计\n\n")
            f.write(f"- **总检测次数**: {self.total_collected}\n")
            f.write(f"- **检测到违规数**: {self.total_violations}\n")
            f.write(f"- **违规帧数**: {self.total_anomalies}\n")
            f.write(f"- **违规率**: {detection_rate:.2f}%\n")
            if self.results:
                avg_duration = sum(r.duration_ms for r in self.results) / len(self.results)
                f.write(f"- **平均检测时长**: {avg_duration:.2f}ms\n\n")

            f.write(f"## 注入异常统计\n\n")
            for anomaly_type, count in self.anomaly_stats.items():
                f.write(f"- **{anomaly_type}**: {count}次\n")
            f.write("\n")

            f.write(f"## 违规类型统计 (RSS规则)\n\n")
            f.write("| 规则ID | 违规次数 |\n")
            f.write("|--------|----------|\n")
            for rule_id, count in sorted(self.violation_stats.items(), key=lambda x: -x[1]):
                f.write(f"| {rule_id} | {count} |\n")
            f.write("\n")

            f.write(f"## 风险分布\n\n")
            f.write("| 风险等级 | 数量 | 百分比 |\n")
            f.write("|---------|------|--------|\n")
            for level, count in sorted(self.risk_distribution.items()):
                percentage = count / self.total_collected * 100 if self.total_collected > 0 else 0
                f.write(f"| **{level}** | {count} | {percentage:.1f}% |\n")
            f.write("\n")

            f.write(f"## 违规样例\n\n")
            anomaly_results = [r for r in self.results if r.violations][:15]
            for i, result in enumerate(anomaly_results):
                f.write(f"### {i + 1}. {result.scenario_name} (注入类型: {result.anomaly_type})\n\n")
                f.write(f"- 时间: {result.timestamp}\n")
                f.write(f"- 风险等级: {result.risk_level}\n")
                f.write(f"- 违规数: {len(result.violations)}\n")
                for v in result.violations[:5]:
                    f.write(f"  - {v.get('message', v.get('rule_id', 'Unknown'))}\n")
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
                'total_violations': self.total_violations,
                'detection_rate': detection_rate,
                'risk_distribution': self.risk_distribution,
                'anomaly_stats': self.anomaly_stats,
                'violation_stats': self.violation_stats,
                'data_source': 'CARLA异常注入',
                'results': [asdict(r) for r in self.results if r.violations]
            }, f, indent=2, ensure_ascii=False)

        print(f"\n\n📄 报告已保存: {report_file}")
        print(f"📊 JSON结果已保存: {results_file}")

    def _print_summary(self):
        """打印总结"""
        end_time = datetime.now()
        total_duration = (end_time - self.start_time).total_seconds()
        detection_rate = self.total_anomalies / self.total_collected * 100 if self.total_collected > 0 else 0

        print("\n" + "=" * 65)
        print("              异常注入检测完成总结")
        print("=" * 65)
        print(f"✅ 总检测次数: {self.total_collected}")
        print(f"✅ 检测到违规: {self.total_violations}次")
        print(f"✅ 违规帧数: {self.total_anomalies}")
        print(f"✅ 违规率: {detection_rate:.2f}%")

        print(f"\n📊 注入异常统计:")
        for anomaly_type, count in self.anomaly_stats.items():
            print(f"   {anomaly_type}: {count}次")

        print(f"\n📋 RSS规则违规统计:")
        for rule_id, count in sorted(self.violation_stats.items(), key=lambda x: -x[1])[:10]:
            print(f"   {rule_id}: {count}次")

        print(f"\n🎯 风险分布:")
        for level, count in sorted(self.risk_distribution.items()):
            percentage = count / self.total_collected * 100 if self.total_collected > 0 else 0
            print(f"   {level:10s}: {count:4d} ({percentage:5.1f}%)")

        if detection_rate > 0:
            print(f"\n✅ RSS规则验证成功! 检测到 {self.total_violations} 个违规")
        else:
            print(f"\n⚠️ 未检测到违规，可能需要调整异常注入参数")

        print("=" * 65)


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description='CARLA异常注入检测')
    parser.add_argument('--duration', type=int, default=600,
                       help='检测时长(秒), 默认600秒(10分钟)')
    parser.add_argument('--interval', type=float, default=1.0,
                       help='检测间隔(秒), 默认1秒')
    parser.add_argument('--host', type=str, default='localhost',
                       help='CARLA主机')
    parser.add_argument('--port', type=int, default=2000,
                       help='CARLA端口')
    parser.add_argument('--output', type=str, default='./output_10min_anomaly_test',
                       help='输出目录')

    args = parser.parse_args()

    detector = AnomalyInjectionDetector(host=args.host, port=args.port)
    if not detector.connect():
        print("\n❌ CARLA连接失败")
        sys.exit(1)

    detector.run_detection(
        duration_seconds=args.duration,
        interval=args.interval,
        output_dir=args.output
    )


if __name__ == '__main__':
    main()
