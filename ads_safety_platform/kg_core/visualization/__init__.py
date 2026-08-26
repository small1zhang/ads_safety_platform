"""
可视化模块
提供自动驾驶安全平台的场景可视化能力

功能:
- 2D 场景可视化 (matplotlib)
- 3D 场景可视化 (matplotlib 3D)
- 风险热力图
- 路径规划可视化
- 实时监控仪表盘 (仅文本/ASCII)

依赖:
- matplotlib (可选)
- numpy
"""
import math
from typing import Dict, Any, List, Optional, Tuple

try:
    import matplotlib.pyplot as plt
    import matplotlib.patches as patches
    from matplotlib.patches import Rectangle, Circle, FancyArrow
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

import numpy as np


class SceneVisualizer:
    """
    场景可视化器
    
    将提取的场景数据可视化为 2D 图
    """
    
    def __init__(self, figsize: Tuple[int, int] = (12, 8), dpi: int = 100):
        """
        初始化可视化器
        
        参数:
            figsize: 图像大小
            dpi: 分辨率
        """
        if not HAS_MATPLOTLIB:
            raise ImportError("需要安装 matplotlib 才能使用可视化功能")
        self.figsize = figsize
        self.dpi = dpi
        self.fig = None
        self.ax = None
    
    def create_figure(self) -> None:
        """创建图形"""
        self.fig, self.ax = plt.subplots(figsize=self.figsize, dpi=self.dpi)
    
    def draw_vehicle(self, vehicle: Dict[str, Any], color: str = 'blue', 
                     label: str = None) -> None:
        """
        绘制车辆
        
        参数:
            vehicle: 车辆数据
            color: 颜色
            label: 标签
        """
        x = vehicle.get('x', 0)
        y = vehicle.get('y', 0)
        yaw = vehicle.get('yaw', 0)
        width = vehicle.get('width', 2.0)
        length = vehicle.get('length', 4.5)
        
        # 绘制车辆矩形
        rect = Rectangle(
            (x - length/2, y - width/2),
            length, width,
            linewidth=1.5,
            edgecolor=color,
            facecolor=color,
            alpha=0.5,
            zorder=3,
        )
        # 旋转矩形
        t = patches.Rectangle(
            (x - length/2, y - width/2), length, width,
            linewidth=1.5, edgecolor=color, facecolor=color,
            alpha=0.5, zorder=3,
        )
        from matplotlib.transforms import Affine2D
        transform = Affine2D().rotate_deg_around(x, y, math.degrees(yaw)) + self.ax.transData
        t.set_transform(transform)
        self.ax.add_patch(t)
        
        # 绘制车头方向箭头
        arrow_len = length * 0.8
        dx = arrow_len * math.cos(yaw)
        dy = arrow_len * math.sin(yaw)
        arrow = FancyArrow(
            x, y, dx, dy,
            width=0.1, head_width=0.6, head_length=0.8,
            color=color, alpha=0.8, zorder=4,
        )
        self.ax.add_patch(arrow)
        
        # 标签
        if label:
            self.ax.annotate(
                label, (x, y),
                textcoords="offset points",
                xytext=(0, 15),
                ha='center', fontsize=8, color=color,
            )
    
    def draw_pedestrian(self, pedestrian: Dict[str, Any], color: str = 'green') -> None:
        """
        绘制行人
        
        参数:
            pedestrian: 行人数据
            color: 颜色
        """
        x = pedestrian.get('x', 0)
        y = pedestrian.get('y', 0)
        radius = 0.5
        
        circle = Circle((x, y), radius,
                        linewidth=1.5, edgecolor=color,
                        facecolor=color, alpha=0.6, zorder=3)
        self.ax.add_patch(circle)
    
    def draw_traffic_light(self, traffic_light: Dict[str, Any]) -> None:
        """
        绘制交通灯
        
        参数:
            traffic_light: 交通灯数据
        """
        x = traffic_light.get('x', 0)
        y = traffic_light.get('y', 0)
        state = traffic_light.get('state', 'Unknown')
        
        color_map = {
            'Red': 'red',
            'Yellow': 'yellow',
            'Green': 'green',
            'Unknown': 'gray',
        }
        color = color_map.get(state, 'gray')
        
        circle = Circle((x, y), 0.8,
                        linewidth=1.5, edgecolor='black',
                        facecolor=color, alpha=0.9, zorder=5)
        self.ax.add_patch(circle)
        
        # 添加状态文本
        self.ax.annotate(
            state, (x, y),
            textcoords="offset points",
            xytext=(0, 12),
            ha='center', fontsize=8, color=color,
        )
    
    def draw_obstacle(self, obstacle: Dict[str, Any], color: str = 'red') -> None:
        """
        绘制障碍物
        
        参数:
            obstacle: 障碍物数据
            color: 颜色
        """
        x = obstacle.get('x', 0)
        y = obstacle.get('y', 0)
        width = obstacle.get('width', 1.0)
        length = obstacle.get('length', 1.0)
        
        rect = Rectangle(
            (x - length/2, y - width/2),
            length, width,
            linewidth=1.5,
            edgecolor=color,
            facecolor=color,
            alpha=0.4,
            zorder=2,
        )
        self.ax.add_patch(rect)
    
    def draw_path(self, path: List[Tuple[float, float]], color: str = 'orange',
                  label: str = 'Path') -> None:
        """
        绘制路径
        
        参数:
            path: 路径点列表 [(x1, y1), (x2, y2), ...]
            color: 颜色
            label: 标签
        """
        if not path:
            return
        
        xs = [p[0] for p in path]
        ys = [p[1] for p in path]
        self.ax.plot(xs, ys, '--', color=color, linewidth=2, label=label, zorder=2)
        self.ax.scatter(xs, ys, s=20, color=color, zorder=2)
    
    def draw_risk_zone(self, center: Tuple[float, float], radius: float,
                       risk_level: float, color: str = None) -> None:
        """
        绘制风险区域
        
        参数:
            center: 中心位置 (x, y)
            radius: 半径
            risk_level: 风险等级 (0-1)
            color: 颜色 (默认根据风险等级自动选择)
        """
        if color is None:
            # 根据风险等级选择颜色
            if risk_level > 0.8:
                color = 'red'
            elif risk_level > 0.5:
                color = 'orange'
            elif risk_level > 0.2:
                color = 'yellow'
            else:
                color = 'green'
        
        circle = Circle(center, radius,
                        linewidth=1, edgecolor=color,
                        facecolor=color, alpha=0.3, zorder=1)
        self.ax.add_patch(circle)
    
    def draw_text(self, x: float, y: float, text: str, 
                  color: str = 'black', fontsize: int = 10) -> None:
        """绘制文本"""
        self.ax.annotate(text, (x, y),
                        textcoords="offset points",
                        xytext=(0, -15),
                        ha='center', fontsize=fontsize, color=color)
    
    def set_limits(self, x_min: float, x_max: float,
                   y_min: float, y_max: float) -> None:
        """设置坐标范围"""
        self.ax.set_xlim(x_min, x_max)
        self.ax.set_ylim(y_min, y_max)
    
    def render(self, title: str = "AD Safety Scene", 
               show: bool = True, save_path: str = None) -> None:
        """
        渲染并显示图像
        
        参数:
            title: 标题
            show: 是否显示
            save_path: 保存路径
        """
        self.ax.set_title(title)
        self.ax.set_xlabel('X (m)')
        self.ax.set_ylabel('Y (m)')
        self.ax.grid(True, alpha=0.3)
        self.ax.set_aspect('equal', adjustable='box')
        self.ax.legend(loc='upper right')
        
        if save_path:
            self.fig.savefig(save_path, bbox_inches='tight')
        
        if show:
            plt.show()
    
    def visualize_frame(self, frame_data: Dict[str, Any], 
                        ego_id: str = None, title: str = "AD Safety Scene") -> None:
        """
        可视化一帧场景数据
        
        参数:
            frame_data: 帧数据 (pipeline.process_frame 的输出)
            ego_id: 自车 ID
            title: 标题
        """
        self.create_figure()
        
        # 计算范围
        all_x = []
        all_y = []
        
        # 绘制车辆
        for v in frame_data.get('vehicles', []):
            is_ego = (ego_id is not None and v.get('entity_id') == ego_id) or \
                     v.get('role_name') == 'ego'
            color = 'red' if is_ego else 'blue'
            label = v.get('entity_id', '') if is_ego else None
            self.draw_vehicle(v, color=color, label=label)
            all_x.append(v.get('x', 0))
            all_y.append(v.get('y', 0))
        
        # 绘制行人
        for p in frame_data.get('pedestrians', []):
            self.draw_pedestrian(p)
            all_x.append(p.get('x', 0))
            all_y.append(p.get('y', 0))
        
        # 绘制交通灯
        for tl in frame_data.get('traffic_lights', []):
            self.draw_traffic_light(tl)
            all_x.append(tl.get('x', 0))
            all_y.append(tl.get('y', 0))
        
        # 绘制障碍物
        for obs in frame_data.get('obstacles', []):
            self.draw_obstacle(obs)
            all_x.append(obs.get('x', 0))
            all_y.append(obs.get('y', 0))
        
        # 自动设置范围
        if all_x and all_y:
            margin = 10
            x_min, x_max = min(all_x) - margin, max(all_x) + margin
            y_min, y_max = min(all_y) - margin, max(all_y) + margin
            self.set_limits(x_min, x_max, y_min, y_max)
        
        self.render(title)


class RiskHeatmap:
    """
    风险热力图
    用于可视化场景中的风险分布
    """
    
    def __init__(self, x_range: Tuple[float, float], y_range: Tuple[float, float],
                 resolution: float = 1.0):
        """
        初始化风险热力图
        
        参数:
            x_range: X 轴范围 (min, max)
            y_range: Y 轴范围 (min, max)
            resolution: 网格分辨率 (m)
        """
        if not HAS_MATPLOTLIB:
            raise ImportError("需要安装 matplotlib 才能使用可视化功能")
        self.x_range = x_range
        self.y_range = y_range
        self.resolution = resolution
        self.grid = None
    
    def compute_risk_grid(self, frame_data: Dict[str, Any],
                          ego_vehicle: Dict[str, Any] = None) -> np.ndarray:
        """
        计算风险网格
        
        参数:
            frame_data: 帧数据
            ego_vehicle: 自车 (可选，用于计算相对风险)
        
        返回:
            风险网格 (2D numpy 数组)
        """
        x_min, x_max = self.x_range
        y_min, y_max = self.y_range
        
        nx = int((x_max - x_min) / self.resolution) + 1
        ny = int((y_max - y_min) / self.resolution) + 1
        
        grid = np.zeros((ny, nx))
        
        # 车辆风险
        for v in frame_data.get('vehicles', []):
            vx, vy = v.get('x', 0), v.get('y', 0)
            speed = v.get('speed', 0)
            
            # 风险随速度增加
            risk_radius = 5.0 + speed * 0.5
            
            # 计算车辆周围的风险
            for iy in range(ny):
                for ix in range(nx):
                    gx = x_min + ix * self.resolution
                    gy = y_min + iy * self.resolution
                    dist = math.sqrt((gx - vx)**2 + (gy - vy)**2)
                    
                    if dist < risk_radius:
                        # 风险随距离衰减
                        risk = (1.0 - dist / risk_radius) * 0.6 * min(1.0, speed / 20.0)
                        grid[iy, ix] = max(grid[iy, ix], risk)
        
        # 行人风险 (更小的半径但更高的权重)
        for p in frame_data.get('pedestrians', []):
            px, py = p.get('x', 0), p.get('y', 0)
            
            risk_radius = 3.0
            for iy in range(ny):
                for ix in range(nx):
                    gx = x_min + ix * self.resolution
                    gy = y_min + iy * self.resolution
                    dist = math.sqrt((gx - px)**2 + (gy - py)**2)
                    
                    if dist < risk_radius:
                        risk = (1.0 - dist / risk_radius) * 0.9
                        grid[iy, ix] = max(grid[iy, ix], risk)
        
        # 交通灯风险
        for tl in frame_data.get('traffic_lights', []):
            state = tl.get('state', 'Unknown')
            if state == 'Red':
                # 红灯区域高风险
                tx, ty = tl.get('x', 0), tl.get('y', 0)
                risk_radius = 8.0
                for iy in range(ny):
                    for ix in range(nx):
                        gx = x_min + ix * self.resolution
                        gy = y_min + iy * self.resolution
                        dist = math.sqrt((gx - tx)**2 + (gy - ty)**2)
                        if dist < risk_radius:
                            risk = (1.0 - dist / risk_radius) * 0.5
                            grid[iy, ix] = max(grid[iy, ix], risk)
        
        self.grid = grid
        return grid
    
    def plot(self, frame_data: Dict[str, Any] = None, title: str = "Risk Heatmap",
             save_path: str = None) -> None:
        """
        绘制风险热力图
        
        参数:
            frame_data: 帧数据 (可选，如果提供则计算风险网格)
            title: 标题
            save_path: 保存路径
        """
        if not HAS_MATPLOTLIB:
            return
        
        if frame_data is not None:
            self.compute_risk_grid(frame_data)
        
        if self.grid is None:
            raise ValueError("请先调用 compute_risk_grid 计算风险网格")
        
        fig, ax = plt.subplots(figsize=(10, 8))
        
        x_min, x_max = self.x_range
        y_min, y_max = self.y_range
        
        extent = [x_min, x_max, y_min, y_max]
        
        im = ax.imshow(self.grid, extent=extent, origin='lower',
                      cmap='hot', aspect='equal')
        plt.colorbar(im, ax=ax, label='Risk Level')
        
        # 叠加车辆位置
        if frame_data:
            for v in frame_data.get('vehicles', []):
                ax.plot(v.get('x', 0), v.get('y', 0), 'o', color='cyan', markersize=6)
            
            for p in frame_data.get('pedestrians', []):
                ax.plot(p.get('x', 0), p.get('y', 0), 's', color='green', markersize=5)
        
        ax.set_title(title)
        ax.set_xlabel('X (m)')
        ax.set_ylabel('Y (m)')
        
        if save_path:
            fig.savefig(save_path, bbox_inches='tight')
        
        plt.show()


class TextDashboard:
    """
    文本仪表盘
    用于终端实时监控场景状态
    """
    
    def __init__(self, width: int = 80):
        """
        初始化仪表盘
        
        参数:
            width: 仪表盘宽度 (字符数)
        """
        self.width = width
    
    def render_frame(self, frame_data: Dict[str, Any],
                    ego_id: str = None,
                    risk_info: Dict[str, Any] = None) -> str:
        """
        渲染一帧数据为文本
        
        参数:
            frame_data: 帧数据
            ego_id: 自车 ID
            risk_info: 风险信息
        
        返回:
            格式化的文本仪表盘
        """
        lines = []
        sep = '=' * self.width
        
        lines.append(sep)
        lines.append(f"🚗 AD 安全监控 | 时间戳: {frame_data.get('timestamp', 0)} | 帧ID: {frame_data.get('frame_id', 'N/A')}")
        lines.append(sep)
        
        # 自车信息
        ego = None
        for v in frame_data.get('vehicles', []):
            if (ego_id and v.get('entity_id') == ego_id) or v.get('role_name') == 'ego':
                ego = v
                break
        
        if ego:
            lines.append(f"📍 自车 (Ego):")
            lines.append(f"   位置: ({ego.get('x', 0):.1f}, {ego.get('y', 0):.1f})m")
            lines.append(f"   速度: {ego.get('speed', 0):.1f} m/s ({ego.get('speed', 0) * 3.6:.1f} km/h)")
            lines.append(f"   加速度: {ego.get('throttle', 0):.2f} | 制动: {ego.get('brake', 0):.2f} | 转向: {ego.get('steer', 0):.2f}")
        
        # 环境信息
        vehicles = frame_data.get('vehicles', [])
        pedestrians = frame_data.get('pedestrians', [])
        traffic_lights = frame_data.get('traffic_lights', [])
        obstacles = frame_data.get('obstacles', [])
        
        lines.append(f"\n🌐 环境信息:")
        lines.append(f"   车辆: {len(vehicles)} | 行人: {len(pedestrians)} | 交通灯: {len(traffic_lights)} | 障碍物: {len(obstacles)}")
        
        # 风险信息
        if risk_info:
            lines.append(f"\n⚠️ 风险信息:")
            for key, value in risk_info.items():
                if isinstance(value, float):
                    lines.append(f"   {key}: {value:.3f}")
                else:
                    lines.append(f"   {key}: {value}")
        
        # 违规信息
        violations = frame_data.get('violations', [])
        if violations:
            lines.append(f"\n🚨 违规检测 ({len(violations)}):")
            for i, v in enumerate(violations[:5]):
                lines.append(f"   {i+1}. {v.get('rule', 'unknown')}: {v.get('message', '')}")
        
        lines.append(sep)
        return '\n'.join(lines)