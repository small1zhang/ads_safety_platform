"""
JSON 序列化器
用于开发/无 Neo4j 时的图数据持久化
"""
import json
import os
from typing import Dict, Any, List
from datetime import datetime


class JSONSerializer:
    """JSON 分片序列化器"""
    
    def __init__(self, output_dir: str = "kg_snapshots"):
        """
        初始化序列化器
        
        参数:
            output_dir: 输出目录
        """
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
    
    def serialize_frame(self, frame_data: Dict[str, Any], frame_id: int) -> str:
        """
        序列化单帧数据为 JSON 文件
        
        参数:
            frame_data: 帧数据
            frame_id: 帧 ID
        
        返回:
            文件路径
        """
        filename = f"{self.output_dir}/frame_{frame_id:06d}.json"
        
        # 添加元数据
        output_data = {
            'metadata': {
                'frame_id': frame_id,
                'timestamp': datetime.now().isoformat(),
                'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            },
            'data': frame_data,
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2, default=str)
        
        return filename
    
    def serialize_delta(self, delta, frame_id: int) -> str:
        """
        序列化差分图为 JSON 文件
        
        参数:
            delta: DeltaGraph 对象
            frame_id: 帧 ID
        
        返回:
            文件路径
        """
        filename = f"{self.output_dir}/delta_{frame_id:06d}.json"
        
        # 转换 DeltaGraph 为可序列化的字典
        delta_dict = {
            'frame_id': delta.frame_id,
            'entities': {
                'added': list(delta.entities.added),
                'removed': list(delta.entities.removed),
                'unchanged': list(delta.entities.unchanged),
            },
            'attributes': {
                f"{eid}_{attr}": {'old': old_val, 'new': new_val}
                for (eid, attr), (old_val, new_val) in delta.attributes.items()
            },
            'relations': {
                'added': list(delta.relations.added),
                'removed': list(delta.relations.removed),
                'unchanged': list(delta.relations.unchanged),
            },
            'rule_events': delta.rule_events,
        }
        
        output_data = {
            'metadata': {
                'frame_id': frame_id,
                'timestamp': datetime.now().isoformat(),
                'summary': delta.summary() if hasattr(delta, 'summary') else '',
            },
            'delta': delta_dict,
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2, default=str)
        
        return filename
    
    def load_frame(self, frame_id: int) -> Dict[str, Any]:
        """
        加载指定帧的数据
        
        参数:
            frame_id: 帧 ID
        
        返回:
            帧数据字典
        """
        filename = f"{self.output_dir}/frame_{frame_id:06d}.json"
        
        if not os.path.exists(filename):
            raise FileNotFoundError(f"帧文件不存在: {filename}")
        
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def list_frames(self) -> List[int]:
        """列出所有可用的帧 ID"""
        frame_ids = []
        
        for filename in os.listdir(self.output_dir):
            if filename.startswith('frame_') and filename.endswith('.json'):
                # 提取帧 ID
                frame_id = int(filename.replace('frame_', '').replace('.json', ''))
                frame_ids.append(frame_id)
        
        return sorted(frame_ids)
    
    def delete_frame(self, frame_id: int) -> bool:
        """
        删除指定帧的文件
        
        参数:
            frame_id: 帧 ID
        
        返回:
            是否删除成功
        """
        filename = f"{self.output_dir}/frame_{frame_id:06d}.json"
        
        if os.path.exists(filename):
            os.remove(filename)
            return True
        
        return False