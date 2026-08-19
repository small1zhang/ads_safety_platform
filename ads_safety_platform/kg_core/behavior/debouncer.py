"""
防抖状态机 (v3 §3.6)
复用 SpatioTemporalKG 的防抖算法
"""
from enum import Enum
from typing import Dict, Tuple


class DebounceState(Enum):
    """防抖状态"""
    INACTIVE = 0     # 未激活
    PENDING = 1      # 待激活（条件满足，等待进入阈值）
    ACTIVE = 2       # 已激活
    EXITING = 3      # 退出中（条件不满足，等待消失阈值）


class RelationDebouncer:
    """
    关系防抖状态机
    
    复用 STKG 的进入/消失阈值机制：
    - 连续 N 帧满足条件 → 进入 ACTIVE
    - 连续 M 帧不满足条件 → 退出到 INACTIVE
    """
    
    # 默认阈值配置
    DEFAULT_THRESHOLDS = {
        'following': (3, 3),           # 进入3帧，消失3帧
        'approaching': (3, 3),
        'overtaking': (5, 3),          # 进入更稳健
        'changing_lane': (2, 2),
        'wrong_side_meeting': (1, 1),  # 瞬时反应
        'opposite_direction': (1, 1),
        'yielding_to': (3, 3),
        'approaching_pedestrian': (3, 3),
    }
    
    def __init__(self, custom_thresholds: Dict[str, Tuple[int, int]] = None):
        """
        初始化防抖器
        
        参数:
            custom_thresholds: 自定义阈值配置
        """
        self.states: Dict[str, DebounceState] = {}
        self.counters: Dict[str, int] = {}
        self.thresholds = self.DEFAULT_THRESHOLDS.copy()
        if custom_thresholds:
            self.thresholds.update(custom_thresholds)
    
    def update(self, relation_key: str, 
               condition_met: bool,
               enter_threshold: int = None,
               exit_threshold: int = None) -> bool:
        """
        更新防抖状态
        
        参数:
            relation_key: 关系唯一标识（如 "veh_1_following_veh_2"）
            condition_met: 当前帧条件是否满足
            enter_threshold: 进入阈值（默认从配置读取）
            exit_threshold: 消失阈值
        
        返回:
            该关系是否应被激活
        """
        # 获取阈值
        # 从 relation_key 中提取关系类型
        relation_type = relation_key.split('_')[0] if '_' in relation_key else 'default'
        enter_t, exit_t = self.thresholds.get(relation_type, (3, 3))
        
        if enter_threshold:
            enter_t = enter_threshold
        if exit_threshold:
            exit_t = exit_threshold
        
        # 获取当前状态
        current_state = self.states.get(relation_key, DebounceState.INACTIVE)
        counter = self.counters.get(relation_key, 0)
        
        # 状态转移
        new_state = current_state
        new_counter = counter
        
        if condition_met:
            if current_state == DebounceState.INACTIVE:
                new_counter = 1
                new_state = DebounceState.PENDING
            elif current_state == DebounceState.PENDING:
                new_counter += 1
                if new_counter >= enter_t:
                    new_state = DebounceState.ACTIVE
                    new_counter = 0
            elif current_state == DebounceState.ACTIVE:
                new_counter = 0  # 保持活跃
        else:
            if current_state == DebounceState.ACTIVE:
                new_counter = 1
                new_state = DebounceState.EXITING
            elif current_state == DebounceState.EXITING:
                new_counter += 1
                if new_counter >= exit_t:
                    new_state = DebounceState.INACTIVE
                    new_counter = 0
            elif current_state == DebounceState.PENDING:
                new_state = DebounceState.INACTIVE
                new_counter = 0
        
        # 更新状态
        self.states[relation_key] = new_state
        self.counters[relation_key] = new_counter
        
        return new_state == DebounceState.ACTIVE
    
    def get_state(self, relation_key: str) -> DebounceState:
        """获取指定关系的当前状态"""
        return self.states.get(relation_key, DebounceState.INACTIVE)
    
    def get_active_relations(self) -> list[str]:
        """获取所有激活的关系"""
        return [k for k, v in self.states.items() if v == DebounceState.ACTIVE]
    
    def reset(self):
        """重置所有状态"""
        self.states.clear()
        self.counters.clear()
    
    def reset_relation(self, relation_key: str):
        """重置指定关系的状态"""
        self.states.pop(relation_key, None)
        self.counters.pop(relation_key, None)