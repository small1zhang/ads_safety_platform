"""
Entity 基类 (v3 §1.8.2, §1.10)
复用 SpatioTemporalKG 的实体基类定义
"""
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

from .types import EntityType, NODE_LABELS


class BaseEntity(BaseModel):
    """所有实体的基类"""
    entity_id: str = Field(..., min_length=1)
    entity_type: EntityType = Field(...)
    valid_from: int = Field(0, ge=0)
    valid_to: Optional[int] = Field(None)
    attrs: Dict[str, Any] = Field(default_factory=dict)
    labels: list[str] = Field(default_factory=list)
    confidence: float = Field(1.0, ge=0.0, le=1.0)

    class Config:
        use_enum_values = True
        extra = "allow"

    def neo4j_label(self) -> str:
        """获取 Neo4j 标签"""
        if isinstance(self.entity_type, str):
            for et, lbl in NODE_LABELS.items():
                if lbl == self.entity_type or et.value == self.entity_type:
                    return lbl
            return str(self.entity_type)
        return NODE_LABELS.get(self.entity_type, self.entity_type.value)

    def is_active(self, frame_id: int) -> bool:
        """检查实体在指定帧是否激活"""
        if frame_id < self.valid_from:
            return False
        if self.valid_to is not None and frame_id > self.valid_to:
            return False
        return True

    def to_neo4j_dict(self) -> Dict[str, Any]:
        """转换为 Neo4j 插入字典"""
        result: Dict[str, Any] = {
            "entity_id": self.entity_id,
            "valid_from": self.valid_from,
            "valid_to": self.valid_to,
            "labels": self.labels,
            "confidence": self.confidence,
        }
        for k, v in self.attrs.items():
            result[k] = v
        return result


class BaseRelation(BaseModel):
    """所有关系的基类"""
    src_id: str = Field(..., min_length=1)
    dst_id: str = Field(..., min_length=1)
    relation_type: str = Field(..., min_length=1)
    frame_id: int = Field(0, ge=0)
    valid_from: int = Field(0, ge=0)
    valid_to: Optional[int] = Field(None)
    attrs: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        use_enum_values = True
        extra = "allow"

    def to_neo4j_dict(self) -> Dict[str, Any]:
        """转换为 Neo4j 插入字典"""
        return {
            "src_id": self.src_id,
            "dst_id": self.dst_id,
            "relation_type": self.relation_type,
            "frame_id": self.frame_id,
            "valid_from": self.valid_from,
            "valid_to": self.valid_to,
            **self.attrs,
        }