"""
ROI 滤波器 (v3 §7.1)
复用 SpatioTemporalKG 的 Ego-Centric ROI 策略
"""
import math
from typing import Dict, Any, List, Optional
from dataclasses import dataclass


@dataclass
class ROICategory:
    """ROI 类别配置"""
    front: float = 70.0      # 正前方距离
    rear: float = 30.0       # 后方距离
    side: float = 50.0       # 侧向距离


class EgoCentricROIFilter:
    """
    以自车为中心的 ROI 滤波器
    
    复用 STKG 的差异化半径策略：
    - 正前方 70m（最远检测距离）
    - 后方 30m（后方检测距离）
    - 侧向 50m（侧向检测距离）
    
    对于行人和特殊车辆使用更小的半径
    """
    
    def __init__(self):
        # 默认 ROI 配置
        self.roi_config = {
            'vehicle': ROICategory(front=70.0, rear=30.0, side=50.0),
            'motorcycle': ROICategory(front=50.0, rear=25.0, side=35.0),
            'bicycle': ROICategory(front=50.0, rear=25.0, side=35.0),
            'pedestrian': ROICategory(front=40.0, rear=20.0, side=30.0),
        }
        
        # Ego 信息
        self.ego_position = (0.0, 0.0)
        self.ego_yaw = 0.0
    
    def set_ego(self, position: tuple, yaw: float):
        """设置自车位置和航向"""
        self.ego_position = position
        self.ego_yaw = yaw
    
    def is_in_roi(self, entity: Dict[str, Any]) -> bool:
        """
        检查实体是否在 ROI 内
        
        参数:
            entity: 实体数据（需要包含 x, y 坐标）
        
        返回:
            是否在 ROI 内
        """
        entity_type = self._get_entity_type(entity)
        roi = self.roi_config.get(entity_type, self.roi_config['vehicle'])
        
        # 计算相对位置
        dx = entity['x'] - self.ego_position[0]
        dy = entity['y'] - self.ego_position[1]
        
        # 转换到自车坐标系
        forward = math.cos(self.ego_yaw)
        lateral = math.sin(self.ego_yaw)
        
        longitudinal = dx * forward + dy * lateral
        lateral_distance = -dx * lateral + dy * forward
        
        # 判断是否在 ROI 内
        if longitudinal > 0:
            # 正前方
            return longitudinal < roi.front and abs(lateral_distance) < roi.side
        else:
            # 后方
            return longitudinal > -roi.rear and abs(lateral_distance) < roi.side
    
    def filter_entities(self, entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        过滤实体列表，只保留 ROI 内的实体
        
        参数:
            entities: 实体列表
        
        返回:
            ROI 内的实体列表
        """
        filtered = []
        for entity in entities:
            if self.is_in_roi(entity):
                filtered.append(entity)
        return filtered
    
    def _get_entity_type(self, entity: Dict[str, Any]) -> str:
        """获取实体类型"""
        if 'type_id' in entity:
            type_id = entity['type_id'].lower()
            if 'pedestrian' in type_id or 'walker' in type_id:
                return 'pedestrian'
            elif 'motorcycle' in type_id:
                return 'motorcycle'
            elif 'bicycle' in type_id:
                return 'bicycle'
            else:
                return 'vehicle'
        elif 'role_name' in entity:
            return 'vehicle'
        
        return 'vehicle'
    
    def get_roi_stats(self) -> Dict[str, Any]:
        """获取 ROI 配置统计"""
        return {
            'vehicle': {
                'front': self.roi_config['vehicle'].front,
                'rear': self.roi_config['vehicle'].rear,
                'side': self.roi_config['vehicle'].side,
            },
            'pedestrian': {
                'front': self.roi_config['pedestrian'].front,
                'rear': self.roi_config['pedestrian'].rear,
                'side': self.roi_config['pedestrian'].side,
            },
        }