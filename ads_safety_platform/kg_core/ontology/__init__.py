# KG Core Ontology Module
# 复用 SpatioTemporalKG 的本体定义

from .types import (
    EntityType,
    SceneRelationType,
    BehaviorRelationType,
    RuleRelationType,
    CrossLayerRelationType,
    NODE_LABELS,
    entity_type_from_label,
    relation_type_from_value,
)

from .entity import BaseEntity, BaseRelation

__all__ = [
    "EntityType",
    "SceneRelationType",
    "BehaviorRelationType",
    "RuleRelationType",
    "CrossLayerRelationType",
    "NODE_LABELS",
    "entity_type_from_label",
    "relation_type_from_value",
    "BaseEntity",
    "BaseRelation",
]