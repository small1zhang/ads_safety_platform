"""
并行处理器
优化关键计算路径的并行执行

增强功能:
- 规则检查并行化
- 缓存机制
- 性能监控
- 自适应并行策略
"""
import concurrent.futures
import time
import functools
from typing import List, Dict, Any, Callable, Optional, Tuple
from dataclasses import dataclass, field
from collections import OrderedDict
import multiprocessing as mp
import threading


@dataclass
class ParallelConfig:
    """并行配置"""
    max_workers: int = None  # 最大并行数
    use_threading: bool = True  # 使用线程池 (True) 或进程池 (False)
    cache_size: int = 1000  # 缓存大小
    enable_cache: bool = True  # 启用缓存
    min_parallel_items: int = 4  # 最小并行项数 (低于此值使用串行)
    timeout: float = 30.0  # 超时时间 (秒)


@dataclass
class PerformanceMetrics:
    """性能指标"""
    total_calls: int = 0
    parallel_calls: int = 0
    serial_calls: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    total_time: float = 0.0
    parallel_time: float = 0.0
    serial_time: float = 0.0
    
    def get_cache_hit_rate(self) -> float:
        """获取缓存命中率"""
        total = self.cache_hits + self.cache_misses
        return self.cache_hits / total if total > 0 else 0.0
    
    def get_average_time(self) -> float:
        """获取平均执行时间"""
        return self.total_time / self.total_calls if self.total_calls > 0 else 0.0
    
    def get_speedup(self) -> float:
        """获取加速比"""
        if self.serial_time == 0:
            return 1.0
        return self.serial_time / self.parallel_time if self.parallel_time > 0 else 1.0


class ResultCache:
    """结果缓存 (LRU 缓存)"""
    
    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self.cache: OrderedDict = OrderedDict()
        self.lock = threading.Lock()
    
    def get(self, key: Any) -> Optional[Any]:
        """获取缓存值"""
        with self.lock:
            if key in self.cache:
                # 移动到末尾 (最近使用)
                self.cache.move_to_end(key)
                return self.cache[key]
            return None
    
    def set(self, key: Any, value: Any) -> None:
        """设置缓存值"""
        with self.lock:
            if key in self.cache:
                self.cache.move_to_end(key)
            else:
                if len(self.cache) >= self.max_size:
                    # 移除最旧的项
                    self.cache.popitem(last=False)
            self.cache[key] = value
    
    def clear(self) -> None:
        """清空缓存"""
        with self.lock:
            self.cache.clear()
    
    def __len__(self) -> int:
        return len(self.cache)


class ParallelProcessor:
    """
    并行处理器
    
    优化以下计算密集型任务：
    1. 多车辆空间关系计算
    2. 多车辆行为检测
    3. 多目标规则检查
    
    增强功能:
    - 自适应并行策略
    - 结果缓存
    - 性能监控
    - 超时控制
    """
    
    def __init__(self, config: ParallelConfig = None):
        """
        初始化并行处理器
        
        参数:
            config: 并行配置
        """
        self.config = config or ParallelConfig()
        self.max_workers = self.config.max_workers or min(mp.cpu_count(), 8)
        self.use_parallel = self.max_workers > 1
        self.use_threading = self.config.use_threading
        
        # 缓存
        self.cache = ResultCache(self.config.cache_size) if self.config.enable_cache else None
        
        # 性能指标
        self.metrics = PerformanceMetrics()
        self.metrics_lock = threading.Lock()
        
        # 执行器
        self._executor = None
        self._executor_lock = threading.Lock()
    
    def _get_executor(self):
        """获取执行器 (线程安全)"""
        if self._executor is None:
            with self._executor_lock:
                if self._executor is None:
                    if self.use_threading:
                        self._executor = concurrent.futures.ThreadPoolExecutor(
                            max_workers=self.max_workers
                        )
                    else:
                        self._executor = concurrent.futures.ProcessPoolExecutor(
                            max_workers=self.max_workers
                        )
        return self._executor
    
    def parallel_map(self, func: Callable, items: List[Any]) -> List[Any]:
        """
        并行映射
        
        参数:
            func: 处理函数
            items: 输入列表
        
        返回:
            结果列表
        """
        start_time = time.time()
        
        # 如果项数太少，使用串行
        if not self.use_parallel or len(items) <= self.config.min_parallel_items:
            self._update_metrics(start_time, len(items), False)
            return [func(item) for item in items]
        
        try:
            with self._get_executor() as executor:
                results = list(executor.map(func, items))
            
            self._update_metrics(start_time, len(items), True)
            return results
        except Exception as e:
            # 回退到串行
            self._update_metrics(start_time, len(items), False)
            return [func(item) for item in items]
    
    def parallel_map_with_cache(self, func: Callable, items: List[Any], 
                                key_func: Callable = None) -> List[Any]:
        """
        带缓存的并行映射
        
        参数:
            func: 处理函数
            items: 输入列表
            key_func: 缓存键生成函数 (默认使用输入项本身)
        
        返回:
            结果列表
        """
        if self.cache is None:
            return self.parallel_map(func, items)
        
        if key_func is None:
            key_func = lambda x: x
        
        results = []
        for item in items:
            key = key_func(item)
            
            # 尝试从缓存获取
            cached_result = self.cache.get(key)
            if cached_result is not None:
                with self.metrics_lock:
                    self.metrics.cache_hits += 1
                results.append(cached_result)
                continue
            
            with self.metrics_lock:
                self.metrics.cache_misses += 1
        
        # 计算未缓存的项
        uncached_items = []
        uncached_indices = []
        for i, item in enumerate(items):
            key = key_func(item)
            if self.cache.get(key) is None:
                uncached_items.append(item)
                uncached_indices.append(i)
        
        # 并行处理未缓存的项
        if uncached_items:
            uncached_results = self.parallel_map(func, uncached_items)
            
            # 缓存结果
            for item, result in zip(uncached_items, uncached_results):
                key = key_func(item)
                self.cache.set(key, result)
            
            # 合并结果
            for idx, result in zip(uncached_indices, uncached_results):
                results.insert(idx, result)
        
        return results
    
    def batch_process(self, func: Callable, items: List[Any], 
                      batch_size: int = 10) -> List[Any]:
        """
        批量处理 (适用于大数据集)
        
        参数:
            func: 处理函数
            items: 输入列表
            batch_size: 批量大小
        
        返回:
            结果列表
        """
        results = []
        for i in range(0, len(items), batch_size):
            batch = items[i:i + batch_size]
            batch_results = self.parallel_map(func, batch)
            results.extend(batch_results)
        return results
    
    def _update_metrics(self, start_time: float, item_count: int, is_parallel: bool):
        """更新性能指标"""
        elapsed = time.time() - start_time
        
        with self.metrics_lock:
            self.metrics.total_calls += 1
            self.metrics.total_time += elapsed
            
            if is_parallel:
                self.metrics.parallel_calls += 1
                self.metrics.parallel_time += elapsed
            else:
                self.metrics.serial_calls += 1
                self.metrics.serial_time += elapsed
    
    def get_metrics(self) -> Dict[str, Any]:
        """获取性能指标"""
        with self.metrics_lock:
            return {
                'total_calls': self.metrics.total_calls,
                'parallel_calls': self.metrics.parallel_calls,
                'serial_calls': self.metrics.serial_calls,
                'cache_hits': self.metrics.cache_hits,
                'cache_misses': self.metrics.cache_misses,
                'cache_hit_rate': self.metrics.get_cache_hit_rate(),
                'total_time': self.metrics.total_time,
                'parallel_time': self.metrics.parallel_time,
                'serial_time': self.metrics.serial_time,
                'average_time': self.metrics.get_average_time(),
                'speedup': self.metrics.get_speedup(),
                'cache_size': len(self.cache) if self.cache else 0,
            }
    
    def reset_metrics(self) -> None:
        """重置性能指标"""
        with self.metrics_lock:
            self.metrics = PerformanceMetrics()
        if self.cache:
            self.cache.clear()
    
    def shutdown(self) -> None:
        """关闭执行器"""
        if self._executor is not None:
            self._executor.shutdown(wait=True)
            self._executor = None


class RuleParallelProcessor:
    """
    规则并行处理器
    专门用于并行检查多个规则
    """
    
    def __init__(self, parallel_config: ParallelConfig = None):
        self.parallel_processor = ParallelProcessor(parallel_config)
    
    def check_rules_parallel(self, 
                           rules: List[Callable],
                           context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        并行检查多个规则
        
        参数:
            rules: 规则函数列表，每个函数接受 context 并返回违规字典
            context: 场景上下文
        
        返回:
            违规列表
        """
        # 为每个规则创建包装函数
        def rule_wrapper(rule_func):
            return rule_func(context)
        
        # 并行执行所有规则
        results = self.parallel_processor.parallel_map(rule_wrapper, rules)
        
        # 过滤出有违规的结果
        violations = [r for r in results if r and r.get('violation', False)]
        return violations
    
    def check_vehicle_pairs_parallel(self,
                                     vehicles: List[Dict[str, Any]],
                                     check_func: Callable) -> List[Dict[str, Any]]:
        """
        并行检查所有车辆对
        
        参数:
            vehicles: 车辆列表
            check_func: 检查函数，接受 (veh1, veh2) 并返回结果
        
        返回:
            结果列表
        """
        # 生成所有车辆对
        pairs = []
        for i in range(len(vehicles)):
            for j in range(i + 1, len(vehicles)):
                pairs.append((vehicles[i], vehicles[j]))
        
        # 并行检查
        results = self.parallel_processor.parallel_map(
            lambda pair: check_func(pair[0], pair[1]),
            pairs
        )
        return results
    
    def check_all_vehicles_parallel(self,
                                   vehicles: List[Dict[str, Any]],
                                   check_func: Callable) -> List[Dict[str, Any]]:
        """
        并行检查所有车辆
        
        参数:
            vehicles: 车辆列表
            check_func: 检查函数，接受 vehicle 并返回结果
        
        返回:
            结果列表
        """
        return self.parallel_processor.parallel_map(check_func, vehicles)


# 全局并行处理器实例
parallel_processor = ParallelProcessor()
rule_parallel_processor = RuleParallelProcessor()
