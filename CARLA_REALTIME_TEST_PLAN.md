# 🚗 CARLA实时检测验证方案

> **完整方案** - 30分钟CARLA仿真实时检测验证

---

## 🎯 **检测目标**

验证异常检测框架在CARLA仿真环境中的实际效果：
- ✅ **连接稳定性**: CARLA服务连接和数据采集
- ✅ **检测准确性**: RSS规则检测的准确性
- ✅ **性能表现**: 实时检测的性能指标
- ✅ **异常覆盖**: 各类异常场景的检出能力
- ✅ **可视化效果**: 输出文件的质量

---

## 📋 **准备工作**

### **1. 检查CARLA服务状态**

#### **方法1: 检查进程**
```bash
# 检查CARLA服务器进程
ps aux | grep -i carla

# 检查端口占用
netstat -tuln | grep 2000
# 或者
ss -tuln | grep 2000
```

#### **方法2: 测试连接**
```bash
# 使用curl测试CARLA Web服务器
curl -s http://localhost:2000 | head -20

# 使用Python测试CARLA客户端
python3 -c "
import carla
client = carla.Client('localhost', 2000)
client.set_timeout(5.0)
print('CARLA连接测试:', '成功' if client.get_server_version() else '失败')
"
```

### **2. 启动CARLA服务**

#### **选项A: 使用Docker启动CARLA**
```bash
# 启动CARLA服务器 (需要Docker)
docker run -it --rm -p 2000-2002:2000-2002 --gpus all carlasim/carla:0.9.14 \
  /bin/bash -c "SDL_VIDEODRIVER=offscreen /opt/carla-simulator/CarlaUE4.sh -RenderOffScreen"
```

#### **选项B: 本地安装CARLA**
```bash
# 启动CARLA服务器
cd /opt/carla-simulator
./CarlaUE4.sh -RenderOffScreen &

# 或者使用GUI模式
./CarlaUE4.sh &
```

#### **选项C: 使用模拟数据 (不需要CARLA)**
```bash
# 使用内置的模拟数据进行测试
# 适合快速验证检测逻辑
```

---

## 🚀 **30分钟实时检测方案**

### **方案1: 使用现有收集器 (推荐)**

#### **运行命令**
```bash
cd /home/aisecurity/01_ZHB

# 方法1: 使用异步收集器 (支持CARLA连接)
python3 backend/app/realtime_carla_collector.py \
  --duration 1800 \  # 30分钟 = 1800秒
  --interval 2.0 \    # 每2秒检测一次
  --inject-anomalies true \  # 注入异常场景
  --output-dir ./output_30min_test
```

#### **预期输出**
```
[INFO] 开始收集数据，持续 1800 秒...
[INFO] 场景 0: 检测到 3 个违规 (CRITICAL)
[INFO] 场景 1: 检测到 1 个违规 (HIGH)
[INFO] 场景 2: 检测到 2 个违规 (MEDIUM)
...
[INFO] 收集完成！总计检测 900 个场景，发现 250+ 个异常
```

### **方案2: 使用简化版检测脚本**

#### **创建检测脚本**
```python
# test_carla_detection.py
import asyncio
import sys
sys.path.insert(0, '/home/aisecurity/01_ZHB/backend/app')

from realtime_carla_collector import RealTimeCollector
from realtime_multi_anomaly_demo import MultiAnomalyRenderer

async def run_30min_test():
    collector = RealTimeCollector(
        host="localhost",
        port=2000,
        timeout=10.0
    )
    
    # 尝试连接CARLA
    if collector.connect():
        print("✅ CARLA连接成功")
    else:
        print("⚠️ CARLA连接失败，使用模拟数据")
        # 使用模拟数据模式
        collector.client = None
    
    # 运行30分钟检测
    data = await collector.collect_async(
        duration_seconds=1800,  # 30分钟
        interval=2.0,
        inject_anomalies=True
    )
    
    # 生成可视化报告
    renderer = MultiAnomalyRenderer()
    dashboard = await renderer.generate_dashboard_async(data)
    
    # 保存结果
    import json
    with open('output_30min_test/results.json', 'w') as f:
        json.dump({
            'total_scenarios': data.num_scenarios,
            'total_anomalies': len(data.anomalies),
            'risk_distribution': data.risk_distribution,
            'total_duration': data.total_duration
        }, f, indent=2)
    
    print(f"✅ 检测完成！")
    print(f"   总场景数: {data.num_scenarios}")
    print(f"   总异常数: {len(data.anomalies)}")
    print(f"   风险分布: {data.risk_distribution}")
    print(f"   总时长: {data.total_duration:.2f}秒")

if __name__ == "__main__":
    asyncio.run(run_30min_test())
```

#### **运行检测**
```bash
cd /home/aisecurity/01_ZHB
mkdir -p output_30min_test
python3 test_carla_detection.py
```

---

## 📊 **检测效果验证**

### **1. 连接稳定性验证**

#### **检查点**
- [ ] CARLA服务器连接成功
- [ ] 数据采集无中断
- [ ] 断线重连机制正常
- [ ] 30分钟连续运行无异常

#### **验证命令**
```bash
# 检查连接日志
grep -i "连接" output_30min_test/*.log 2>/dev/null || echo "无日志文件"

# 检查错误信息
grep -i "error\|exception\|失败" output_30min_test/*.log 2>/dev/null || echo "无错误"
```

### **2. 检测准确性验证**

#### **检查点**
- [ ] RSS规则检测正确
- [ ] 异常分类准确
- [ ] 风险等级合理
- [ ] 违规信息完整

#### **验证方法**
```python
# 验证检测结果
import json

with open('output_30min_test/results.json', 'r') as f:
    results = json.load(f)

print("检测准确性验证:")
print(f"总场景数: {results['total_scenarios']}")
print(f"总异常数: {results['total_anomalies']}")
print(f"检出率: {results['total_anomalies']/results['total_scenarios']*100:.2f}%")
print(f"风险分布: {results['risk_distribution']}")

# 验证RSS规则覆盖
anomaly_files = []  # 这里应该读取实际的异常文件
# 检查每个异常文件中的违规规则
```

### **3. 性能表现验证**

#### **检查点**
- [ ] 平均检测时长 < 100ms
- [ ] 内存占用稳定
- [ ] CPU使用率合理
- [ ] 无内存泄漏

#### **验证命令**
```bash
# 监控系统资源使用
# 在另一个终端运行:
top -d 1 -p $(pgrep -f "python.*realtime_carla")

# 或者使用htop
htop
```

### **4. 异常覆盖验证**

#### **检查点**
- [ ] 覆盖所有RSS规则类型
- [ ] 各风险等级都有检出
- [ ] 异常场景多样性
- [ ] 违规信息详细

#### **验证方法**
```python
# 分析异常覆盖
import json
import glob

# 读取所有异常文件
anomaly_files = glob.glob('output_30min_test/anomalies/*.html')
print(f"异常文件数量: {len(anomaly_files)}")

# 分析违规规则分布
rule_distribution = {}
for file in anomaly_files[:10]:  # 示例：分析前10个文件
    with open(file, 'r') as f:
        content = f.read()
        # 提取违规规则信息
        # 这里需要根据实际HTML内容调整
        pass

print(f"违规规则分布: {rule_distribution}")
```

---

## 📈 **预期结果**

### **基于20分钟检测的推断**

| 指标 | 20分钟结果 | 30分钟预期 |
|------|-----------|-----------|
| 检测时长 | 1200秒 | 1800秒 |
| 检测次数 | 600次 | 900次 |
| 异常检出 | 172个 | 250-300个 |
| 检出率 | 28.67% | 28-33% |
| 风险分布 | 均匀分布 | 均匀分布 |

### **异常分布预期**

| 风险等级 | 20分钟 | 30分钟预期 |
|----------|--------|-----------|
| CRITICAL | 43个 | 60-70个 |
| HIGH | 43个 | 60-70个 |
| MEDIUM | 43个 | 60-70个 |
| LOW | 43个 | 60-70个 |

### **RSS规则覆盖预期**

| 规则类别 | 20分钟 | 30分钟预期 |
|----------|--------|-----------|
| 纵向安全 | 4条规则 | 4条规则 |
| 横向安全 | 5条规则 | 5条规则 |
| 交叉口 | 8条规则 | 8条规则 |
| 行人保护 | 4条规则 | 4条规则 |
| 风险指数 | 6条规则 | 6条规则 |
| 应用层验证 | 6条规则 | 6条规则 |

---

## 🎯 **检测效果评估标准**

### **优秀 (⭐⭐⭐⭐⭐)**
- [ ] 连接稳定，无中断
- [ ] 检测准确性 > 95%
- [ ] 平均检测时长 < 100ms
- [ ] 异常检出率 > 25%
- [ ] 覆盖所有RSS规则
- [ ] 输出文件完整且清晰

### **良好 (⭐⭐⭐⭐)**
- [ ] 连接基本稳定，偶尔中断
- [ ] 检测准确性 > 90%
- [ ] 平均检测时长 < 200ms
- [ ] 异常检出率 > 20%
- [ ] 覆盖大部分RSS规则
- [ ] 输出文件基本完整

### **合格 (⭐⭐⭐)**
- [ ] 连接偶尔中断
- [ ] 检测准确性 > 80%
- [ ] 平均检测时长 < 500ms
- [ ] 异常检出率 > 15%
- [ ] 覆盖部分RSS规则
- [ ] 输出文件有缺失

---

## 🚨 **常见问题及解决方案**

### **问题1: CARLA服务连接失败**

#### **症状**
```
[WARN] CARLA连接失败: Connection refused
[ERROR] 获取实体信息失败: No connection to CARLA server
```

#### **解决方案**
1. **检查CARLA服务是否运行**
   ```bash
   ps aux | grep carla
   ```

2. **检查端口是否正确**
   ```bash
   netstat -tuln | grep 2000
   ```

3. **重新启动CARLA**
   ```bash
   # 先杀死现有进程
   pkill -f carla
   
   # 重新启动
   cd /opt/carla-simulator
   ./CarlaUE4.sh -RenderOffScreen &
   ```

4. **使用模拟数据模式**
   ```python
   # 在代码中设置
   collector.client = None  # 使用模拟数据
   ```

### **问题2: 检测速度慢**

#### **症状**
```
平均检测时长: 500ms+
检测频率低
```

#### **解决方案**
1. **减少检测间隔**
   ```python
   # 从2.0秒改为1.0秒
   interval=1.0
   ```

2. **优化RSS规则计算**
   ```python
   # 使用缓存，减少重复计算
   # 优化数学公式计算
   ```

3. **使用异步处理**
   ```python
   # 已经使用异步，确保没有阻塞操作
   ```

### **问题3: 异常检出率低**

#### **症状**
```
检出率 < 15%
异常数量少
```

#### **解决方案**
1. **启用异常注入**
   ```python
   inject_anomalies=True  # 确保启用
   ```

2. **增加异常场景类型**
   ```python
   # 在realtime_carla_collector.py中添加更多异常类型
   anomaly_types = [
       ('RED_LIGHT', builder.create_red_light_scenario),
       ('MERGE_CONFLICT', builder.create_merge_scenario),
       ('PEDESTRIAN', builder.create_pedestrian_crossing_scenario),
       ('INTERSECTION', builder.create_intersection_scenario),
       # 添加更多...
   ]
   ```

3. **调整检测阈值**
   ```python
   # 在RSS规则中调整参数
   # 例如：减小安全距离阈值
   ```

---

## 📝 **检测结果记录模板**

### **检测信息**
```
检测开始时间: __________
检测结束时间: __________
检测总时长: __________ 秒
检测次数: __________ 次
```

### **连接状态**
```
CARLA服务连接: [✅ 成功 / ❌ 失败]
连接中断次数: __________
断线重连次数: __________
```

### **检测结果**
```
总异常数: __________
检出率: __________ %
平均检测时长: __________ ms
```

### **风险分布**
```
CRITICAL: __________ 个 (_____%)
HIGH:     __________ 个 (_____%)
MEDIUM:   __________ 个 (_____%)
LOW:      __________ 个 (_____%)
```

### **RSS规则覆盖**
```
纵向安全: __________ 条规则触发
横向安全: __________ 条规则触发
交叉口:    __________ 条规则触发
行人保护:  __________ 条规则触发
风险指数:  __________ 条规则触发
应用层:    __________ 条规则触发
```

### **性能指标**
```
内存占用: __________ MB
CPU使用率: __________ %
磁盘I/O: __________ MB/s
网络I/O: __________ KB/s
```

### **问题记录**
```
问题1: ________________________________
解决方案: _____________________________

问题2: ________________________________
解决方案: _____________________________
```

---

## 🎉 **总结**

### **检测方案特点**

1. **灵活性**: 支持CARLA连接和模拟数据两种模式
2. **完整性**: 覆盖所有RSS规则类型
3. **可验证性**: 提供详细的检测结果和统计
4. **可视化**: 生成HTML可视化报告
5. **可扩展性**: 易于添加新的检测规则

### **预期效果**

基于20分钟检测的成功经验，30分钟检测预期：
- ✅ **检测次数**: 900次 (每2秒一次)
- ✅ **异常检出**: 250-300个 (检出率28-33%)
- ✅ **风险分布**: 均匀分布在4个等级
- ✅ **RSS覆盖**: 覆盖所有33条规则
- ✅ **性能表现**: 平均检测时长 < 100ms

### **下一步行动**

1. **启动CARLA服务**
2. **运行30分钟检测**
3. **收集检测结果**
4. **分析检测效果**
5. **优化检测参数**

---

## 📞 **支持**

- **项目地址**: [github.com/small1zhang/ads_safety_platform](https://github.com/small1zhang/ads_safety_platform)
- **文档**: 查看 [DOCUMENT_NAVIGATION.md](./DOCUMENT_NAVIGATION.md)
- **问题**: 通过GitHub Issues反馈

---

*方案生成时间: 2026-08-26*  
*项目状态: ✅ 已完成  
*版本: 2.0.0*