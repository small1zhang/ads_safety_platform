"""
行为层节点定义 (v3 §3.2)
复用 SpatioTemporalKG 的行为层实体定义
"""
from typing import List, Optional
from pydantic import Field

from ..ontology.types import EntityType
from ..ontology.entity import BaseEntity


class ManeuverNode(BaseEntity):
    """机动行为节点 (单实体持续行为)"""
    entity_type: EntityType = EntityType.MANEUVER
    
    actor_id: str = Field(..., description="执行该行为的实体 ID")
    maneuver_type: str = Field(..., description="行为类型")
    start_frame: int = Field(0, description="行为开始帧")
    end_frame: Optional[int] = Field(None, description="行为结束帧 (None 表示持续中)")
    
    # 行为参数
    duration: float = Field(0.0, description="持续时间 (s)")
    intensity: float = Field(0.0, description="强度 (0-1)")


class InteractionEvent(BaseEntity):
    """交互事件节点 (多实体交互)"""
    entity_type: EntityType = EntityType.INTERACTION_EVENT
    
    src_actor_id: str = Field(..., description="源实体 ID")
    dst_actor_id: str = Field(..., description="目标实体 ID")
    interaction_type: str = Field(..., description="交互类型")
    
    # 交互参数
    relative_distance: float = Field(0.0, description="相对距离")
    relative_speed: float = Field(0.0, description="相对速度")
    time_to_collision: Optional[float] = Field(None, description="碰撞时间 (TTC)")
    
    # 空间关系
    longitudinal_offset: float = Field(0.0, description="纵向偏移")
    lateral_offset: float = Field(0.0, description="横向偏移")