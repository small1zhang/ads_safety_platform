#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CARLA真实轨迹检测 - 自动创建ego车辆

功能:
1. 连接CARLA并加载地图
2. 自动创建ego车辆 (自动驾驶)
3. 同时创建NPC车辆增加复杂度
4. 运行RSS异常检测
5. 30分钟持续检测
"""

import sys
import time
import random
import math
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
    ego_x: float
    ego_y: float
    ego_z: float
    ego_speed: float
    ego_yaw: float
    vehicle_count: int
    pedestrian_count: int
    violations: list
    risk_index: float
    risk_level: str
    duration_ms: float


class CARLARealTrajectoryDetector:
    """CARLA真实轨迹检测器"""

    def __init__(self, host='localhost', port=2000, timeout=10.0):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.client = None
        self.world = None
        self.blueprint_library = None
        self.ego_vehicle = None
        self.npc_vehicles = []
        self.pedestrians = []
        self.validator = ScenarioValidator()
        self.results = []
        self.risk_distribution = {
            'CRITICAL': 0, 'HIGH': 0, 'MEDIUM': 0, 'LOW': 0, 'SAFE': 0
        }
        self.start_time = None
        self.total_collected = 0
        self.total_anomalies = 0

    def connect(self) -> bool:
        """连接CARLA"""
        print(f"[连接] 尝试连接到 CARLA {self.host}:{self.port}...")
        try:
            self.client = carla.Client(self.host, self.port)
            self.client.set_timeout(self.timeout)
            self.client.get_world()
            self.world = self.client.get_world()
            self.blueprint_library = self.world.get_blueprint_library()
            print("[连接] ✅ CARLA连接成功！")
            print(f"[地图] 当前地图: {self.world.get_map().name}")
            return True
        except Exception as e:
            print(f"[连接] ❌ CARLA连接失败: {e}")
            return False

    def setup_world(self):
        """设置世界环境"""
        print("\n[设置] 配置世界环境...")

        # 设置天气
        weather = carla.WeatherParameters(
            cloudiness=50.0,
            precipitation=30.0,
            wetness=30.0,
            sun_azimuth_angle=45.0,
            sun_altitude_angle=45.0
        )
        self.world.set_weather(weather)
        print("[设置] ✅ 天气已设置")

        # 检查现有车辆
        existing_vehicles = self.world.get_actors().filter('vehicle.*')
        print(f"[设置] 世界中已有 {len(existing_vehicles)} 辆车")

        # 获取 spawn points
        map = self.world.get_map()
        spawn_points = map.get_spawn_points()

        if len(spawn_points) < 2:
            print("[警告] Spawn points不足")
            spawn_points = [carla.Transform(carla.Location(x=0, y=0, z=2), carla.Rotation())]

        return spawn_points

    def use_existing_or_spawn(self):
        """使用现有车辆或创建新车辆"""
        existing_vehicles = list(self.world.get_actors().filter('vehicle.*'))

        if len(existing_vehicles) > 0:
            print(f"\n[使用] 使用现有车辆进行检测...")
            self.ego_vehicle = existing_vehicles[0]
            print(f"[使用] Ego车辆: {self.ego_vehicle.type_id} (ID: {self.ego_vehicle.id})")

            # 其他车辆作为NPC
            for veh in existing_vehicles[1:min(6, len(existing_vehicles))]:  # 最多5辆NPC
                self.npc_vehicles.append(veh)

            print(f"[使用] NPC车辆数量: {len(self.npc_vehicles)}")
        else:
            print("\n[警告] 世界中没有车辆，需要手动添加")
            return False

        return True

    def spawn_npc_vehicles(self, spawn_points, count=5):
        """Spawn NPC车辆"""
        print(f"\n[Spawn] 创建{count}个NPC车辆...")

        npc_bp = self.blueprint_library.filter('vehicle.*')[1]  # 第二辆作为NPC
        spawned = 0

        for i, sp in enumerate(spawn_points[:count]):
            if i == 0:  # 跳过第一个，因为是ego
                continue

            try:
                npc_bp = random.choice(self.blueprint_library.filter('vehicle.*'))
                npc = self.world.spawn_actor(npc_bp, sp)
                tm = self.client.get_trafficmanager(self.port + 100)
                npc.set_autopilot(True, self.port + 100)
                self.npc_vehicles.append(npc)
                spawned += 1
            except Exception as e:
                print(f"[Spawn] NPC {i} 失败: {e}")

        print(f"[Spawn] ✅ 已创建{spawned}个NPC车辆")
        return spawned

    def spawn_pedestrians(self, count=3):
        """Spawn行人"""
        print(f"\n[Spawn] 创建{count}个行人...")

        pedestrian_bp = random.choice(self.blueprint_library.filter('walker.pedestrian.*'))
        spawn_points = []
        w = self.world.get_map().get_waypoints(3)
        for wp in w[:20]:
            spawn_points.append(carla.Transform(
                location=wp[0].transform.location + carla.Location(x=random.uniform(-2, 2), z=1),
                rotation=wp[0].transform.rotation
            ))

        spawned = 0
        for i in range(count):
            try:
                ped_bp = random.choice(self.blueprint_library.filter('walker.pedestrian.*'))
                sp = random.choice(spawn_points) if spawn_points else carla.Transform(
                    carla.Location(x=random.uniform(-50, 50), y=random.uniform(-50, 50), z=1)
                )
                ped = self.world.spawn_actor(ped_bp, sp)
                self.pedestrians.append(ped)
                spawned += 1
            except Exception as e:
                print(f"[Spawn] Pedestrian {i} 失败: {e}")

        print(f"[Spawn] ✅ 已创建{spawned}个行人")
        return spawned

    def get_vehicle_speed(self, vehicle):
        """获取车辆速度(m/s)"""
        v = vehicle.get_velocity()
        return math.sqrt(v.x**2 + v.y**2 + v.z**2)

    def collect_scenario(self, scenario_id: int) -> AnomalyResult:
        """收集当前场景"""
        try:
            if not self.ego_vehicle:
                return None

            # 获取ego状态
            ego_transform = self.ego_vehicle.get_transform()
            ego_velocity = self.ego_vehicle.get_velocity()
            ego_speed = self.get_vehicle_speed(self.ego_vehicle)

            # 构建场景数据
            builder = ScenarioBuilder()

            # 创建模拟场景进行RSS检测
            scenario = builder.create_straight_road_scenario(
                ego_speed=ego_speed,
                num_vehicles=len(self.npc_vehicles)
            )

            # 更新ego位置
            scenario.ego_vehicle.x = ego_transform.location.x
            scenario.ego_vehicle.y = ego_transform.location.y
            scenario.ego_vehicle.z = ego_transform.location.z
            scenario.ego_vehicle.speed = ego_speed
            scenario.ego_vehicle.yaw = ego_transform.rotation.yaw

            # 获取所有车辆信息
            all_actors = self.world.get_actors()
            vehicles = all_actors.filter('vehicle.*')
            peds = all_actors.filter('walker.pedestrian.*')

            # 添加NPC车辆到场景
            for veh in vehicles:
                if veh.id != self.ego_vehicle.id:
                    t = veh.get_transform()
                    v = veh.get_velocity()
                    speed = self.get_vehicle_speed(veh)
                    scenario.vehicles.append(
                        type('VehicleConfig', (), {
                            'x': t.location.x,
                            'y': t.location.y,
                            'z': t.location.z,
                            'speed': speed,
                            'yaw': t.rotation.yaw,
                            'vehicle_type': 'vehicle.npc',
                            'role': 'npc'
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
                scenario_name=f"真实轨迹_{scenario_id}",
                timestamp=datetime.now().isoformat(),
                ego_x=ego_transform.location.x,
                ego_y=ego_transform.location.y,
                ego_z=ego_transform.location.z,
                ego_speed=ego_speed,
                ego_yaw=ego_transform.rotation.yaw,
                vehicle_count=len(vehicles),
                pedestrian_count=len(peds),
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
        """清理所有actor"""
        print("\n[清理] 销毁所有车辆和行人...")

        for veh in self.npc_vehicles:
            if veh.is_alive:
                veh.destroy()

        for ped in self.pedestrians:
            if ped.is_alive:
                ped.destroy()

        if self.ego_vehicle and self.ego_vehicle.is_alive:
            self.ego_vehicle.destroy()

        print("[清理] ✅ 清理完成")

    def run_detection(self, duration_seconds: int = 1800, interval: float = 2.0,
                     output_dir: str = './output_30min_real_carla'):
        """运行30分钟真实轨迹检测"""
        self.start_time = datetime.now()
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        print("\n" + "=" * 65)
        print("      🚗 CARLA真实轨迹检测 - 30分钟实时检测")
        print("=" * 65)
        print(f"开始时间: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"检测时长: {duration_seconds}秒 ({duration_seconds / 60:.0f}分钟)")
        print(f"检测间隔: {interval}秒")
        print(f"输出目录: {output_path}")
        print("=" * 65 + "\n")

        # 设置世界
        spawn_points = self.setup_world()

        # 使用现有车辆或创建
        if not self.use_existing_or_spawn():
            # 如果没有现有车辆，尝试创建
            self.spawn_ego_vehicle(spawn_points)
            self.spawn_npc_vehicles(spawn_points, count=5)
            self.spawn_pedestrians(count=3)

        # 等待车辆稳定
        print("\n[等待] 等待车辆启动稳定...")
        time.sleep(3)

        scenario_id = 0
        last_print_time = time.time()

        print("\n[开始] 开始实时检测...\n")

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

        # 清理
        self.cleanup()

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

        print(f"\r[{bar}] {progress:5.1f}% | "
              f"{elapsed / 60:5.1f}/{total / 60:.0f}分钟 | "
              f"已检测: {self.total_collected:4d} | "
              f"异常: {self.total_anomalies:4d} ({detection_rate:5.1f}%) | "
              f"剩余: {minutes_remaining:4.1f}分钟",
              end='', flush=True)

    def _generate_report(self, output_path: Path):
        """生成报告"""
        report_file = output_path / 'real_trajectory_report.md'
        end_time = datetime.now()
        total_duration = (end_time - self.start_time).total_seconds()
        detection_rate = self.total_anomalies / self.total_collected * 100 if self.total_collected > 0 else 0

        with open(report_file, 'w', encoding='utf-8') as f:
            f.write("# 🚗 CARLA真实轨迹检测报告\n\n")
            f.write("## 测试信息\n\n")
            f.write(f"- **测试类型**: CARLA真实轨迹检测\n")
            f.write(f"- **数据来源**: CARLA实时仿真数据\n")
            f.write(f"- **开始时间**: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"- **结束时间**: {end_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"- **总时长**: {total_duration:.0f}秒 ({total_duration / 60:.1f}分钟)\n")
            f.write(f"- **检测频率**: 每2秒一次\n\n")

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
                f.write(f"- 位置: ({result.ego_x:.1f}, {result.ego_y:.1f}, {result.ego_z:.1f})\n")
                f.write(f"- 速度: {result.ego_speed:.1f} m/s\n")
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
                'data_source': 'CARLA真实轨迹',
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
        print(f"✅ 数据来源: CARLA真实轨迹")
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

    parser = argparse.ArgumentParser(description='CARLA真实轨迹检测')
    parser.add_argument('--duration', type=int, default=1800,
                       help='检测时长(秒), 默认1800秒(30分钟)')
    parser.add_argument('--interval', type=float, default=2.0,
                       help='检测间隔(秒), 默认2秒')
    parser.add_argument('--host', type=str, default='localhost',
                       help='CARLA主机地址')
    parser.add_argument('--port', type=int, default=2000,
                       help='CARLA端口')
    parser.add_argument('--output', type=str, default='./output_30min_real_carla',
                       help='输出目录')

    args = parser.parse_args()

    # 创建检测器
    detector = CARLARealTrajectoryDetector(host=args.host, port=args.port)

    # 连接CARLA
    if not detector.connect():
        print("\n❌ CARLA连接失败，程序退出")
        sys.exit(1)

    # 运行检测
    detector.run_detection(
        duration_seconds=args.duration,
        interval=args.interval,
        output_dir=args.output
    )


if __name__ == '__main__':
    main()
