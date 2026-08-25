import carla
import numpy as np
import math

from ads_safety_platform.car.trajectory_prediction import predict_trajectory, VehicleParams
from ads_safety_platform.car.reachable_set import generate_trajectory_bundle, compute_reachable_sets, convex_hull_2d
from ads_safety_platform.car.collision_prediction import analyze_collision

# 风险等级定义
SAFE = 0           # 安全
UNCERTAIN = 1      # 不确定
UNSAFE = 2         # 不安全

# 风险等级文字映射
risk_levels = {SAFE: "SAFE", UNCERTAIN: "UNCERTAIN", UNSAFE: "UNSAFE"}

# 预测时间
PREDICT_TIME = 5.0

# 车辆参数
vehicle_params = VehicleParams()

def carla_to_numpy(vec):
    """将Carla向量转换为numpy数组"""
    return np.array([vec.x, vec.y])

def get_heading(vehicle):
    """获取车辆航向角（弧度）"""
    return math.radians(vehicle.get_transform().rotation.yaw)

def get_vehicle_state(vehicle):
    """获取车辆状态"""
    location = vehicle.get_location()
    velocity = vehicle.get_velocity()
    speed = math.hypot(velocity.x, velocity.y)
    heading = get_heading(vehicle)
    
    return {
        'x': location.x,
        'y': location.y,
        'v': speed,
        'theta': heading
    }

def predict_trajectory_carla(vehicle, a_cmd=0.0, delta=0.0, duration=PREDICT_TIME):
    """基于Carla车辆对象的轨迹预测"""
    state = get_vehicle_state(vehicle)
    return predict_trajectory(
        state['x'], state['y'], state['v'], state['theta'],
        a_cmd, delta, duration=duration, params=vehicle_params
    )

def reachable_set_carla(vehicle, duration=PREDICT_TIME):
    """基于Carla车辆对象的可达区域预测"""
    state = get_vehicle_state(vehicle)
    trajectories, controls = generate_trajectory_bundle(
        state['x'], state['y'], state['v'], state['theta'],
        duration=duration, params=vehicle_params
    )
    reachable_sets = compute_reachable_sets(trajectories)
    return trajectories, controls, reachable_sets

def collision_prediction_carla(ego_vehicle, other_vehicle, duration=PREDICT_TIME):
    """基于Carla车辆对象的碰撞预测"""
    ego_state = get_vehicle_state(ego_vehicle)
    other_state = get_vehicle_state(other_vehicle)
    
    result = analyze_collision(
        ego_state['x'], ego_state['y'], ego_state['v'], ego_state['theta'],
        other_state['x'], other_state['y'], other_state['v'], other_state['theta'],
        duration=duration, params=vehicle_params
    )
    
    # 分析碰撞风险
    n_total = result['n_total']
    n_safe = result['n_safe']
    n_colliding = result['n_colliding']
    
    # 根据碰撞检测结果判断
    if n_safe == 0:
        return UNSAFE, "Inevitable collision"
    elif n_colliding == 0:
        return SAFE, "No collision risk"
    else:
        # 当存在碰撞轨迹时，返回UNCERTAIN
        return UNCERTAIN, f"Collision probability: {n_colliding}/{n_total}"

def check_red_light(ego_vehicle, world):
    """
    🔥 CARLA 闯红灯检测 - 优化版 - 针对0.9.16环境
    严格遵守你的逻辑：
    1. 无红灯 → 直接 SAFE
    2. 已过停止线（距离 <1m）→ 直接 UNSAFE
    3. 只有【全部轨迹都闯红灯】→ UNSAFE
    4. 只要有一条轨迹能停下 → 不报 UNSAFE
    """
    SAFE = 0
    UNCERTAIN = 1
    UNSAFE = 2

    # 车辆基础信息
    ego_state = get_vehicle_state(ego_vehicle)
    v = ego_state['v']
    max_decel = vehicle_params.max_brake_decel
    braking_distance = v**2 / (2 * max_decel) if v > 0 else 0.0

    ego_loc = ego_vehicle.get_location()
    ego_wp = world.get_map().get_waypoint(ego_loc, lane_type=carla.LaneType.Driving)
    forward_vec = ego_vehicle.get_transform().get_forward_vector()

    target_tl = None
    matched_stop_wp = None
    min_dist = 9999.0

    # ==============================================
    # 【优化匹配策略】精确匹配：同车道 + 正前方 + 红灯
    # ==============================================
    traffic_lights = world.get_actors().filter("traffic.traffic_light*")
    
    for tl in traffic_lights:
        try:
            if tl.get_state() != carla.TrafficLightState.Red:
                continue

            # 获取交通灯的触发位置（更可靠的方法）
            # tl_loc = tl.get_transform().location
            
            # 获取交通灯关联的停止线位置
            stop_wps = tl.get_stop_waypoints()
            if not stop_wps:
                continue

            for swp in stop_wps:
                # 更严格的匹配逻辑：必须在同一道路和车道
                if swp.road_id == ego_wp.road_id and swp.lane_id == ego_wp.lane_id:
                    # 检查是否在车辆前方
                    delta = swp.transform.location - ego_loc
                    dot = delta.x * forward_vec.x + delta.y * forward_vec.y
                    if dot < 0:  # 在车辆后方，跳过
                        continue
                    
                    # 计算距离并更新最小距离
                    dist = ego_loc.distance(swp.transform.location)
                    
                    # 只考虑合理范围内的停止线（避免远处的干扰）
                    if dist < min_dist and dist < 50.0:  # 缩小检测范围
                        min_dist = dist
                        target_tl = tl
                        matched_stop_wp = swp
        except Exception as e:
            print(f"处理交通灯时出错: {e}")
            continue

    # ==============================================
    # 无红灯 → 直接安全
    # ==============================================
    if not target_tl or not matched_stop_wp:
        return SAFE, "Safe - No red light in front"

    print(f"检测到目标红灯，距离停止线: {min_dist:.2f}m, 车速: {v:.2f}m/s")  # 调试信息
    distance_to_stop = min_dist

    # ==============================================
    # 【最高优先级】已过停止线 → 直接闯红灯
    # ==============================================
    if distance_to_stop < 1.0 and v > 0.1:
        print(f"🔴UNSAFE: 会越过停止线，距离={distance_to_stop:.1f}m, 当前车速={v:.2f}m/s")  # 调试信息
        return UNSAFE, f"Red light violation (crossed line) | dist={distance_to_stop:.1f}m"

    # ==============================================
    # 【优化】基于制动距离的初步判断
    # ==============================================
    if distance_to_stop > braking_distance * 2.0:
        # 如果距离很远且有足够的制动距离，则认为安全
        return SAFE, f"Safe - Adequate braking distance (dist={distance_to_stop:.1f}m, brake_dist={braking_distance:.1f}m)"

    # ==============================================
    # 【优化】更精确的轨迹簇判断
    # ==============================================
    # 生成更多样化的轨迹，包含更强的制动情况
    trajectories, _ = generate_trajectory_bundle(
        ego_state['x'], ego_state['y'], ego_state['v'], ego_state['theta'],
        a_range=(-max_decel * 1.2, 0),  # 增加最大减速度的安全系数
        duration=min(PREDICT_TIME, distance_to_stop/v*2 if v > 0.1 else PREDICT_TIME),  # 根据距离调整预测时间
        params=vehicle_params
    )

    # 检查每条轨迹是否会越过停止线
    all_violate = True
    violating_trajectories = 0
    total_trajectories = len(trajectories)
    
    for traj_idx, traj in enumerate(trajectories):
        # 检查整个轨迹路径，而不仅仅是终点
        violate = False
        for point_idx in range(len(traj)):
            px, py = traj[point_idx, 0], traj[point_idx, 1]
            point_loc = carla.Location(x=px, y=py, z=ego_loc.z)
            point_wp = world.get_map().get_waypoint(point_loc, lane_type=carla.LaneType.Driving)
            
            # 检查是否在同一道路和车道，且超过了停止线位置
            if point_wp and point_wp.road_id == matched_stop_wp.road_id and point_wp.lane_id == matched_stop_wp.lane_id:
                # 使用更精确的比较方式：检查点是否在停止线之后
                if point_wp.s > matched_stop_wp.s:
                    violate = True
                    break
        
        if violate:
            violating_trajectories += 1
        else:
            all_violate = False
            # 找到一条不会违反的轨迹即可退出
            break

    # ==============================================
    # 最终输出
    # ==============================================
    if all_violate:
        print(f"所有轨迹都会闯红灯 ({total_trajectories}/{total_trajectories} trajectories)")
        print(f"🔴UNSAFE: 所有轨迹都会闯红灯 ({violating_trajectories}/{total_trajectories} trajectories)")
        return UNSAFE, "Red light violation (all trajectories cross stop line)"
    elif violating_trajectories > 0:
        # 部分轨迹违规，但不是全部，返回不确定
        violation_ratio = violating_trajectories / total_trajectories
        if violation_ratio > 0.5:  # 超过一半的轨迹违规
            return UNCERTAIN, f"High risk of red light violation ({violating_trajectories}/{total_trajectories} trajectories)"
        else:
            return UNCERTAIN, f"Possible red light violation ({violating_trajectories}/{total_trajectories} trajectories)"
    else:
        # 没有轨迹违规，但接近停止线
        if distance_to_stop < braking_distance * 1.2:
            return UNCERTAIN, f"Approaching stop line (dist={distance_to_stop:.1f}m, brake_dist={braking_distance:.1f}m)"
        else:
            return SAFE, f"Safe - Adequate distance to stop line"

def check_lane_crossing(ego_vehicle, map):
    """车道压线检测 - 基于压车道线逻辑"""
    # 获取当前车道
    location = ego_vehicle.get_location()
    waypoint = map.get_waypoint(location, project_to_road=True, lane_type=carla.LaneType.Driving)
    if not waypoint:
        return UNCERTAIN, "Cannot get lane information"

    # 计算横向偏移
    def get_lateral_offset(position, wp):
        """Calculate lateral offset from lane center"""
        if hasattr(position, 'get_location'):
            # If it's a Vehicle object
            veh = carla_to_numpy(position.get_location())
        else:
            # If it's (x, y) coordinates
            veh = np.array(position)
        cen = carla_to_numpy(wp.transform.location)
        yaw = math.radians(wp.transform.rotation.yaw)
        dx = veh[0] - cen[0]
        dy = veh[1] - cen[1]
        return dx * math.sin(yaw) - dy * math.cos(yaw)

    # 检查当前车辆是否已经压线
    lane_width = waypoint.lane_width
    lane_boundary = lane_width / 2  # 车道线位置
    current_offset = get_lateral_offset(ego_vehicle, waypoint)
    
    # 通过 Carla 接口获取车辆的实际宽度
    # 尝试从车辆属性中获取宽度，如果获取失败则使用默认值
    try:
        # 获取车辆蓝图
        vehicle_bp = ego_vehicle.get_blueprint()
        # 尝试获取宽度属性
        if 'width' in vehicle_bp.get_attribute_names():
            vehicle_width = float(vehicle_bp.get_attribute('width'))
        else:
            # 如果没有宽度属性，使用默认值
            vehicle_width = 2.0
        vehicle_half_width = vehicle_width / 2
    except:
        # 发生错误时使用默认值
        vehicle_half_width = 1.0
    
    # 检查车道线类型
    # 获取左右车道线类型
    left_lane_marking = waypoint.left_lane_marking.type
    right_lane_marking = waypoint.right_lane_marking.type
    
    # 添加调试信息
    # print(f"Lane width: {lane_width:.2f}m, boundary: {lane_boundary:.2f}m, current offset: {current_offset:.2f}m, abs offset: {abs(current_offset):.2f}m, vehicle half width: {vehicle_half_width:.2f}m")
    # print(f"Left lane marking: {left_lane_marking}, Right lane marking: {right_lane_marking}")
    
    # 调整判断阈值，考虑车辆宽度和车道线类型
    # 当车辆边缘超过车道边界时，根据车道线类型判断是否报 UNSAFE
    if abs(current_offset) + vehicle_half_width >= lane_boundary:
        # 判断是左侧还是右侧压线
        if current_offset < 0:
            # 右侧压线
            if right_lane_marking == carla.LaneMarkingType.Solid or right_lane_marking == carla.LaneMarkingType.SolidSolid:
                print(f"⛔UNSAFE: Vehicle is currently crossing Right solid lane boundary (offset: {abs(current_offset):.2f}m, vehicle edge: {abs(current_offset) + vehicle_half_width:.2f}m)")
                return UNSAFE, f"Vehicle is currently crossing right solid lane boundary (offset: {abs(current_offset):.2f}m, vehicle edge: {abs(current_offset) + vehicle_half_width:.2f}m)"
            # 虚线，允许压线，继续执行后面的逻辑
        else:
            # 左侧压线
            if left_lane_marking == carla.LaneMarkingType.Solid or left_lane_marking == carla.LaneMarkingType.SolidSolid:
                print(f"⛔UNSAFE: Vehicle is currently crossing Left solid lane boundary (offset: {abs(current_offset):.2f}m, vehicle edge: {abs(current_offset) + vehicle_half_width:.2f}m)")
                return UNSAFE, f"Vehicle is currently crossing solid lane boundary (offset: {abs(current_offset):.2f}m, vehicle edge: {abs(current_offset) + vehicle_half_width:.2f}m)"
            # 虚线，允许压线，继续执行后面的逻辑

    # 生成轨迹簇
    ego_state = get_vehicle_state(ego_vehicle)
    trajectories, controls = generate_trajectory_bundle(
        ego_state['x'], ego_state['y'], ego_state['v'], ego_state['theta'],
        duration=PREDICT_TIME, params=vehicle_params
    )

    # 检查轨迹是否压线
    lane_width = waypoint.lane_width
    lane_boundary = lane_width / 2  # 车道线位置

    trajectories_crossing = 0
    trajectories_safe = 0

    for traj in trajectories:
        crosses_lane = False
        for i in range(len(traj)):
            pos = traj[i, :2]
            wp = map.get_waypoint(carla.Location(x=pos[0], y=pos[1], z=location.z), 
                                 project_to_road=True, lane_type=carla.LaneType.Driving)
            if wp:
                traj_offset = get_lateral_offset(pos, wp)
                if abs(traj_offset) >= lane_boundary:
                    crosses_lane = True
                    break
        if crosses_lane:
            trajectories_crossing += 1
        else:
            trajectories_safe += 1

    total_trajectories = len(trajectories)

    # 判断风险等级
    if trajectories_crossing == 0:
        # 所有轨迹都不会压线
        return SAFE, "No lane crossing risk"
    elif trajectories_safe == 0:
        # 所有轨迹都会压线
        print(f"⛔UNSAFE: All trajectories will cross the lane boundary")
        return UNSAFE, "Lane crossing inevitable"
    else:
        # 部分轨迹会压线，部分不会
        return UNCERTAIN, f"Possible lane crossing ({trajectories_crossing}/{total_trajectories} trajectories crossing)"


def visualize_trajectory_bundle(ego_vehicle, world):
    """可视化自车的轨迹簇区域"""
    # 生成轨迹簇
    ego_state = get_vehicle_state(ego_vehicle)
    trajectories, controls = generate_trajectory_bundle(
        ego_state['x'], ego_state['y'], ego_state['v'], ego_state['theta'],
        duration=PREDICT_TIME, params=vehicle_params
    )
    
    # 绘制轨迹簇 - 使用较短的生命周期以提高刷新响应速度
    for traj in trajectories:
        # 绘制轨迹点
        for i in range(len(traj) - 1):
            point1 = carla.Location(x=traj[i, 0], y=traj[i, 1], z=ego_vehicle.get_location().z + 0.5)
            point2 = carla.Location(x=traj[i+1, 0], y=traj[i+1, 1], z=ego_vehicle.get_location().z + 0.5)
            # 使用红色绘制轨迹线，更像线框区域，厚度设为0.05以减少视觉干扰
            # 生命周期设置为0.2秒以平衡闪烁和刷新响应
            world.debug.draw_line(point1, point2, thickness=0.05, color=carla.Color(r=255, g=0, b=0), life_time=0.2)

def safety_judge(ego_vehicle, world):
    """综合安全判断"""
    # 获取地图
    map = world.get_map()
    
    # 可视化轨迹簇
    visualize_trajectory_bundle(ego_vehicle, world)
    
    # 只计算一次车辆状态
    ego_state = get_vehicle_state(ego_vehicle)
    
    # 闯红灯检测
    red_light_risk, red_light_msg = check_red_light(ego_vehicle, world)
    
    # 车道压线检测
    lane_risk, lane_msg = check_lane_crossing(ego_vehicle, map)
    
    # 碰撞风险检测
    collision_risk = SAFE
    collision_msg = "No collision risk"
    
    # 检查周围车辆和行人（限制检查距离，减少计算）
    ego_pos = np.array([ego_state['x'], ego_state['y']])
    for actor in world.get_actors():
        if actor.id == ego_vehicle.id:
            continue
        if 'vehicle' in actor.type_id or 'walker' in actor.type_id:
            # 计算距离，只检查附近的车辆和行人
            other_pos = np.array([actor.get_location().x, actor.get_location().y])
            distance = np.linalg.norm(ego_pos - other_pos)
            if distance < 50:  # 只检查50米内的对象
                risk, msg = collision_prediction_carla(ego_vehicle, actor)
                if risk > collision_risk:
                    collision_risk = risk
                    collision_msg = msg
                    # 如果发生碰撞风险，打印碰撞物体的信息
                    if risk == UNSAFE:  # 发生碰撞
                        print(f"💥🚗UNSAFE: 检测到与物体的碰撞风险!")
                        print(f"  物体类别: {actor.type_id}")
                        print(f"  物体ID: {actor.id}")
                        print(f"  距离: {distance:.2f}米")
                        print(f"  位置: ({other_pos[0]:.2f}, {other_pos[1]:.2f})")
                        print(f"  碰撞信息: {msg}")
    
    # 综合判断
    overall_risk = max(red_light_risk, lane_risk, collision_risk)
    
    return {
        'overall_risk': overall_risk,
        'overall_risk_str': risk_levels[overall_risk],
        'red_light': {
            'risk': red_light_risk,
            'risk_str': risk_levels[red_light_risk],
            'message': red_light_msg
        },
        'lane_keeping': {
            'risk': lane_risk,
            'risk_str': risk_levels[lane_risk],
            'message': lane_msg
        },
        'collision': {
            'risk': collision_risk,
            'risk_str': risk_levels[collision_risk],
            'message': collision_msg
        }
    }

if __name__ == '__main__':
    # 测试代码
    import time
    
    try:
        # 连接到Carla服务器
        client = carla.Client('localhost', 2000)
        client.set_timeout(10.0)
        world = client.get_world()
        
        # 获取自车
        ego_vehicle = None
        for actor in world.get_actors():
            if actor.type_id.startswith('vehicle.') and actor.attributes.get('role_name') == 'ego':
                ego_vehicle = actor
                break
        
        if not ego_vehicle:
            print("未找到自车，请确保车辆已生成并设置role_name为'ego'")
            exit(1)
        
        print("开始安全检测...")
        while True:
            result = safety_judge(ego_vehicle, world)
            print(f"\n综合风险: {result['overall_risk_str']}")
            print(f"闯红灯检测: {result['red_light']['risk_str']} - {result['red_light']['message']}")
            print(f"车道保持: {result['lane_keeping']['risk_str']} - {result['lane_keeping']['message']}")
            print(f"碰撞风险: {result['collision']['risk_str']} - {result['collision']['message']}")
            time.sleep(1.0)
            
    except KeyboardInterrupt:
        print("检测终止")
    except Exception as e:
        print(f"错误: {e}")
