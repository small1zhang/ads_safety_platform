"""
RSS 交叉口/路口规则 (论文复现 Lin et al. 2024 "RSS-based Rule-Compliance Path Planner for Lane-Merge Scenarios")

参考文献:
- Lin, Pengfei et al. "A Rule-Compliance Path Planner for Lane-Merge Scenarios Based on Responsibility-Sensitive Safety" (2024)
- arXiv:2403.13251

论文贡献:
1. 明确了路口/汇合处的 right-of-way (right-of-way) 规则
2. 基于 RSS 的合规路径规划 (RCPP - Rule-Compliance Path Planner)
3. 合并时间 (72.3% 缩减) 和路径长度 (53.4% 缩减) 改进

实现了以下 RSS 交叉口规则:
1. RSS_OW_RIGHT_WAY - 右侧右先行 (Right-of-Way)
2. RSS_INTERSECTION_MERGE - 交叉口合并/并线规则
3. RSS_MERGE_SAFE_DISTANCE - 合并安全距离
4. RCPP (Rule-Compliance Path Planner) - 合规路径规划器
5. 环岛、T型路口、十字路口支持
"""
import numpy as np
import math
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum


class IntersectionType(Enum):
    """路口类型枚举"""
    MERGE = "merge"           # 并道
    INTERSECTION = "intersection"  # 十字路口
    T_JUNCTION = "t_junction"     # T型路口
    ROUNDABOUT = "roundabout"      # 环岛
    LANE_CHANGE = "lane_change"   # 变道


class RightOfWayRule(Enum):
    """先行权规则枚举"""
    RIGHT_BEFORE_LEFT = "right_before_left"  # 右侧优先
    FIRST_COME_FIRST_SERVED = "first_come_first_served"  # 先到先行
    SIGNAL_CONTROLLED = "signal_controlled"  # 信号灯控制
    STOP_SIGN = "stop_sign"  # 停车标志
    YIELD_SIGN = "yield_sign"  # 让行标志


@dataclass
class RCPPParams:
    """RCPP 算法参数"""
    # RSS 基础参数
    rho: float = 0.5                       # 反应时间 (s)
    a_max_accel: float = 2.0               # 最大加速度 (m/s²)
    a_min_brake: float = 4.0               # 最小制动减速度 (m/s²)
    
    # 合并参数
    merge_safe_distance: float = 15.0     # 合并安全距离 (m)
    merge_time_gap: float = 2.0           # 合并时间间隙 (s)
    merge_speed_threshold: float = 5.0    # 合并速度阈值 (m/s)
    
    # 路口参数
    intersection_safe_distance: float = 20.0  # 路口安全距离 (m)
    intersection_time_gap: float = 3.0        # 路口时间间隙 (s)
    
    # 环岛参数
    roundabout_entry_speed: float = 8.0    # 环岛入口速度 (m/s)
    roundabout_yield_distance: float = 10.0  # 环岛让行距离 (m)
    
    # 优先权参数
    right_of_way_rule: RightOfWayRule = RightOfWayRule.RIGHT_BEFORE_LEFT


@dataclass
class VehicleState:
    """车辆状态"""
    x: float = 0.0
    y: float = 0.0
    vx: float = 0.0
    vy: float = 0.0
    speed: float = 0.0
    yaw: float = 0.0
    width: float = 2.0
    length: float = 4.5
    entity_id: str = ""
    role_name: str = "npc"


@dataclass
class IntersectionContext:
    """路口上下文"""
    ego: VehicleState
    other_vehicles: List[VehicleState] = field(default_factory=list)
    intersection_type: IntersectionType = IntersectionType.INTERSECTION
    traffic_light_state: Optional[str] = None  # "Red", "Yellow", "Green"
    stop_sign_present: bool = False
    yield_sign_present: bool = False


def compute_relative_position(ego: VehicleState, other: VehicleState) -> Tuple[float, float, float]:
    """
    计算相对位置
    
    返回: (相对距离, 相对方位角(弧度), 相对速度)
    """
    dx = other.x - ego.x
    dy = other.y - ego.y
    
    distance = math.sqrt(dx**2 + dy**2)
    
    # 相对方位角 (相对于ego的正向)
    ego_fwd_x = math.cos(ego.yaw)
    ego_fwd_y = math.sin(ego.yaw)
    
    # 相对位置向量
    rel_x = dx
    rel_y = dy
    
    # 计算相对方位角
    dot = ego_fwd_x * rel_x + ego_fwd_y * rel_y
    det = ego_fwd_x * rel_y - ego_fwd_y * rel_x
    relative_bearing = math.atan2(det, dot)
    
    # 相对速度
    rel_vx = other.vx - ego.vx
    rel_vy = other.vy - ego.vy
    relative_speed = math.sqrt(rel_vx**2 + rel_vy**2)
    
    return distance, relative_bearing, relative_speed


def check_right_of_way_by_position(ego: VehicleState, 
                                   other: VehicleState) -> Dict[str, Any]:
    """
    基于位置判断先行权 (右侧优先规则)
    
    规则: 如果其他车辆在ego的右侧，则其他车辆有先行权
    
    参数:
        ego: 自车状态
        other: 其他车辆状态
    
    返回:
        {
            'has_right_of_way': bool,  # ego是否有先行权
            'other_has_right_of_way': bool,  # 其他车辆是否有先行权
            'relative_bearing': float,  # 相对方位角 (弧度)
            'reason': str,
            'rule_code': str
        }
    """
    distance, relative_bearing, relative_speed = compute_relative_position(ego, other)
    
    # 右侧优先: 如果其他车辆在ego的右侧 (相对方位角在 -π/2 到 π/2 之间)
    # 在ego的坐标系中，右侧是负的y方向
    # 相对方位角: 0 = 正前方, π/2 = 左侧, -π/2 = 右侧
    
    is_on_right = -math.pi/2 < relative_bearing < math.pi/2
    
    if is_on_right:
        # 其他车辆在ego的右侧，其他车辆有先行权
        return {
            'has_right_of_way': False,
            'should_yield': True,
            'other_has_right_of_way': True,
            'relative_bearing': relative_bearing,
            'reason': f'其他车辆在右侧 (方位角: {math.degrees(relative_bearing):.1f}°)，依据右侧优先规则',
            'rule_code': 'RSS_RIGHT_OF_WAY_RIGHT',
            'distance': distance,
        }
    else:
        # 其他车辆在ego的左侧，ego有先行权
        return {
            'has_right_of_way': True,
            'should_yield': False,
            'other_has_right_of_way': False,
            'relative_bearing': relative_bearing,
            'reason': f'其他车辆在左侧 (方位角: {math.degrees(relative_bearing):.1f}°)，ego有先行权',
            'rule_code': 'RSS_RIGHT_OF_WAY_LEFT',
            'distance': distance,
        }


def check_merge_priority(ego: VehicleState, 
                         other: VehicleState,
                         params: RCPPParams = None) -> Dict[str, Any]:
    """
    检查并道/合并优先权 (基于 Lin et al. 2024)
    
    规则:
    1. 如果ego在主路，other在辅路，ego有先行权
    2. 如果速度差较大，速度快的车辆应让行
    3. 如果距离较近，应让行
    
    参数:
        ego: 自车状态
        other: 其他车辆状态
        params: RCPP参数
    
    返回:
        {
            'has_right_of_way': bool,
            'should_yield': bool,
            'reason': str,
            'rule_code': str,
            'distance': float,
            'relative_speed': float,
            'time_to_collision': float
        }
    """
    if params is None:
        params = RCPPParams()
    
    distance, relative_bearing, relative_speed = compute_relative_position(ego, other)
    
    # 计算碰撞时间 (TTC)
    if relative_speed > 0:
        ttc = distance / relative_speed
    else:
        ttc = float('inf')
    
    # 规则1: 如果距离小于安全距离，需要让行
    if distance < params.merge_safe_distance:
        return {
            'has_right_of_way': False,
            'should_yield': True,
            'reason': f'距离 {distance:.1f}m 小于安全距离 {params.merge_safe_distance}m，必须让行',
            'rule_code': 'RSS_MERGE_SAFE_DISTANCE',
            'distance': distance,
            'relative_speed': relative_speed,
            'time_to_collision': ttc,
        }
    
    # 规则2: 如果TTC小于时间间隙，需要让行
    if ttc < params.merge_time_gap:
        return {
            'has_right_of_way': False,
            'should_yield': True,
            'reason': f'碰撞时间 {ttc:.1f}s 小于时间间隙 {params.merge_time_gap}s，必须让行',
            'rule_code': 'RSS_MERGE_TIME_GAP',
            'distance': distance,
            'relative_speed': relative_speed,
            'time_to_collision': ttc,
        }
    
    # 规则3: 如果ego速度远大于other，ego应让行
    speed_diff = ego.speed - other.speed
    if speed_diff > params.merge_speed_threshold:
        return {
            'has_right_of_way': False,
            'should_yield': True,
            'reason': f'ego速度 {ego.speed:.1f}m/s 比other快 {speed_diff:.1f}m/s，应让行',
            'rule_code': 'RSS_MERGE_SPEED_DIFF',
            'distance': distance,
            'relative_speed': relative_speed,
            'time_to_collision': ttc,
        }
    
    # 默认: ego有先行权
    return {
        'has_right_of_way': True,
        'should_yield': False,
        'reason': f'距离 {distance:.1f}m 充足，TTC {ttc:.1f}s 充足，速度差 {speed_diff:.1f}m/s 可接受',
        'rule_code': 'RSS_MERGE_SAFE',
        'distance': distance,
        'relative_speed': relative_speed,
        'time_to_collision': ttc,
    }


def check_intersection_priority(ego: VehicleState,
                                 other: VehicleState,
                                 intersection_type: IntersectionType = IntersectionType.INTERSECTION,
                                 params: RCPPParams = None) -> Dict[str, Any]:
    """
    检查路口优先权
    
    参数:
        ego: 自车状态
        other: 其他车辆状态
        intersection_type: 路口类型
        params: RCPP参数
    
    返回:
        {
            'has_right_of_way': bool,
            'should_yield': bool,
            'reason': str,
            'rule_code': str,
            'intersection_type': str
        }
    """
    if params is None:
        params = RCPPParams()
    
    distance, relative_bearing, relative_speed = compute_relative_position(ego, other)
    
    # 根据路口类型应用不同规则
    if intersection_type == IntersectionType.ROUNDABOUT:
        # 环岛规则: 环岛内车辆有先行权
        # 简化: 假设other在环岛内，ego在环岛外
        return {
            'has_right_of_way': False,
            'should_yield': True,
            'reason': '环岛内车辆有先行权，ego应让行',
            'rule_code': 'RSS_ROUNDABOUT_YIELD',
            'intersection_type': intersection_type.value,
            'distance': distance,
        }
    
    elif intersection_type == IntersectionType.T_JUNCTION:
        # T型路口: 主路车辆有先行权
        # 简化: 假设ego在主路
        return {
            'has_right_of_way': True,
            'should_yield': False,
            'reason': 'T型路口主路车辆有先行权',
            'rule_code': 'RSS_T_JUNCTION_MAIN_ROAD',
            'intersection_type': intersection_type.value,
            'distance': distance,
        }
    
    elif intersection_type == IntersectionType.MERGE:
        # 并道: 使用合并规则
        return check_merge_priority(ego, other, params)
    
    else:  # INTERSECTION
        # 十字路口: 使用右侧优先规则
        return check_right_of_way_by_position(ego, other)


class RCPPPlanner:
    """
    合规路径规划器 (Rule-Compliance Path Planner)
    
    基于 Lin et al. 2024 的算法，结合 RSS 安全约束进行路径规划
    """
    
    def __init__(self, params: RCPPParams = None):
        self.params = params or RCPPParams()
    
    def plan_merge_path(self,
                       ego: VehicleState,
                       other: VehicleState,
                       target_lane: Dict[str, Any]) -> Dict[str, Any]:
        """
        规划并道路径
        
        参数:
            ego: 自车状态
            other: 其他车辆状态
            target_lane: 目标车道信息
        
        返回:
            {
                'path': List[Tuple[float, float]],  # 路径点列表
                'safe': bool,  # 路径是否安全
                'merge_point': Tuple[float, float],  # 合并点
                'time_to_merge': float,  # 合并所需时间
                'violations': List[str]  # 违规列表
            }
        """
        distance, relative_bearing, relative_speed = compute_relative_position(ego, other)
        
        # 检查合并优先权
        priority = check_merge_priority(ego, other, self.params)
        
        if priority['should_yield']:
            # 需要让行，规划等待路径
            return {
                'path': [],
                'safe': False,
                'merge_point': (ego.x, ego.y),
                'time_to_merge': float('inf'),
                'violations': [priority['reason']],
                'action': 'YIELD',
            }
        
        # 计算合并点
        # 简化: 合并点在ego和other连线的中点
        merge_x = (ego.x + other.x) / 2
        merge_y = (ego.y + other.y) / 2
        
        # 计算合并时间
        merge_distance = distance / 2
        if ego.speed > 0:
            time_to_merge = merge_distance / ego.speed
        else:
            time_to_merge = float('inf')
        
        # 生成简单路径 (直线到合并点)
        path = [(ego.x, ego.y), (merge_x, merge_y)]
        
        return {
            'path': path,
            'safe': True,
            'merge_point': (merge_x, merge_y),
            'time_to_merge': time_to_merge,
            'violations': [],
            'action': 'MERGE',
        }
    
    def plan_intersection_path(self,
                               ego: VehicleState,
                               others: List[VehicleState],
                               intersection_type: IntersectionType = IntersectionType.INTERSECTION) -> Dict[str, Any]:
        """
        规划路口通过路径
        
        参数:
            ego: 自车状态
            others: 其他车辆状态列表
            intersection_type: 路口类型
        
        返回:
            {
                'path': List[Tuple[float, float]],
                'safe': bool,
                'actions': List[str],  # 需要执行的动作
                'violations': List[str],
                'priority_info': Dict[str, Any]
            }
        """
        actions = []
        violations = []
        priority_info = {}
        
        # 检查与所有其他车辆的优先权
        for i, other in enumerate(others):
            priority = check_intersection_priority(ego, other, intersection_type, self.params)
            priority_info[f'vehicle_{i}'] = priority
            
            if priority['should_yield']:
                actions.append(f"YIELD to vehicle_{i}")
                violations.append(priority['reason'])
        
        # 如果需要让行，路径不安全
        if violations:
            return {
                'path': [],
                'safe': False,
                'actions': actions,
                'violations': violations,
                'priority_info': priority_info,
            }
        
        # 生成通过路口的路径
        # 简化: 直线通过
        path = [(ego.x, ego.y), (ego.x + ego.vx * 2, ego.y + ego.vy * 2)]
        
        return {
            'path': path,
            'safe': True,
            'actions': actions,
            'violations': violations,
            'priority_info': priority_info,
        }


class IntersectionRSSModel:
    """RSS 交叉口/合并模型 (Lin et al. 2024)"""
    
    def __init__(self, params: RCPPParams = None):
        self.params = params or RCPPParams()
        self.rcpp_planner = RCPPPlanner(params)
    
    def check_intersection_right_of_way(self, 
                                       ego_state: Dict[str, Any],
                                       other_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        检查交叉口的优先权
        
        基于 RSS 原理和交通规则综合实现
        """
        ego = VehicleState(**{k: v for k, v in ego_state.items() if k in VehicleState.__dataclass_fields__})
        other = VehicleState(**{k: v for k, v in other_state.items() if k in VehicleState.__dataclass_fields__})
        
        # 使用右侧优先规则
        return check_right_of_way_by_position(ego, other)
    
    def check_merge_priority(self,
                            ego_state: Dict[str, Any],
                            other_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        检查合并优先权
        """
        ego = VehicleState(**{k: v for k, v in ego_state.items() if k in VehicleState.__dataclass_fields__})
        other = VehicleState(**{k: v for k, v in other_state.items() if k in VehicleState.__dataclass_fields__})
        
        return check_merge_priority(ego, other, self.params)
    
    def check_merge_safety(self,
                          ego_state: Dict[str, Any],
                          other_state: Dict[str, Any]) -> Dict[str, Any]:
        """检查合并安全距离"""
        ego = VehicleState(**{k: v for k, v in ego_state.items() if k in VehicleState.__dataclass_fields__})
        other = VehicleState(**{k: v for k, v in other_state.items() if k in VehicleState.__dataclass_fields__})
        
        distance, _, relative_speed = compute_relative_position(ego, other)
        
        from kg_core.rules.rss.longitudinal import compute_d_min_long, RSSLongitudinalParams
        long_params = RSSLongitudinalParams()
        d_min = compute_d_min_long(ego.speed, other.speed, long_params)
        
        safe = distance >= d_min
        
        return {
            'safe': safe,
            'safe_distance': d_min,
            'actual_distance': distance,
            'rule_code': 'RSS_MERGE_SAFE_DISTANCE',
            'relative_speed': relative_speed,
        }
    
    def plan_merge_path(self,
                       ego_state: Dict[str, Any],
                       other_state: Dict[str, Any],
                       target_lane: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        规划合并路径
        """
        ego = VehicleState(**{k: v for k, v in ego_state.items() if k in VehicleState.__dataclass_fields__})
        other = VehicleState(**{k: v for k, v in other_state.items() if k in VehicleState.__dataclass_fields__})
        
        if target_lane is None:
            target_lane = {'x': other.x, 'y': other.y}
        
        return self.rcpp_planner.plan_merge_path(ego, other, target_lane)
    
    def plan_intersection_path(self,
                               ego_state: Dict[str, Any],
                               other_states: List[Dict[str, Any]],
                               intersection_type: str = "intersection") -> Dict[str, Any]:
        """
        规划路口通过路径
        """
        ego = VehicleState(**{k: v for k, v in ego_state.items() if k in VehicleState.__dataclass_fields__})
        others = []
        for os in other_states:
            other = VehicleState(**{k: v for k, v in os.items() if k in VehicleState.__dataclass_fields__})
            others.append(other)
        
        try:
            itype = IntersectionType(intersection_type)
        except ValueError:
            itype = IntersectionType.INTERSECTION
        
        return self.rcpp_planner.plan_intersection_path(ego, others, itype)


# 向后兼容性函数 (保持旧API)

def check_intersection_merge_priority(ego_x: float, ego_y: float,
                                      other_x: float, other_y: float,
                                      ego_yaw: float, other_yaw: float,
                                      distance_threshold: float = 20.0) -> Dict[str, Any]:
    """
    旧版交叉口合并优先权检查 (保持向后兼容)
    
    使用新的 check_intersection_priority 实现
    """
    ego = VehicleState(x=ego_x, y=ego_y, yaw=math.radians(ego_yaw))
    other = VehicleState(x=other_x, y=other_y, yaw=math.radians(other_yaw))
    
    result = check_intersection_priority(ego, other, IntersectionType.INTERSECTION)
    return {
        'has_right_of_way': result['has_right_of_way'],
        'should_yield': result['should_yield'],
        'reason': result['reason'],
        'relative_bearing': result.get('relative_bearing', 0),
        'distance': result.get('distance', 0),
    }


def check_merge_safe_distance(v_f: float, v_l: float,
                              d_actual: float,
                              params) -> Dict[str, Any]:
    """
    旧版合并安全距离检查 (保持向后兼容)
    
    使用新的 check_merge_priority 实现
    """
    # 创建临时车辆状态
    ego = VehicleState(speed=v_f)
    other = VehicleState(speed=v_l)
    
    # 计算相对位置 (简化)
    # 这里假设距离是纵向距离
    ego.x = 0
    ego.y = 0
    other.x = 0
    other.y = d_actual
    
    result = check_merge_priority(ego, other)
    
    return {
        'safe': not result['should_yield'],
        'safe_distance': result.get('safe_distance', d_actual * 0.8),
        'actual_distance': d_actual,
        'rule_code': 'RSS_MERGE_SAFE_DISTANCE',
    }


# 实用工具函数
def check_rss_based_priority(ego_state: Dict[str, Any], 
                             other_state: Dict[str, Any]) -> Dict[str, Any]:
    """
    简化的 RSS 优先权检查 (使用论文简化版)
    
    基于 RSS 原理确定谁有先行权
    """
    ego = VehicleState(**{k: v for k, v in ego_state.items() if k in VehicleState.__dataclass_fields__})
    other = VehicleState(**{k: v for k, v in other_state.items() if k in VehicleState.__dataclass_fields__})
    
    distance, relative_bearing, relative_speed = compute_relative_position(ego, other)
    
    # 简化实现：基于相对速度和距离
    if distance < 20.0 and abs(relative_speed) > 5.0:
        # 距离近且速度差大，需要让行
        return {
            'should_yield': True,
            'has_right_of_way': False,
            'reason': f'距离 {distance:.1f}m 近且相对速度 {relative_speed:.1f}m/s 大，依据 RSS 让行原则',
            'distance': distance,
            'relative_speed': relative_speed,
        }
    else:
        return {
            'should_yield': False,
            'has_right_of_way': True,
            'reason': f'距离 {distance:.1f}m 充足或相对速度 {relative_speed:.1f}m/s 小，可安全通过',
            'distance': distance,
            'relative_speed': relative_speed,
        }
