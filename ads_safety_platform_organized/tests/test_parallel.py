"""
单元测试 - 并行计算优化
"""
import unittest
import time
from ads_safety_platform.kg.optimization.parallel import (
    ParallelProcessor, ParallelConfig, ResultCache,
    PerformanceMetrics, RuleParallelProcessor
)


class TestResultCache(unittest.TestCase):
    """测试结果缓存"""
    
    def test_cache_set_get(self):
        """测试缓存设置和获取"""
        cache = ResultCache(max_size=10)
        cache.set('key1', 'value1')
        self.assertEqual(cache.get('key1'), 'value1')
    
    def test_cache_miss(self):
        """测试缓存未命中"""
        cache = ResultCache(max_size=10)
        self.assertIsNone(cache.get('nonexistent'))
    
    def test_cache_eviction(self):
        """测试缓存淘汰"""
        cache = ResultCache(max_size=3)
        cache.set('key1', 'value1')
        cache.set('key2', 'value2')
        cache.set('key3', 'value3')
        cache.set('key4', 'value4')  # 应该淘汰 key1
        
        self.assertIsNone(cache.get('key1'))
        self.assertEqual(cache.get('key2'), 'value2')
        self.assertEqual(cache.get('key3'), 'value3')
        self.assertEqual(cache.get('key4'), 'value4')
    
    def test_cache_lru(self):
        """测试 LRU 策略"""
        cache = ResultCache(max_size=3)
        cache.set('key1', 'value1')
        cache.set('key2', 'value2')
        cache.set('key3', 'value3')
        
        # 访问 key1 使其成为最近使用
        cache.get('key1')
        
        # 添加新项，应该淘汰 key2
        cache.set('key4', 'value4')
        
        self.assertEqual(cache.get('key1'), 'value1')
        self.assertIsNone(cache.get('key2'))
        self.assertEqual(cache.get('key3'), 'value3')
        self.assertEqual(cache.get('key4'), 'value4')


class TestPerformanceMetrics(unittest.TestCase):
    """测试性能指标"""
    
    def test_initial_values(self):
        """测试初始值"""
        metrics = PerformanceMetrics()
        self.assertEqual(metrics.total_calls, 0)
        self.assertEqual(metrics.cache_hits, 0)
        self.assertEqual(metrics.get_cache_hit_rate(), 0.0)
        self.assertEqual(metrics.get_average_time(), 0.0)
    
    def test_cache_hit_rate(self):
        """测试缓存命中率计算"""
        metrics = PerformanceMetrics()
        metrics.cache_hits = 8
        metrics.cache_misses = 2
        self.assertEqual(metrics.get_cache_hit_rate(), 0.8)
    
    def test_average_time(self):
        """测试平均时间计算"""
        metrics = PerformanceMetrics()
        metrics.total_calls = 4
        metrics.total_time = 8.0
        self.assertEqual(metrics.get_average_time(), 2.0)


class TestParallelProcessor(unittest.TestCase):
    """测试并行处理器"""
    
    def test_serial_execution(self):
        """测试串行执行"""
        config = ParallelConfig(max_workers=1, use_threading=True)
        processor = ParallelProcessor(config)
        
        def square(x):
            return x * x
        
        items = [1, 2, 3, 4, 5]
        results = processor.parallel_map(square, items)
        expected = [1, 4, 9, 16, 25]
        self.assertEqual(results, expected)
    
    def test_parallel_execution(self):
        """测试并行执行"""
        config = ParallelConfig(max_workers=4, use_threading=True)
        processor = ParallelProcessor(config)
        
        def square(x):
            return x * x
        
        items = [1, 2, 3, 4, 5, 6, 7, 8]
        results = processor.parallel_map(square, items)
        expected = [1, 4, 9, 16, 25, 36, 49, 64]
        self.assertEqual(results, expected)
    
    def test_batch_process(self):
        """测试批量处理"""
        config = ParallelConfig(max_workers=2, use_threading=True)
        processor = ParallelProcessor(config)
        
        def square(x):
            return x * x
        
        items = list(range(20))
        results = processor.batch_process(square, items, batch_size=5)
        expected = [x * x for x in range(20)]
        self.assertEqual(results, expected)
    
    def test_metrics_tracking(self):
        """测试指标跟踪"""
        config = ParallelConfig(max_workers=2, use_threading=True)
        processor = ParallelProcessor(config)
        
        def square(x):
            return x * x
        
        processor.parallel_map(square, [1, 2, 3])
        metrics = processor.get_metrics()
        
        self.assertGreaterEqual(metrics['total_calls'], 1)
        self.assertGreaterEqual(metrics['parallel_calls'], 0)
    
    def test_cache_integration(self):
        """测试缓存集成"""
        config = ParallelConfig(max_workers=2, enable_cache=True, cache_size=100)
        processor = ParallelProcessor(config)
        
        def square(x):
            return x * x
        
        items = [1, 2, 3, 4, 5]
        
        # 第一次执行
        results1 = processor.parallel_map_with_cache(square, items)
        
        # 第二次执行 (应使用缓存)
        results2 = processor.parallel_map_with_cache(square, items)
        
        self.assertEqual(results1, results2)
        
        metrics = processor.get_metrics()
        self.assertGreater(metrics['cache_hits'], 0)


class TestRuleParallelProcessor(unittest.TestCase):
    """测试规则并行处理器"""
    
    def test_check_rules_parallel(self):
        """测试并行规则检查"""
        processor = RuleParallelProcessor()
        
        def rule1(context):
            return {'violation': True, 'rule': 'rule1', 'message': '违规1'}
        
        def rule2(context):
            return {'violation': False, 'rule': 'rule2', 'message': '正常'}
        
        def rule3(context):
            return {'violation': True, 'rule': 'rule3', 'message': '违规3'}
        
        context = {'speed': 20, 'distance': 10}
        rules = [rule1, rule2, rule3]
        
        violations = processor.check_rules_parallel(rules, context)
        
        self.assertEqual(len(violations), 2)
        self.assertIn('rule1', [v['rule'] for v in violations])
        self.assertIn('rule3', [v['rule'] for v in violations])
    
    def test_check_vehicle_pairs_parallel(self):
        """测试并行车辆对检查"""
        processor = RuleParallelProcessor()
        
        def check_distance(v1, v2):
            dx = v2['x'] - v1['x']
            dy = v2['y'] - v1['y']
            dist = (dx**2 + dy**2) ** 0.5
            return {'distance': dist, 'safe': dist > 10}
        
        vehicles = [
            {'x': 0, 'y': 0},
            {'x': 5, 'y': 0},
            {'x': 15, 'y': 0},
        ]
        
        results = processor.check_vehicle_pairs_parallel(vehicles, check_distance)
        
        # 应该有 3 个车辆对: (0,1), (0,2), (1,2)
        self.assertEqual(len(results), 3)


if __name__ == '__main__':
    unittest.main()
