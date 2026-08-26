#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CARLA异常检测 - 实时预警版

功能:
1. 实时RSS异常检测
2. 终端预警提示
3. CARLA车辆颜色变化警示
4. 违规原因详细输出
5. 违规数据记录
"""

import sys
import time
import random
import math
import json
import os
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict

sys.path.insert(0, str(Path(__file__).parent / 'backend' / 'app'))

import carla
from ads_safety_platform.scenarios.scenario_validator import ScenarioValidator
from ads_safety_platform.scenarios.scenario_injector import ScenarioBuilder


# 预警颜色
RED = '\033[91m'
YELLOW = '\033[93m'
GREEN = '\033[92m'
BLUE = '\033[94m'
RESET = '\033[0m'
BOLD = '\033[1m'


@dataclass
class ViolationAlert:
    """违规预警"""
    timestamp: str
    scenario_id: int
    risk_level: str
    violations: list
    ego_position: tuple
    ego_speed: float
    nearest_vehicle_distance: float
    alert_triggered: bool


class RealTimeAlertDetector:
    """实时预警检测器"""

    def __init__(self, host='localhost', port=2000):
        self.host = host
        self.port = port
        self.client = carla.Client(host, port)
        self.client.set_timeout(10)
        self.world = self.client.get_world()
        self.blueprint_library = self.world.get_blueprint_library()
        self.validator = ScenarioValidator()

        # 车辆
        self.ego_vehicle = None
        self.npc_vehicles = []
        self.all_vehicles = []

        # 结果
        self.results = []
        self.alerts = []
        self.risk_distribution = {'CRITICAL': 0, 'HIGH': 0, 'MEDIUM': 0, 'LOW': 0, 'SAFE': 0}
        self.violation_stats = {}
        self.start_time = None

        # 预警状态
        self.current_alert_level = 'SAFE'
        self.last_alert_time = 0
        self.alert_cooldown = 3  # 预警冷却时间(秒)

        # 初始颜色
        self.original_colors = {}

    def get_speed(self, vehicle):
        v = vehicle.get_velocity()
        return math.sqrt(v.x**2 + v.y**2 + v.z**2)

    def setup_vehicles(self):
        """设置车辆"""
        vehicles = list(self.world.get_actors().filter('vehicle.*'))
        print(f"[设置] 世界中有 {len(vehicles)} 辆车")

        if len(vehicles) == 0:
            print("[错误] 没有可用车辆!")
            return False

        # 保存原始颜色
        for v in vehicles:
            try:
                self.original_colors[v.id] = v.attributes.get('color', '255,255,255')
            except:
                self.original_colors[v.id] = '255,255,255'

        # Ego
        self.ego_vehicle = vehicles[0]
        print(f"[设置] Ego: {self.ego_vehicle.type_id} (ID: {self.ego_vehicle.id})")

        # NPC
        for v in vehicles[1:]:
            self.npc_vehicles.append(v)
        print(f"[设置] NPC: {len(self.npc_vehicles)} 辆")

        return True

    def set_vehicle_color(self, vehicle, color_rgb):
        """设置车辆颜色"""
        try:
            color_str = f"{color_rgb[0]},{color_rgb[1]},{color_rgb[2]}"
            vehicle.set_attribute('color', color_str)
        except Exception as e:
            pass

    def flash_vehicle_color(self, vehicle, alert_color):
        """闪烁车辆颜色"""
        try:
            if alert_color == 'RED':
                self.set_vehicle_color(vehicle, (255, 0, 0))  # 红色
            elif alert_color == 'YELLOW':
                self.set_vehicle_color(vehicle, (255, 255, 0))  # 黄色
            elif alert_color == 'GREEN':
                self.set_vehicle_color(vehicle, (0, 255, 0))  # 绿色
            elif alert_color == 'BLUE':
                self.set_vehicle_color(vehicle, (0, 0, 255))  # 蓝色
        except:
            pass

    def print_alert(self, alert_type, message, details=None):
        """打印预警信息"""
        timestamp = datetime.now().strftime('%H:%M:%S')

        if alert_type == 'CRITICAL':
            print(f"\n{'='*70}")
            print(f"{RED}{BOLD}🚨 CRITICAL 预警 | {timestamp}{RESET}")
            print(f"{RED}{message}{RESET}")
            if details:
                for d in details:
                    print(f"{RED}  ⚠️  {d}{RESET}")
            print(f"{'='*70}\n")

        elif alert_type == 'HIGH':
            print(f"\n{RED}🔴 HIGH 预警 | {timestamp}{RESET}")
            print(f"{RED}{message}{RESET}")
            if details:
                for d in details:
                    print(f"{RED}  ⚠️  {d}{RESET}")
            print()

        elif alert_type == 'MEDIUM':
            print(f"\n{YELLOW}🟡 MEDIUM 预警 | {timestamp}{RESET}")
            print(f"{YELLOW}{message}{RESET}")
            if details:
                for d in details:
                    print(f"{YELLOW}  ⚠️  {d}{RESET}")
            print()

        elif alert_type == 'INFO':
            print(f"{BLUE}ℹ️  {message}{RESET}")
            if details:
                for d in details:
                    print(f"{BLUE}    {d}{RESET}")

    def inject_anomaly(self):
        """注入异常"""
        if not self.npc_vehicles:
            return None

        anomaly_type = random.choice(['sudden_brake', 'tailgating', 'close_call', 'rapid_approach'])
        npc = random.choice(self.npc_vehicles)

        try:
            if anomaly_type == 'sudden_brake':
                control = carla.VehicleControl(brake=1.0, throttle=0)
                npc.apply_control(control)
                self.print_alert('INFO', f"注入异常: 前车急刹 (NPC{npc.id})")

            elif anomaly_type == 'tailgating':
                ego_t = self.ego_vehicle.get_transform()
                new_loc = carla.Location(
                    ego_t.location.x + random.uniform(3, 6),
                    ego_t.location.y + random.uniform(-1, 1),
                    ego_t.location.z
                )
                npc.set_location(new_loc)
                self.print_alert('INFO', f"注入异常: 跟车过近 (NPC{npc.id})")

            elif anomaly_type == 'close_call':
                ego_t = self.ego_vehicle.get_transform()
                new_loc = carla.Location(
                    ego_t.location.x + random.uniform(-3, 3),
                    ego_t.location.y + random.uniform(3, 6),
                    ego_t.location.z
                )
                npc.set_location(new_loc)
                self.print_alert('INFO', f"注入异常: 横向近距离 (NPC{npc.id})")

            elif anomaly_type == 'rapid_approach':
                ego_t = self.ego_vehicle.get_transform()
                new_loc = carla.Location(
                    ego_t.location.x - random.uniform(20, 30),  # ego前方远处
                    ego_t.location.y + random.uniform(-2, 2),
                    ego_t.location.z
                )
                npc.set_location(new_loc)
                control = carla.VehicleControl(throttle=1.0)
                npc.apply_control(control)
                self.print_alert('INFO', f"注入异常: 快速接近 (NPC{npc.id})")

            return anomaly_type
        except Exception as e:
            print(f"[注入] 失败: {e}")
            return None

    def collect_and_detect(self, scenario_id):
        """收集并检测"""
        try:
            ego_t = self.ego_vehicle.get_transform()
            ego_speed = self.get_speed(self.ego_vehicle)
            all_vehicles = list(self.world.get_actors().filter('vehicle.*'))

            # 计算最近车辆距离
            nearest_distance = float('inf')
            nearest_vehicle = None

            for veh in all_vehicles:
                if veh.id != self.ego_vehicle.id:
                    t = veh.get_transform()
                    dx = t.location.x - ego_t.location.x
                    dy = t.location.y - ego_t.location.y
                    dist = math.sqrt(dx**2 + dy**2)
                    if dist < nearest_distance:
                        nearest_distance = dist
                        nearest_vehicle = veh

            # 构建场景
            builder = ScenarioBuilder()
            scenario = builder.create_straight_road_scenario(
                ego_speed=ego_speed,
                num_vehicles=len(all_vehicles)
            )
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

            # 构建预警
            alert = ViolationAlert(
                timestamp=datetime.now().isoformat(),
                scenario_id=scenario_id,
                risk_level=result.risk_level,
                violations=violations,
                ego_position=(ego_t.location.x, ego_t.location.y),
                ego_speed=ego_speed,
                nearest_vehicle_distance=nearest_distance,
                alert_triggered=False
            )

            return alert, violations, result.risk_level, duration_ms, nearest_distance

        except Exception as e:
            print(f"[错误] {scenario_id}: {e}")
            return None

    def process_alert(self, alert, violations, risk_level, scenario_id):
        """处理预警"""
        current_time = time.time()

        # 记录违规统计
        self.risk_distribution[risk_level] += 1
        for v in violations:
            rule = v.get('rule_id', v.get('message', 'unknown'))
            self.violation_stats[rule] = self.violation_stats.get(rule, 0) + 1

        # 检查是否需要预警 (MEDIUM及以上)
        need_alert = (
            risk_level in ['CRITICAL', 'HIGH', 'MEDIUM'] and
            current_time - self.last_alert_time > self.alert_cooldown
        )

        if need_alert:
            self.last_alert_time = current_time
            alert.alert_triggered = True
            self.alerts.append(alert)

            # 预警
            if risk_level == 'CRITICAL':
                self.print_alert('CRITICAL', '检测到严重违规!', [
                    f"风险等级: {risk_level}",
                    f"风险指数: {alert.risk_index:.3f}" if hasattr(alert, 'risk_index') else f"风险指数: -1",
                    f"违规数量: {len(violations)}",
                    f"自车位置: ({alert.ego_position[0]:.1f}, {alert.ego_position[1]:.1f})",
                    f"自车速度: {alert.ego_speed:.1f} m/s",
                    f"最近车辆距离: {alert.nearest_vehicle_distance:.1f}m",
                ])

                # 违规原因
                for v in violations[:5]:
                    msg = v.get('message', v.get('rule_id', '未知违规'))
                    self.print_alert('CRITICAL', f"违规原因: {msg}")

                # CARLA警示
                self.flash_vehicle_color(self.ego_vehicle, 'RED')

            elif risk_level == 'HIGH':
                self.print_alert('HIGH', '检测到高风险违规!', [
                    f"风险等级: {risk_level}",
                    f"违规数量: {len(violations)}",
                    f"最近车辆距离: {alert.nearest_vehicle_distance:.1f}m",
                ])
                for v in violations[:3]:
                    msg = v.get('message', v.get('rule_id', '未知违规'))
                    self.print_alert('HIGH', f"违规原因: {msg}")

                self.flash_vehicle_color(self.ego_vehicle, 'RED')

            elif risk_level == 'MEDIUM':
                self.print_alert('MEDIUM', '检测到中等风险', [
                    f"违规数量: {len(violations)}",
                    f"最近车辆距离: {alert.nearest_vehicle_distance:.1f}m",
                ])
                self.flash_vehicle_color(self.ego_vehicle, 'YELLOW')

        # 恢复正常颜色
        elif risk_level == 'SAFE' or risk_level == 'LOW':
            try:
                orig = self.original_colors.get(self.ego_vehicle.id, '255,255,255')
                self.set_vehicle_color(self.ego_vehicle, [int(x) for x in orig.split(',')])
            except:
                pass

        return alert

    def run(self, duration=600, interval=1.0, output='./output_realtime_alert'):
        """运行检测"""
        self.start_time = datetime.now()
        Path(output).mkdir(exist_ok=True)

        print("\n" + "="*70)
        print(f"{BOLD}  🚗 CARLA实时预警检测 - RSS规则验证{RESET}")
        print("="*70)
        print(f"检测时长: {duration}秒 | 间隔: {interval}秒 | 注入概率: 35%")
        print(f"预警冷却: {self.alert_cooldown}秒")
        print("="*70 + "\n")

        if not self.setup_vehicles():
            return

        scenario_id = 0
        last_inject = 0
        last_print = time.time()
        total_collected = 0
        total_violations = 0

        print(f"{GREEN}✅ 系统启动，等待检测...{RESET}\n")

        while True:
            elapsed = (datetime.now() - self.start_time).total_seconds()
            if elapsed >= duration:
                break

            # 注入异常
            if elapsed - last_inject > random.uniform(4, 7) and random.random() < 0.35:
                self.inject_anomaly()
                last_inject = elapsed

            # 检测
            result = self.collect_and_detect(scenario_id)
            if result:
                alert, violations, risk_level, duration_ms, nearest_dist = result
                total_collected += 1

                if violations:
                    total_violations += len(violations)

                # 处理预警
                self.process_alert(alert, violations, risk_level, scenario_id)

            # 进度
            if time.time() - last_print >= 3:
                violation_rate = total_violations / max(1, total_collected) * 100

                # 进度条
                pct = elapsed / duration * 100
                bar_len = 30
                filled = int(bar_len * elapsed / duration)
                bar = '█' * filled + '░' * (bar_len - filled)

                # 风险分布
                risk_str = ""
                for level in ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'SAFE']:
                    count = self.risk_distribution.get(level, 0)
                    if count > 0:
                        if level == 'CRITICAL':
                            risk_str += f"{RED}{level}:{count}{RESET} "
                        elif level == 'HIGH':
                            risk_str += f"{RED}{level}:{count}{RESET} "
                        elif level == 'MEDIUM':
                            risk_str += f"{YELLOW}{level}:{count}{RESET} "
                        else:
                            risk_str += f"{GREEN}{level}:{count}{RESET} "

                print(f"\r[{bar}] {pct:5.1f}% | "
                      f"检测:{total_collected:4d} | "
                      f"违规:{total_violations:3d}({violation_rate:4.1f}%) | "
                      f"最近:{nearest_dist:.1f}m | "
                      f"{risk_str}"
                      f"剩余:{(duration-elapsed)/60:.1f}分钟",
                      end='', flush=True)
                last_print = time.time()

            scenario_id += 1
            time.sleep(interval)

        # 报告
        self.generate_report(output)
        self.print_summary(total_collected, total_violations)

    def generate_report(self, output):
        """生成报告"""
        output_path = Path(output)
        end_time = datetime.now()
        duration = (end_time - self.start_time).total_seconds()

        # Markdown
        with open(output_path / 'alert_report.md', 'w') as f:
            f.write("# 🚗 CARLA实时预警检测报告\n\n")
            f.write(f"## 测试信息\n\n")
            f.write(f"- 测试时长: {duration:.0f}秒 ({duration/60:.1f}分钟)\n")
            f.write(f"- 预警冷却: {self.alert_cooldown}秒\n\n")

            f.write(f"## 风险分布\n\n")
            f.write("| 等级 | 数量 | 占比 |\n|------|------|------|\n")
            total = sum(self.risk_distribution.values())
            for level in ['SAFE', 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL']:
                count = self.risk_distribution.get(level, 0)
                pct = count / max(1, total) * 100
                f.write(f"| {level} | {count} | {pct:.1f}% |\n")

            f.write("\n## RSS违规统计\n\n")
            f.write("| 规则 | 次数 |\n|------|------|\n")
            for rule, count in sorted(self.violation_stats.items(), key=lambda x: -x[1]):
                f.write(f"| {rule} | {count} |\n")

            f.write("\n## 预警记录\n\n")
            for alert in self.alerts[:20]:
                f.write(f"### {alert.timestamp}\n\n")
                f.write(f"- 风险等级: {alert.risk_level}\n")
                f.write(f"- 位置: ({alert.ego_position[0]:.1f}, {alert.ego_position[1]:.1f})\n")
                f.write(f"- 速度: {alert.ego_speed:.1f} m/s\n")
                f.write(f"- 最近车辆: {alert.nearest_vehicle_distance:.1f}m\n")
                f.write(f"- 违规数: {len(alert.violations)}\n")
                for v in alert.violations[:3]:
                    f.write(f"  - {v.get('message', v.get('rule_id', '?'))}\n")
                f.write("\n")

        # JSON
        with open(output_path / 'results.json', 'w') as f:
            json.dump({
                'duration': duration,
                'risk_distribution': self.risk_distribution,
                'violation_stats': self.violation_stats,
                'alerts': [asdict(a) for a in self.alerts]
            }, f, indent=2, ensure_ascii=False)

        print(f"\n\n✅ 报告已保存: {output_path}")

    def print_summary(self, total_collected, total_violations):
        """打印总结"""
        print("\n" + "="*70)
        print(f"{BOLD}              检测完成总结{RESET}")
        print("="*70)
        print(f"总检测: {total_collected} | 违规总数: {total_violations}")

        print(f"\n风险分布:")
        for level, count in self.risk_distribution.items():
            pct = count / max(1, total_collected) * 100
            if level == 'CRITICAL':
                print(f"  {RED}{level:10s}: {count:4d} ({pct:5.1f}%){RESET}")
            elif level in ['HIGH', 'MEDIUM']:
                print(f"  {YELLOW}{level:10s}: {count:4d} ({pct:5.1f}%){RESET}")
            else:
                print(f"  {GREEN}{level:10s}: {count:4d} ({pct:5.1f}%){RESET}")

        print(f"\nRSS违规统计 (Top 10):")
        for rule, count in sorted(self.violation_stats.items(), key=lambda x: -x[1])[:10]:
            print(f"  {rule}: {count}次")

        print(f"\n预警次数: {len(self.alerts)}")

        if total_violations > 0:
            print(f"\n{GREEN}✅ RSS规则验证成功!{RESET}")
            print(f"{GREEN}检测到 {total_violations} 个违规，触发了 {len(self.alerts)} 次预警{RESET}")
        else:
            print(f"{YELLOW}⚠️ 未检测到违规{RESET}")

        print("="*70)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--duration', type=int, default=600)
    parser.add_argument('--interval', type=float, default=1.0)
    parser.add_argument('--output', default='./output_realtime_alert')
    args = parser.parse_args()

    detector = RealTimeAlertDetector()
    detector.run(duration=args.duration, interval=args.interval, output=args.output)
