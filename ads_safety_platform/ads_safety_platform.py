import carla
import time
import numpy as np
import pygame
import threading
import math
import random
import os
from datetime import datetime
from safety_judge import safety_judge, SAFE, UNCERTAIN, UNSAFE, risk_levels
from auto_drive_agent import LaneKeepingAgent

# 显示设置
WIDTH, HEIGHT = 800, 600

# 障碍车数量（可修改）
NUM_NPC_VEHICLES = 10 # 障碍车数量，用于测试碰撞风险（可修改，如 10）

NORMAL_DRIVING_TEST = True  # 是否测试正常驾驶，True 表示测试正常驾驶，False 表示压线测试
LOCK_RED_LIGHT = False  # 是否强制保持红灯, True 表示强制保持红灯, False 表示不强制保持红灯

# 全局红绿灯控制
global_traffic_lights = []
lock_red_light = True

# 场景采集相关全局变量
image_sequence = []
MAX_IMAGE_SEQUENCE_LENGTH = 30

def collect_scene_data(ego_vehicle, world, current_frame=None):
    """采集场景数据，包括相机图像序列和场景配置"""
    global image_sequence
    
    scene_data = {
        'timestamp': datetime.now().isoformat(),
        'ego_vehicle': {
            'type_id': ego_vehicle.type_id,
            'location': {
                'x': ego_vehicle.get_location().x,
                'y': ego_vehicle.get_location().y,
                'z': ego_vehicle.get_location().z
            },
            'velocity': {
                'x': ego_vehicle.get_velocity().x,
                'y': ego_vehicle.get_velocity().y,
                'z': ego_vehicle.get_velocity().z
            },
            'transform': {
                'pitch': ego_vehicle.get_transform().rotation.pitch,
                'yaw': ego_vehicle.get_transform().rotation.yaw,
                'roll': ego_vehicle.get_transform().rotation.roll
            },
            'control': {
                'throttle': ego_vehicle.get_control().throttle,
                'steer': ego_vehicle.get_control().steer,
                'brake': ego_vehicle.get_control().brake,
                'reverse': ego_vehicle.get_control().reverse
            }
        },
        'vehicles': [],
        'traffic_lights': [],
        'lane_markers': [],
        'pedestrians': [],
        'obstacles': [],
        'image_sequence': []
    }
    
    vehicles = world.get_actors().filter('vehicle.*')
    for vehicle in vehicles:
        if vehicle.id != ego_vehicle.id and vehicle.is_alive:
            scene_data['vehicles'].append({
                'id': vehicle.id,
                'type_id': vehicle.type_id,
                'location': {
                    'x': vehicle.get_location().x,
                    'y': vehicle.get_location().y,
                    'z': vehicle.get_location().z
                },
                'velocity': {
                    'x': vehicle.get_velocity().x,
                    'y': vehicle.get_velocity().y,
                    'z': vehicle.get_velocity().z
                }
            })
    
    traffic_lights = world.get_actors().filter('traffic.traffic_light*')
    for tl in traffic_lights:
        if tl.is_alive:
            scene_data['traffic_lights'].append({
                'id': tl.id,
                'location': {
                    'x': tl.get_location().x,
                    'y': tl.get_location().y,
                    'z': tl.get_location().z
                },
                'state': tl.get_state().name
            })
    
    pedestrians = world.get_actors().filter('walker.pedestrian*')
    for ped in pedestrians:
        if ped.is_alive:
            scene_data['pedestrians'].append({
                'id': ped.id,
                'location': {
                    'x': ped.get_location().x,
                    'y': ped.get_location().y,
                    'z': ped.get_location().z
                },
                'velocity': {
                    'x': ped.get_velocity().x,
                    'y': ped.get_velocity().y,
                    'z': ped.get_velocity().z
                }
            })
    
    actors = world.get_actors()
    obstacle_types = ['static.prop.*', 'dynamic.prop.*']
    for obstacle_type in obstacle_types:
        obstacles = actors.filter(obstacle_type)
        for obs in obstacles:
            if obs.is_alive:
                scene_data['obstacles'].append({
                    'id': obs.id,
                    'type_id': obs.type_id,
                    'location': {
                        'x': obs.get_location().x,
                        'y': obs.get_location().y,
                        'z': obs.get_location().z
                    }
                })
    
    if current_frame is not None:
        image_sequence.append({
            'timestamp': datetime.now().isoformat(),
            'frame': current_frame.copy()
        })
        if len(image_sequence) > MAX_IMAGE_SEQUENCE_LENGTH:
            image_sequence.pop(0)
    
    scene_data['image_sequence'] = [img['timestamp'] for img in image_sequence]
    
    return scene_data

def attention_model_vote(scene_data):
    """专注度小模型表决判定模块 - 打桩实现"""
    print(f"专注度小模型表决判定 - 输入场景数据: {len(scene_data['vehicles'])} 辆车, {len(scene_data['pedestrians'])} 个行人")
    
    risk_score = random.random()
    
    if risk_score > 0.8:
        print("专注度小模型表决判定结果: 不安全")
        return UNSAFE
    else:
        print("专注度小模型表决判定结果: 安全")
        return SAFE

def save_scene_evidence(scene_data, test_sequence_id):
    """保存现场证据"""
    save_dir = f"scene_evidence/{test_sequence_id}"
    os.makedirs(save_dir, exist_ok=True)
    
    evidence_file = os.path.join(save_dir, "scene_data.txt")
    with open(evidence_file, 'w') as f:
        f.write(f"Test Sequence ID: {test_sequence_id}\n")
        f.write(f"Timestamp: {scene_data['timestamp']}\n")
        f.write(f"\n=== 自车信息 ===\n")
        f.write(f"Type: {scene_data['ego_vehicle']['type_id']}\n")
        f.write(f"Location: {scene_data['ego_vehicle']['location']}\n")
        f.write(f"Velocity: {scene_data['ego_vehicle']['velocity']}\n")
        
        f.write(f"\n=== 车辆信息 ({len(scene_data['vehicles'])} 辆) ===\n")
        for v in scene_data['vehicles']:
            f.write(f"  - {v['type_id']}: {v['location']}\n")
        
        f.write(f"\n=== 交通灯信息 ({len(scene_data['traffic_lights'])} 个) ===\n")
        for tl in scene_data['traffic_lights']:
            f.write(f"  - State: {tl['state']} at {tl['location']}\n")
        
        f.write(f"\n=== 行人信息 ({len(scene_data['pedestrians'])} 个) ===\n")
        for p in scene_data['pedestrians']:
            f.write(f"  - Pedestrian at {p['location']}\n")
        
        f.write(f"\n=== 障碍物信息 ({len(scene_data['obstacles'])} 个) ===\n")
        for obs in scene_data['obstacles']:
            f.write(f"  - {obs['type_id']} at {obs['location']}\n")
    
    print(f"现场证据已保存到: {save_dir}")
    return save_dir

def log_risk_violation(result):
    """记录物理规则判定失败信息到文件并打印"""
    timestamp = datetime.now().isoformat()
    failed_rules = []
    
    if result['red_light']['risk'] == UNSAFE:
        failed_rules.append(f"[闯红灯风险] {result['red_light']['message']}")
    if result['lane_keeping']['risk'] == UNSAFE:
        failed_rules.append(f"[车道压线风险] {result['lane_keeping']['message']}")
    if result['collision']['risk'] == UNSAFE:
        failed_rules.append(f"[碰撞风险] {result['collision']['message']}")
    
    print(f"⚠️ 物理规则判定为不安全 - 时间: {timestamp}")
    print(f"   失败规则:")
    for rule in failed_rules:
        print(f"     - {rule}")
    
    os.makedirs("safety_logs", exist_ok=True)
    log_file = os.path.join("safety_logs", "risk_violations.log")
    
    with open(log_file, 'a') as f:
        f.write(f"\n{'='*60}\n")
        f.write(f"违规时间: {timestamp}\n")
        f.write(f"总体风险等级: {result['overall_risk_str']}\n")
        f.write("失败规则:\n")
        for rule in failed_rules:
            f.write(f"  {rule}\n")
    
    print(f"⚠️ 物理规则判定失败信息已记录到: {log_file}")

def spawn_npc_vehicles(world, num_vehicles=10):
    """生成 NPC 障碍车辆（自动行驶，产生碰撞风险）"""
    if num_vehicles <= 0:
        print("需要生成的车辆数量为 0，不生成任何 NPC 车辆")
        return []

    blueprint_library = world.get_blueprint_library()
    vehicle_bps = blueprint_library.filter('vehicle.*')
    vehicle_bps = [bp for bp in vehicle_bps if int(bp.get_attribute('number_of_wheels')) == 4]
    
    # 额外：彻底排除警车（双重保险）
    vehicle_bps = [bp for bp in vehicle_bps if 'police' not in bp.id.lower()]

    spawn_points = world.get_map().get_spawn_points()
    npcs = []

    available_spawns = spawn_points.copy()
    random.shuffle(available_spawns)
    max_possible = min(num_vehicles, len(available_spawns))

    for i in range(max_possible):
        bp = random.choice(vehicle_bps)
        spawn_point = available_spawns[i]

        try:
            npc = world.try_spawn_actor(bp, spawn_point)
            if npc:
                npc.set_autopilot(True)
                npcs.append(npc)
                print(f"生成障碍车: {npc.type_id}")
        except RuntimeError:
            continue

    print(f"\n✅ 成功生成 {len(npcs)} 辆 NPC 车辆")
    return npcs


# ==============================================
# 强制所有红绿灯保持红灯
# ==============================================
def set_all_traffic_lights_to_red(world):
    global global_traffic_lights
    traffic_lights = world.get_actors().filter('traffic.traffic_light*')
    global_traffic_lights = list(traffic_lights)
    
    for tl in traffic_lights:
        tl.set_state(carla.TrafficLightState.Red)
        # 把红绿黄时间都设成极大值，确保永远不变
        tl.set_red_time(9999.0)
        tl.set_green_time(0.0)
        tl.set_yellow_time(0.0)
        tl.freeze(True)  # 冻结，不自动切换
    print(f"✅ 已将 {len(global_traffic_lights)} 个交通灯强制设置为红灯并冻结")

# 独立线程持续锁红灯
def traffic_light_red_thread():
    global global_traffic_lights, lock_red_light
    while lock_red_light:
        try:
            for tl in global_traffic_lights:
                if tl.is_alive():
                    tl.set_state(carla.TrafficLightState.Red)
            time.sleep(0.1)
        except:
            pass
# ==============================================


def test_safety_system():
    """测试安全检测系统 + 碰撞风险车辆"""
    npc_vehicles = []
    risk_counts = {SAFE: 0, UNCERTAIN: 0, UNSAFE: 0}
    test_count = 0

    try:
        # 初始化 pygame
        pygame.init()
        screen = pygame.display.set_mode((WIDTH, HEIGHT))
        font = pygame.font.Font(None, 24)
        clock = pygame.time.Clock()
        
        # 连接到Carla服务器
        client = carla.Client('localhost', 2000)
        client.set_timeout(15.0)  # 设置连接超时时间为 15 秒
        #world = client.get_world()
        #world = client.load_world('Town05')  # 可以改为 'Town01'~'Town05'
        world = client.load_world('Town03') 
        map = world.get_map()
        
        if LOCK_RED_LIGHT:
            # 启动强制红灯系统
            set_all_traffic_lights_to_red(world)
            tl_thread = threading.Thread(target=traffic_light_red_thread, daemon=True)
            tl_thread.start()
        
        # ==============================================
        # 关键修复：关闭自动刷车 + 清空所有现有车辆
        # ==============================================
        traffic_manager = client.get_trafficmanager(8000)
        traffic_manager.set_synchronous_mode(True)
        traffic_manager.set_hybrid_physics_mode(False)  # 关闭自动生成车辆

        # 销毁世界上所有车辆（包括警车）
        for actor in world.get_actors().filter('vehicle.*'):
            if actor.is_alive and actor.attributes.get('role_name') != 'ego':
                actor.destroy()
        # 设置同步模式
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 0.05
        world.apply_settings(settings)
        
        # 获取/生成自车
        ego_vehicle = None
        for actor in world.get_actors():
            if actor.type_id.startswith('vehicle.') and actor.attributes.get('role_name') == 'ego':
                ego_vehicle = actor
                break
        
        if not ego_vehicle:
            print("未找到自车，正在生成测试车辆...")
            blueprint_library = world.get_blueprint_library()
            vehicle_bp = blueprint_library.find('vehicle.tesla.model3')
            vehicle_bp.set_attribute('role_name', 'ego')
            spawn_points = map.get_spawn_points()
            
            for spawn_point in spawn_points:
                try:
                    ego_vehicle = world.spawn_actor(vehicle_bp, spawn_point)
                    print(f"生成自车: {ego_vehicle.type_id}")
                    break
                except RuntimeError as e:
                    continue
            else:
                print("无法生成自车")
                return
        
        # ====================== 生成碰撞风险障碍车 ======================
        print(f"正在生成 {NUM_NPC_VEHICLES} 辆障碍车...")
        npc_vehicles = spawn_npc_vehicles(world, NUM_NPC_VEHICLES)
        time.sleep(1)
        # ========================================================================
        
        # 初始化 Agent
        agent = LaneKeepingAgent(ego_vehicle, target_speed=25.0)
        
        # 设置相机
        blueprint_library = world.get_blueprint_library()
        cam = blueprint_library.find('sensor.camera.rgb')
        cam.set_attribute('image_size_x', str(WIDTH))
        cam.set_attribute('image_size_y', str(HEIGHT))
        cam.set_attribute('fov', '100')
        camera = world.spawn_actor(cam, carla.Transform(carla.Location(x=-5, z=2.5), carla.Rotation(pitch=-10)), attach_to=ego_vehicle)
        
        # 相机回调
        frame = None
        lock = threading.Lock()
        def camera_callback(img):
            nonlocal frame
            a = np.frombuffer(img.raw_data, np.uint8).reshape(img.height, img.width, 4)[:, :, :3]
            with lock:
                frame = a[:, :, ::-1]
        camera.listen(camera_callback)
        
        print("\n开始测试安全检测系统（含碰撞风险车辆）...")
        print("按 Ctrl+C 或关闭窗口停止测试")
        
        # 安全检测结果和锁
        safety_result = None
        safety_result_lock = threading.Lock()
        execution_time = 0.0
        
        # 安全检测线程函数
        def safety_check_thread():
            nonlocal safety_result, execution_time
            sequence_id = 0
            while True:
                try:
                    start = time.time()
                    result = safety_judge(ego_vehicle, world)
                    execution_time = time.time() - start
                    
                    with lock:
                        current_frame_copy = frame.copy() if frame is not None else None
                    
                    scene_data = collect_scene_data(ego_vehicle, world, current_frame_copy)
                    
                    if result['overall_risk'] == UNSAFE:
                        log_risk_violation(result)
                    else:
                        attention_result = attention_model_vote(scene_data)
                        if attention_result == UNSAFE:
                            sequence_id += 1
                            print(f"⚠️ 专注度小模型表决判定为不安全，正在保存现场证据...")
                            save_scene_evidence(scene_data, sequence_id)
                            result['overall_risk'] = UNSAFE
                            result['overall_risk_str'] = 'UNSAFE (Attention)'
                    
                    with safety_result_lock:
                        safety_result = result
                except Exception as e:
                    print(f"安全检测线程错误: {e}")
                time.sleep(0.05)  # 控制检测频率：每 0.05 秒检查一次
        
        # 启动安全检测线程
        safety_thread = threading.Thread(target=safety_check_thread, daemon=True)
        safety_thread.start()
        
        # 等待第一次检测结果
        while safety_result is None:
            time.sleep(0.1)  # 等待安全检测线程初始化
        
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return
            
            world.tick()
            test_count += 1
            
            # 获取安全结果
            with safety_result_lock:
                result = safety_result
            
            risk_counts[result['overall_risk']] += 1
            
            # 车道保持控制
            control = agent.run_step(map)
            ego_vehicle.apply_control(control)
            
            # 渲染画面
            screen.fill((0, 0, 0))
            with lock:
                if frame is not None:
                    surf = pygame.surfarray.make_surface(frame.swapaxes(0, 1))
                    screen.blit(surf, (0, 0))
            
            # 风险颜色映射
            color_map = {
                SAFE: (0, 255, 0),          # 安全 - 绿色
                UNCERTAIN: (255, 255, 0),   # 不确定 - 黄色
                UNSAFE: (255, 0, 0)         # 不安全 - 红色
            }
            current_color = color_map[result['overall_risk']]
            
            # 显示信息
            speed = math.hypot(ego_vehicle.get_velocity().x, ego_vehicle.get_velocity().y)
            texts = [
                (f"Speed: {speed*3.6:.1f} km/h", (255, 255, 255)),  # 白色
                (f"Steer: {control.steer:.2f}", (255, 255, 255)),   # 白色
                (f"Overall Risk: {result['overall_risk_str']}", color_map[result['overall_risk']]),
                (f"Red Light: {result['red_light']['risk_str']} - {result['red_light']['message']}", color_map[result['red_light']['risk']]),
                (f"Lane Crossing: {result['lane_keeping']['risk_str']} - {result['lane_keeping']['message']}", color_map[result['lane_keeping']['risk']]),
                (f"Collision: {result['collision']['risk_str']} - {result['collision']['message']}", color_map[result['collision']['risk']]),
                (f"Execution Time: {execution_time:.3f}s", (255, 255, 255))  # 白色
            ]
            y = 20
            for text, color in texts:
                screen.blit(font.render(text, True, color), (20, y))
                y += 28
            
            # # 统计
            # if test_count % 10 == 0:
            #     stats = [
            #         f"Test: {test_count}",
            #         f"SAFE: {risk_counts[SAFE]}",
            #         f"UNCERTAIN: {risk_counts[UNCERTAIN]}",
            #         f"UNSAFE: {risk_counts[UNSAFE]}"
            #     ]
            #     y = 220
            #     for t in stats:
            #         screen.blit(font.render(t, True, (255,255,255)), (520, y))
            #         y += 22
            
            pygame.display.flip()
            clock.tick(30)
            
    except KeyboardInterrupt:
        print("\n测试终止")
    finally:
        if LOCK_RED_LIGHT:
            # 停止红灯锁定
            global lock_red_light
            lock_red_light = False
            time.sleep(0.15)

        # 清理所有车辆
        print("\n正在清理车辆...")
        try:
            settings = world.get_settings()
            settings.synchronous_mode = False
            world.apply_settings(settings)
            
            camera.destroy()
            for npc in npc_vehicles:
                if npc.is_alive:
                    npc.destroy()
            if ego_vehicle and ego_vehicle.is_alive:
                ego_vehicle.destroy()
                
        except:
            pass
        
        pygame.quit()
        print(f"\n=== 最终统计 ===")
        if test_count > 0:
            for k, v in risk_counts.items():
                print(f"{risk_levels[k]}: {v} ({v/test_count*100:.1f}%)")
        else:
            print("未执行任何测试循环")

if __name__ == '__main__':
    test_safety_system()