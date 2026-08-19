"""
并行处理器
优化关键计算路径的并行执行
"""
import concurrent.futures
from typing import List, Dict, Any, Callable
import multiprocessing as mp


class ParallelProcessor:
    """
    并行处理器
    
    优化以下计算密集型任务：
    1. 多车辆空间关系计算
    2. 多车辆行为检测
    3. 多目标规则检查
    """
    
    def __init__(self, max_workers: int = None):
        """
        初始化并行处理器
        
        参数:
            max_workers: 最大并行数，默认为 CPU 核心数
        """
        self.max_workers = max_workers or min(mp.cpu_count(), 8)
        self.use_parallel = self.max_workers > 1
    
    def parallel_map(self, func: Callable, items: List[Any]) -> List[Any]:
        """
        并行映射
        
        参数:
            func: 处理函数
            items: 输入列表
        
        返回:
            结果列表
        """
        if not self.use_parallel or len(items) <= 1:
            # 串行执行
            return [func(item) for item in items]
        
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=self.max_workers
        ) as executor:
            results = list(executor.map(func, items))
        
        return results
    
    def parallel_spatial_relations(self, 
                                   ego: Dict[str, Any],
                                   entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        并行计算空间关系
        
        参数:
            ego: 自车信息
            entities: 其他实体列表
        
        返回:
            关系列表
        """
        from kg_core.scenario.spatial import (
            compute_ahead_of,
            compute_beside,
            compute_nearby_pedestrian,
            compute_controlled_by,
        )
        
        def compute_relations_for_entity(entity):
            relations = []
            
            # 计算 ahead_of 关系
            if compute_ahead_of(entity, ego):
                relations.append({
                    'src_id': entity['entity_id'],
                    'dst_id': ego['entity_id'],
                    'relation_type': 'ahead_of',
                })
            
            # 计算 beside 关系
            if compute_beside(entity, ego):
                relations.append({
                    'src_id': entity['entity_id'],
                    'dst_id': ego['entity_id'],
                    'relation_type': 'beside',
                })
            
            # 计算 nearby_pedestrian 关系（如果是行人）
            if 'pedestrian' in entity.get('type_id', '').lower():
                if compute_nearby_pedestrian(ego, entity):
                    relations.append({
                        'src_id': entity['entity_id'],
                        'dst_id': ego['entity_id'],
                        'relation_type': 'nearby_pedestrian',
                    })
            
            return relations
        
        all_relations = self.parallel_map(compute_relations_for_entity, entities)
        
        # 展平结果
        return [r for sublist in all_relations for r in sublist]
    
    def parallel_behavior_detection(self,
                                    ego: Dict[str, Any],
                                    entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        并行行为检测
        
        参数:
            ego: 自车信息
            entities: 其他实体列表
        
        返回:
            行为事件列表
        """
        from kg_core.behavior import (
            detect_following,
            detect_approaching,
            detect_opposite_direction,
        )
        
        def detect_behaviors(entity):
            behaviors = []
            
            # 检测跟车
            if detect_following(ego, entity):
                behaviors.append({
                    'src_id': ego['entity_id'],
                    'dst_id': entity['entity_id'],
                    'behavior_type': 'following',
                })
            
            # 检测接近
            if detect_approaching(ego, entity):
                behaviors.append({
                    'src_id': ego['entity_id'],
                    'dst_id': entity['entity_id'],
                    'behavior_type': 'approaching',
                })
            
            # 检测对向行驶
            if detect_opposite_direction(ego, entity):
                behaviors.append({
                    'src_id': ego['entity_id'],
                    'dst_id': entity['entity_id'],
                    'behavior_type': 'opposite_direction',
                })
            
            return behaviors
        
        all_behaviors = self.parallel_map(detect_behaviors, entities)
        
        # 展平结果
        return [b for sublist in all_behaviors for b in sublist]
    
    def parallel_rule_check(self,
                           ego: Dict[str, Any],
                           entities: List[Dict[str, Any]],
                           rule_checks: List[Callable]) -> List[Dict[str, Any]]:
        """
        并行规则检查
        
        参数:
            ego: 自车信息
            entities: 其他实体列表
            rule_checks: 规则检查函数列表
        
        返回:
            违规列表
        """
        def check_rule(rule_func):
            try:
                return rule_func(ego, entities)
            except Exception as e:
                print(f"规则检查失败: {e}")
                return []
        
        all_violations = self.parallel_map(check_rule, rule_checks)
        
        # 展平结果
        return [v for sublist in all_violations for v in sublist]
    
    def get_stats(self) -> Dict[str, Any]:
        """获取处理器统计"""
        return {
            'max_workers': self.max_workers,
            'use_parallel': self.use_parallel,
            'cpu_count': mp.cpu_count(),
        }