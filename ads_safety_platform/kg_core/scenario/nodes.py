"""
场景层节点定义 (v3 §2.3)
复用 SpatioTemporalKG 的场景层实体定义
"""
from typing import Optional, List
from pydantic import Field

from ..ontology.types import EntityType
from ..ontology.entity import BaseEntity


class VehicleEntity(BaseEntity):
    """车辆实体"""
    entity_type: EntityType = EntityType.VEHICLE
    
    # 标识组
    actor_type: str = Field(..., description="CARLA actor 类型")
    role_name: str = Field("npc", description="角色名 (ego/npc)")
    
    # 位置/运动组
    x: float = Field(0.0, description="X 坐标")
    y: float = Field(0.0, description="Y 坐标")
    z: float = Field(0.0, description="Z 坐标")
    speed: float = Field(0.0, ge=0.0, description="速度 (m/s)")
    yaw: float = Field(0.0, description="航向角 (rad)")
    vx: float = Field(0.0, description="X 方向速度")
    vy: float = Field(0.0, description="Y 方向速度")
    
    # 派生计算组
    lane_id: Optional[str] = Field(None, description="当前车道 ID")
    road_id: Optional[str] = Field(None, description="当前道路 ID")
    distance_to_ego: Optional[float] = Field(None, description="距自车距离")
    
    # 物理状态组
    length: float = Field(5.0, description="车身长度")
    width: float = Field(2.0, description="车身宽度")
    throttle: float = Field(0.0, description="油门")
    brake: float = Field(0.0, description="刹车")
    steer: float = Field(0.0, description="转向角")


class PedestrianEntity(BaseEntity):
    """行人实体"""
    entity_type: EntityType = EntityType.PEDESTRIAN
    
    x: float = Field(0.0)
    y: float = Field(0.0)
    z: float = Field(0.0)
    speed: float = Field(0.0, ge=0.0)
    yaw: float = Field(0.0)
    vx: float = Field(0.0)
    vy: float = Field(0.0)
    
    is_on_crosswalk: bool = Field(False, description="是否在人行横道上")
    is_on_sidewalk: bool = Field(False, description="是否在人行道上")
    action: str = Field("standing", description="当前动作")


class TrafficLightEntity(BaseEntity):
    """交通灯实体"""
    entity_type: EntityType = EntityType.TRAFFIC_LIGHT
    
    x: float = Field(0.0)
    y: float = Field(0.0)
    z: float = Field(0.0)
    state: str = Field(..., description="状态: Red/Yellow/Green")
    elapsed_time: float = Field(0.0, description="已持续时间 (s)")
    affected_lane_ids: List[str] = Field(default_factory=list, description="受影响车道列表")


class RoadElementEntity(BaseEntity):
    """道路元素实体"""
    entity_type: EntityType = EntityType.LANE
    
    # 位置/几何
    x: float = Field(0.0)
    y: float = Field(0.0)
    length: float = Field(0.0, description="车道长度")
    width: float = Field(3.7, description="车道宽度")
    
    # 拓扑
    road_id: str = Field(..., description="道路 ID")
    lane_id: str = Field(..., description="车道 ID")
    lane_index: int = Field(0, description="车道索引 (0=最右)")
    lane_type: str = Field("driving", description="车道类型")
    
    # 拓扑连接
    left_lane_id: Optional[str] = Field(None)
    right_lane_id: Optional[str] = Field(None)
    predecessor_id: Optional[str] = Field(None, description="前驱车道")
    successor_id: Optional[str] = Field(None, description="后继车道")
    
    # 标记
    left_lane_marking: str = Field("none", description="左侧标线类型")
    right_lane_marking: str = Field("none", description="右侧标线类型")


class EnvironmentSnapshot(BaseEntity):
    """环境快照节点"""
    entity_type: EntityType = EntityType.ENV_SNAPSHOT
    
    weather: str = Field("Clear", description="天气状况")
    sun_altitude: float = Field(0.0, description="太阳高度角")
    sun_azimuth: float = Field(0.0, description="太阳方位角")
    precipitation: float = Field(0.0, description="降水量")
    precipitation_deposits: float = Field(0.0, description="积水深度")
    wind_intensity: float = Field(0.0, description="风力强度")
    fog_density: float = Field(0.0, description="雾气密度")
    cloudiness: float = Field(0.0, description="云量")
    wetness: float = Field(0.0, description="路面湿度")
    scattering_intensity: float = Field(0.0, description="散射强度")
    
    # 帧信息
    frame_id: int = Field(0, description="帧 ID")
    timestamp: float = Field(0.0, description="时间戳")


class ScenarioSnapshot(BaseEntity):
    """场景快照根节点"""
    entity_type: EntityType = EntityType.SCENE_SNAPSHOT
    
    frame_id: int = Field(0, description="帧 ID")
    timestamp: float = Field(0.0, description="时间戳")
    vehicle_count: int = Field(0, description="车辆数量")
    pedestrian_count: int = Field(0, description="行人数量")
    traffic_light_count: int = Field(0, description="交通灯数量")


class SafetyViolation(BaseEntity):
    """安全违规节点"""
    entity_type: EntityType = EntityType.SAFETY_VIOLATION
    
    rule_code: str = Field(..., description="规则代码")
    severity: str = Field(..., description="严重程度")
    message: str = Field("", description="违规描述")
    evidence: dict = Field(default_factory=dict, description="证据数据")