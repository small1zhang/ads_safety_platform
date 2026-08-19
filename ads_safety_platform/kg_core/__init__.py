"""
KG Core - 知识图谱核心模块
用于增强自动驾驶安全平台的时空语义理解能力
"""

__version__ = "0.1.0"
__author__ = "Zhang Haibing"

from .ontology import (
    EntityType,
    SceneRelationType,
    BehaviorRelationType,
    RuleRelationType,
    CrossLayerRelationType,
    BaseEntity,
    BaseRelation,
)

__all__ = [
    "EntityType",
    "SceneRelationType",
    "BehaviorRelationType",
    "RuleRelationType",
    "CrossLayerRelationType",
    "BaseEntity",
    "BaseRelation",
]