"""
增量更新引擎 (v3 §5.1)
复用 SpatioTemporalKG 的增量更新流程
"""
from typing import Dict, Any, Optional

from .diff import DeltaGraph, DiffSet, compute_delta
from .version import VersionManager


class IncrementalEngine:
    """
    增量图更新引擎
    
    复用 STKG 的五步流程：
    1. recv - 接收并校验（数值属性防污染）
    2. diff - 计算三集合差分 + 属性变化
    3. patch - 应用生命周期转移 + 属性版本化
    4. eval - 规则引擎评估（由 RuleEnforcer 处理）
    5. writeback - 保存 prev_frame, 返回 Δg_t
    """
    
    def __init__(self):
        self.version_manager = VersionManager()
        self.prev_entities: Dict[str, Dict[str, Any]] = {}
        self.prev_relations: Dict[str, Dict[str, Any]] = {}
        self.current_frame_id: int = 0
    
    def process_frame(self, frame_data: Dict[str, Any]) -> DeltaGraph:
        """
        处理单帧数据，返回增量图
        
        参数:
            frame_data: 当前帧的提取数据，包含:
                - vehicles: 车辆列表
                - pedestrians: 行人列表
                - traffic_lights: 交通灯列表
                - relations: 关系列表（可选）
                - rule_events: 规则事件列表（可选）
        
        返回:
            DeltaGraph 差分图
        """
        # 1. 接收并校验
        validated_data = self._validate(frame_data)
        
        # 转换为字典格式
        curr_entities = self._to_entity_dict(validated_data)
        curr_relations = self._to_relation_dict(validated_data.get('relations', []))
        
        # 2. 计算差分
        delta = compute_delta(
            prev_entities=self.prev_entities,
            curr_entities=curr_entities,
            prev_relations=self.prev_relations,
            curr_relations=curr_relations,
            frame_id=self.current_frame_id,
        )
        
        # 3. 应用补丁（更新版本）
        self._apply_patch(delta, curr_entities)
        
        # 4. 规则评估（由外部 RuleEnforcer 处理）
        
        # 5. 保存当前帧
        self.prev_entities = curr_entities
        self.prev_relations = curr_relations
        self.current_frame_id += 1
        
        return delta
    
    def _validate(self, frame_data: Dict[str, Any]) -> Dict[str, Any]:
        """数据校验"""
        # 检查必需字段
        validated = frame_data.copy()
        
        # 数值属性防污染
        for vehicle in validated.get('vehicles', []):
            vehicle['speed'] = max(0, float(vehicle.get('speed', 0)))
            vehicle['x'] = float(vehicle.get('x', 0))
            vehicle['y'] = float(vehicle.get('y', 0))
            vehicle['vx'] = float(vehicle.get('vx', 0))
            vehicle['vy'] = float(vehicle.get('vy', 0))
        
        for pedestrian in validated.get('pedestrians', []):
            pedestrian['speed'] = max(0, float(pedestrian.get('speed', 0)))
            pedestrian['x'] = float(pedestrian.get('x', 0))
            pedestrian['y'] = float(pedestrian.get('y', 0))
        
        return validated
    
    def _to_entity_dict(self, frame_data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """将帧数据转换为实体字典"""
        entities = {}
        
        for v in frame_data.get('vehicles', []):
            eid = v.get('entity_id', f"veh_{id(v)}")
            entities[eid] = v
        
        for p in frame_data.get('pedestrians', []):
            eid = p.get('entity_id', f"ped_{id(p)}")
            entities[eid] = p
        
        for tl in frame_data.get('traffic_lights', []):
            eid = tl.get('entity_id', f"tl_{id(tl)}")
            entities[eid] = tl
        
        return entities
    
    def _to_relation_dict(self, relations: list) -> Dict[str, Dict[str, Any]]:
        """将关系列表转换为字典"""
        rel_dict = {}
        for rel in relations:
            rid = f"{rel['src_id']}_{rel['relation_type']}_{rel['dst_id']}"
            rel_dict[rid] = rel
        return rel_dict
    
    def _apply_patch(self, delta: DeltaGraph, curr_entities: Dict[str, Dict[str, Any]]):
        """应用差分补丁，更新版本"""
        # 更新属性版本
        for (eid, attr), (old_val, new_val) in delta.attributes.items():
            self.version_manager.record(
                entity_id=eid,
                attribute=attr,
                old_value=old_val,
                new_value=new_val,
                frame_id=delta.frame_id,
            )
        
        # 新增实体的初始版本
        for eid in delta.entities.added:
            if eid in curr_entities:
                entity = curr_entities[eid]
                for attr, value in entity.items():
                    if attr not in ['entity_id', 'entity_type']:
                        self.version_manager.record(
                            entity_id=eid,
                            attribute=attr,
                            old_value=None,
                            new_value=value,
                            frame_id=delta.frame_id,
                        )
    
    def query_entity_history(self, entity_id: str, attribute: str):
        """查询实体属性的历史版本"""
        return self.version_manager.get_version_history(entity_id, attribute)
    
    def query_entity_at_frame(self, entity_id: str, frame_id: int):
        """查询实体在指定帧的所有属性"""
        return self.version_manager.get_entity_attributes(entity_id, frame_id)
    
    def get_current_snapshot(self):
        """获取当前帧的快照"""
        return self.prev_entities.copy()
    
    def reset(self):
        """重置引擎状态"""
        self.version_manager.clear()
        self.prev_entities.clear()
        self.prev_relations.clear()
        self.current_frame_id = 0