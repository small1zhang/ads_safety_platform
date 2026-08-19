"""
版本管理 (v3 §5.3)
复用 SpatioTemporalKG 的属性版本化算法
"""
from dataclasses import dataclass
from typing import Dict, Any, List, Optional
from datetime import datetime


@dataclass
class AttrVersion:
    """属性版本"""
    value: Any
    valid_from: int
    valid_to: Optional[int] = None
    
    def is_active(self, frame_id: int) -> bool:
        """检查版本在指定帧是否激活"""
        if frame_id < self.valid_from:
            return False
        if self.valid_to is not None and frame_id > self.valid_to:
            return False
        return True


class VersionManager:
    """
    属性版本管理器
    
    管理每个实体每个属性的版本链
    支持任意时点的属性时间旅行查询
    """
    
    def __init__(self):
        # 版本链: {entity_id: {attr_name: [AttrVersion, ...]}}
        self.versions: Dict[str, Dict[str, List[AttrVersion]]] = {}
    
    def record(self, entity_id: str, attribute: str, 
               old_value: Any, new_value: Any, frame_id: int):
        """
        记录属性变化
        
        参数:
            entity_id: 实体 ID
            attribute: 属性名
            old_value: 旧值
            new_value: 新值
            frame_id: 当前帧 ID
        """
        if entity_id not in self.versions:
            self.versions[entity_id] = {}
        
        if attribute not in self.versions[entity_id]:
            self.versions[entity_id][attribute] = []
        
        # 关闭旧版本的 valid_to
        versions = self.versions[entity_id][attribute]
        if versions and versions[-1].valid_to is None:
            versions[-1].valid_to = frame_id - 1
        
        # 创建新版本
        new_version = AttrVersion(
            value=new_value,
            valid_from=frame_id,
            valid_to=None,
        )
        versions.append(new_version)
    
    def query(self, entity_id: str, attribute: str, frame_id: int) -> Optional[Any]:
        """
        查询指定帧的属性值（时间旅行查询）
        
        参数:
            entity_id: 实体 ID
            attribute: 属性名
            frame_id: 查询的帧 ID
        
        返回:
            属性值，如果不存在返回 None
        """
        if entity_id not in self.versions:
            return None
        
        if attribute not in self.versions[entity_id]:
            return None
        
        versions = self.versions[entity_id][attribute]
        
        # 从后向前查找第一个激活的版本
        for version in reversed(versions):
            if version.is_active(frame_id):
                return version.value
        
        return None
    
    def get_version_history(self, entity_id: str, attribute: str) -> List[AttrVersion]:
        """获取属性的完整版本历史"""
        if entity_id not in self.versions:
            return []
        
        if attribute not in self.versions[entity_id]:
            return []
        
        return self.versions[entity_id][attribute].copy()
    
    def get_entity_attributes(self, entity_id: str, frame_id: int) -> Dict[str, Any]:
        """获取实体在指定帧的所有属性"""
        if entity_id not in self.versions:
            return {}
        
        result = {}
        for attr, versions in self.versions[entity_id].items():
            value = self.query(entity_id, attr, frame_id)
            if value is not None:
                result[attr] = value
        
        return result
    
    def clear(self):
        """清空所有版本记录"""
        self.versions.clear()
    
    def save_to_json(self, filepath: str):
        """保存版本历史到 JSON 文件"""
        import json
        
        data = {}
        for entity_id, attrs in self.versions.items():
            data[entity_id] = {}
            for attr, versions in attrs.items():
                data[entity_id][attr] = [
                    {
                        'value': v.value,
                        'valid_from': v.valid_from,
                        'valid_to': v.valid_to,
                    }
                    for v in versions
                ]
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
    
    def load_from_json(self, filepath: str):
        """从 JSON 文件加载版本历史"""
        import json
        
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        self.clear()
        
        for entity_id, attrs in data.items():
            for attr, versions in attrs.items():
                self.versions[entity_id][attr] = [
                    AttrVersion(
                        value=v['value'],
                        valid_from=v['valid_from'],
                        valid_to=v.get('valid_to'),
                    )
                    for v in versions
                ]