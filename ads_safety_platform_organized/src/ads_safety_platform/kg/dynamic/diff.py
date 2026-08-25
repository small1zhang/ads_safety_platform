"""
差分图计算 (v3 §5.2)
复用 SpatioTemporalKG 的差分算法
"""
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Set, Tuple


@dataclass
class DiffSet:
    """差分集合"""
    added: Set[str] = field(default_factory=set)
    removed: Set[str] = field(default_factory=set)
    unchanged: Set[str] = field(default_factory=set)


@dataclass
class DeltaGraph:
    """
    差分图 Δg_t
    
    Δg_t := ⟨Δ_ℰ(t), Δ_𝒜(t), Δ_ℛ(t), ℰ_rule(t)⟩
    
    | 分量 | 含义 | 结构 |
    |------|------|------|
    | Δ_ℰ(t) | 实体级差分 | DiffSet(added, removed, unchanged) |
    | Δ_𝒜(t) | 属性级差分 | {(eid, attr): (old_val, new_val)} |
    | Δ_ℛ(t) | 关系级差分 | DiffSet(added, removed, unchanged) |
    | ℰ_rule(t) | 规则事件 | SafetyViolation 列表 |
    """
    frame_id: int = 0
    entities: DiffSet = field(default_factory=DiffSet)
    attributes: Dict[Tuple[str, str], Tuple[Any, Any]] = field(default_factory=dict)
    relations: DiffSet = field(default_factory=DiffSet)
    rule_events: List[Dict[str, Any]] = field(default_factory=list)
    
    def is_empty(self) -> bool:
        """检查差分图是否为空"""
        return (len(self.entities.added) == 0 and
                len(self.entities.removed) == 0 and
                len(self.attributes) == 0 and
                len(self.relations.added) == 0 and
                len(self.relations.removed) == 0 and
                len(self.rule_events) == 0)
    
    def summary(self) -> str:
        """生成差分图摘要"""
        return (
            f"Δg_{self.frame_id}: "
            f"+{len(self.entities.added)}/-{len(self.entities.removed)} entities, "
            f"{len(self.attributes)} attr changes, "
            f"+{len(self.relations.added)}/-{len(self.relations.removed)} relations, "
            f"{len(self.rule_events)} rule events"
        )


def compute_delta(
    prev_entities: Dict[str, Dict[str, Any]],
    curr_entities: Dict[str, Dict[str, Any]],
    prev_relations: Dict[str, Dict[str, Any]] = None,
    curr_relations: Dict[str, Dict[str, Any]] = None,
    frame_id: int = 0,
) -> DeltaGraph:
    """
    计算两帧之间的差分图
    
    参数:
        prev_entities: 上一帧的实体 {entity_id: entity_data}
        curr_entities: 当前帧的实体 {entity_id: entity_data}
        prev_relations: 上一帧的关系 {relation_id: relation_data}
        curr_relations: 当前帧的关系 {relation_id: relation_data}
        frame_id: 当前帧 ID
    
    返回:
        DeltaGraph 差分图
    """
    if prev_relations is None:
        prev_relations = {}
    if curr_relations is None:
        curr_relations = {}
    
    delta = DeltaGraph(frame_id=frame_id)
    
    # 1. 实体级差分
    prev_eids = set(prev_entities.keys())
    curr_eids = set(curr_entities.keys())
    
    delta.entities.added = curr_eids - prev_eids
    delta.entities.removed = prev_eids - curr_eids
    delta.entities.unchanged = curr_eids & prev_eids
    
    # 2. 属性级差分
    for eid in delta.entities.unchanged:
        prev_attrs = prev_entities[eid]
        curr_attrs = curr_entities[eid]
        
        # 比较所有属性
        all_attrs = set(prev_attrs.keys()) | set(curr_attrs.keys())
        for attr in all_attrs:
            prev_val = prev_attrs.get(attr)
            curr_val = curr_attrs.get(attr)
            
            # 使用近似比较（浮点数）
            if isinstance(prev_val, float) and isinstance(curr_val, float):
                if abs(prev_val - curr_val) > 1e-6:
                    delta.attributes[(eid, attr)] = (prev_val, curr_val)
            elif prev_val != curr_val:
                delta.attributes[(eid, attr)] = (prev_val, curr_val)
    
    # 3. 关系级差分
    prev_rids = set(prev_relations.keys())
    curr_rids = set(curr_relations.keys())
    
    delta.relations.added = curr_rids - prev_rids
    delta.relations.removed = prev_rids - curr_rids
    delta.relations.unchanged = curr_rids & prev_rids
    
    return delta