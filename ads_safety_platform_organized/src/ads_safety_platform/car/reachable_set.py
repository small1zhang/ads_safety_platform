"""
汽车轨迹簇与可达范围预测
=========================
在约定的控制量范围内（转向角、油门/刹车加速度），
对控制量空间进行网格采样，利用 trajectory_prediction.predict_trajectory
生成未来5秒的轨迹簇，并计算每个时刻的可达区域（凸包）。

控制量范围约定:
  - 转向角 delta: [-max_steer, +max_steer]  (默认 [-35, +35] deg)
  - 油门/刹车加速度 a_cmd: [-max_brake_decel, +max_throttle_accel]  (默认 [-8, +4] m/s^2)
"""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MplPolygon

from .trajectory_prediction import (
    VehicleParams,
    predict_trajectory,
    make_vehicle_box,
)

plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'KaiTi']
plt.rcParams['axes.unicode_minus'] = False


def convex_hull_2d(points):
    """
    Graham Scan 凸包算法（纯 numpy 实现）。
    
    参数
    ----
    points : np.ndarray, shape (N, 2)
    
    返回
    ----
    hull_points : np.ndarray, shape (M, 2)
        凸包上的有序点集（逆时针）
    hull_indices : np.ndarray, shape (M,)
        凸包点在原始 points 中的索引
    """
    pts = points.copy()
    n = len(pts)
    if n < 3:
        idx = np.arange(n)
        return pts, idx

    pivot_idx = np.argmin(pts[:, 1] * 1e10 + pts[:, 0])
    pivot = pts[pivot_idx]

    def polar_angle(p):
        return np.arctan2(p[1] - pivot[1], p[0] - pivot[0])

    angles = np.array([polar_angle(p) for p in pts])
    dists = np.sum((pts - pivot) ** 2, axis=1)
    order = np.lexsort((dists, angles))

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    stack = []
    stack_indices = []
    for idx in order:
        while len(stack) >= 2 and cross(stack[-2], stack[-1], pts[idx]) <= 0:
            stack.pop()
            stack_indices.pop()
        stack.append(pts[idx])
        stack_indices.append(idx)

    hull_points = np.array(stack)
    hull_indices = np.array(stack_indices)
    return hull_points, hull_indices


def hull_area(hull_points):
    """Shoelace formula 计算多边形面积。"""
    n = len(hull_points)
    if n < 3:
        return 0.0
    x = hull_points[:, 0]
    y = hull_points[:, 1]
    return 0.5 * abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))


def generate_trajectory_bundle(x, y, v, theta,
                               a_range=(-8.0, 4.0),
                               delta_range=None,
                               n_a=5, n_delta=7,
                               dt=0.05, duration=5.0,
                               params=None):
    """
    在控制量空间 (a_cmd, delta) 上做网格采样，生成轨迹簇。

    参数
    ----
    x, y, v, theta : float
        车辆的初始状态（位置、速度、航向角）
    a_range : tuple (a_min, a_max)
        加速度控制范围(m/s²), 负值表示刹车，正值表示油门
    delta_range : tuple (delta_min, delta_max) or None
        转向角范围 (rad), None 则使用车辆最大转向角
    n_a, n_delta : int
        加速度和转向角的采样数
    dt, duration : float
        时间步长和预测总时长（秒）
    params : VehicleParams
        车辆参数

    返回
    ----
    trajectories : list of np.ndarray, each shape (N, 4)
        轨迹列表
    controls : list of (float, float)
        对应的 (a_cmd, delta) 控制输入
    """
    if params is None:
        params = VehicleParams()
    if delta_range is None:
        max_delta = params.max_steer_at_speed(v)
        delta_range = (-max_delta, max_delta)

    a_cmds = np.linspace(a_range[0], a_range[1], n_a)
    deltas = np.linspace(delta_range[0], delta_range[1], n_delta)

    trajectories = []
    controls = []

    for a_cmd in a_cmds:
        for delta in deltas:
            traj = predict_trajectory(
                x, y, v, theta, a_cmd, delta,
                dt=dt, duration=duration, params=params
            )
            trajectories.append(traj)
            controls.append((a_cmd, delta))

    return trajectories, controls


def compute_reachable_sets(trajectories, time_indices=None):
    """
    计算指定时刻的可达区域（凸包）。

    返回
    ----
    reachable_sets : dict { time_index: (hull_points, hull_indices) }
        每个时刻的凸包点集和索引
    """
    N = trajectories[0].shape[0]
    if time_indices is None:
        time_indices = [0, N // 5, 2 * N // 5, 3 * N // 5, 4 * N // 5, N - 1]

    reachable_sets = {}
    for ti in time_indices:
        points = np.array([traj[ti, :2] for traj in trajectories])
        if len(points) >= 3 and np.std(points, axis=0).max() > 1e-6:
            try:
                hull_pts, hull_idx = convex_hull_2d(points)
                if len(hull_pts) >= 3:
                    reachable_sets[ti] = (hull_pts, hull_idx)
            except Exception:
                pass

    return reachable_sets


def plot_trajectory_bundle(trajectories, controls, params=None,
                           reachable_sets=None, dt=0.05,
                           show_boxes=True, box_times=None,
                           title='轨迹簇与可达范围', ax=None):
    """
    绘制轨迹簇 + 可达范围 + 终态车辆盒子。
    """
    if params is None:
        params = VehicleParams()
    if ax is None:
        fig, ax = plt.subplots(1, 1, figsize=(14, 10))

    cmap_a = plt.cm.RdYlGn
    a_values = [c[0] for c in controls]
    a_min, a_max = min(a_values), max(a_values)

    for i, (traj, (a_cmd, delta)) in enumerate(zip(trajectories, controls)):
        a_norm = (a_cmd - a_min) / max(a_max - a_min, 1e-6)
        color = cmap_a(a_norm)
        ax.plot(traj[:, 0], traj[:, 1], '-', color=color,
                linewidth=0.6, alpha=0.5)

    if reachable_sets:
        cmap_t = plt.cm.Blues
        sorted_times = sorted(reachable_sets.keys())
        n_sets = len(sorted_times)
        for idx, ti in enumerate(sorted_times):
            hull_pts, _ = reachable_sets[ti]
            alpha = 0.08 + 0.12 * (idx / max(n_sets - 1, 1))
            color = cmap_t(0.3 + 0.5 * idx / max(n_sets - 1, 1))
            polygon = MplPolygon(hull_pts, closed=True,
                                 facecolor=color, edgecolor=color,
                                 alpha=alpha, linewidth=1.5,
                                 label=f't={ti * dt:.1f}s 可达区域')
            ax.add_patch(polygon)

    if show_boxes:
        if box_times is None:
            box_times_sec = [(trajectories[0].shape[0] - 1) * dt]
        else:
            box_times_sec = box_times

        for t_sec in box_times_sec:
            ti = int(round(t_sec / dt))
            ti = min(ti, trajectories[0].shape[0] - 1)
            for i, (traj, (a_cmd, delta)) in enumerate(zip(trajectories, controls)):
                if i % max(1, len(trajectories) // 30) != 0:
                    continue
                corners = make_vehicle_box(
                    traj[ti, 0], traj[ti, 1], traj[ti, 3],
                    params.length, params.width
                )
                a_norm = (a_cmd - a_min) / max(a_max - a_min, 1e-6)
                color = cmap_a(a_norm)
                polygon = MplPolygon(corners, closed=True,
                                     fill=False, edgecolor=color,
                                     linewidth=0.5, alpha=0.4)
                ax.add_patch(polygon)

    ax.plot(trajectories[0][0, 0], trajectories[0][0, 1],
            'k*', markersize=15, zorder=10, label='起点')

    ax.set_xlabel('X (m)')
    ax.set_ylabel('Y (m)')
    ax.set_aspect('equal')
    ax.grid(True, alpha=0.3)

    sm = plt.cm.ScalarMappable(cmap=cmap_a,
                               norm=plt.Normalize(vmin=a_min, vmax=a_max))
    sm.set_array([])
    cbar = plt.colorbar(sm, ax=ax, shrink=0.6, pad=0.02)
    cbar.set_label('加速度 (m/s^2)')

    if title:
        ax.set_title(title, fontsize=13, fontweight='bold')

    return ax


def plot_reachable_evolution(trajectories, dt=0.05, ax=None):
    """
    绘制可达区域面积和半径随时间的演化。
    """
    if ax is None:
        fig, ax = plt.subplots(1, 1, figsize=(10, 5))

    N = trajectories[0].shape[0]
    areas = []
    radii = []
    times = []

    for ti in range(0, N, max(1, N // 50)):
        points = np.array([traj[ti, :2] for traj in trajectories])
        try:
            hull_pts, hull_idx = convex_hull_2d(points)
            if len(hull_pts) >= 3:
                area = hull_area(hull_pts)
                center = hull_pts.mean(axis=0)
                radius = np.max(np.linalg.norm(hull_pts - center, axis=1))
            else:
                area = 0
                radius = 0
        except Exception:
            area = 0
            radius = 0
        areas.append(area)
        radii.append(radius)
        times.append(ti * dt)

    ax2 = ax.twinx()
    l1, = ax.plot(times, areas, 'b-', linewidth=2, label='可达面积 (m^2)')
    l2, = ax2.plot(times, radii, 'r--', linewidth=2, label='可达半径 (m)')

    ax.set_xlabel('时间 (s)')
    ax.set_ylabel('可达面积 (m^2)', color='b')
    ax2.set_ylabel('可达半径 (m)', color='r')
    ax.set_title('可达范围随时间演化')
    ax.grid(True, alpha=0.3)
    ax.legend([l1, l2], [l1.get_label(), l2.get_label()], loc='upper left')

    return ax


def plot_terminal_states(trajectories, controls, params=None, ax=None):
    """
    绘制终态散点图，颜色编码加速度，叠加车辆盒子和可达边界。
    """
    if params is None:
        params = VehicleParams()
    if ax is None:
        fig, ax = plt.subplots(1, 1, figsize=(10, 8))

    a_values = [c[0] for c in controls]
    a_min, a_max = min(a_values), max(a_values)

    final_x = [traj[-1, 0] for traj in trajectories]
    final_y = [traj[-1, 1] for traj in trajectories]
    final_theta = [traj[-1, 3] for traj in trajectories]

    sc = ax.scatter(final_x, final_y, c=a_values, cmap='RdYlGn',
                    s=30, alpha=0.8, edgecolors='gray', linewidth=0.3)

    for i in range(0, len(trajectories), max(1, len(trajectories) // 15)):
        corners = make_vehicle_box(
            final_x[i], final_y[i], final_theta[i],
            params.length, params.width
        )
        a_norm = (a_values[i] - a_min) / max(a_max - a_min, 1e-6)
        color = plt.cm.RdYlGn(a_norm)
        polygon = MplPolygon(corners, closed=True,
                             fill=False, edgecolor=color,
                             linewidth=0.8, alpha=0.6)
        ax.add_patch(polygon)

    cbar = plt.colorbar(sc, ax=ax, shrink=0.7, pad=0.02)
    cbar.set_label('加速度 (m/s^2)')

    points = np.column_stack([final_x, final_y])
    try:
        hull_pts, _ = convex_hull_2d(points)
        if len(hull_pts) >= 3:
            polygon = MplPolygon(hull_pts, closed=True,
                                 facecolor='none', edgecolor='black',
                                 linewidth=2, linestyle='--',
                                 label='可达边界')
            ax.add_patch(polygon)
            ax.legend(loc='upper left')
    except Exception:
        pass

    ax.set_xlabel('X (m)')
    ax.set_ylabel('Y (m)')
    ax.set_aspect('equal')
    ax.set_title('5秒末态可达范围', fontsize=13, fontweight='bold')
    ax.grid(True, alpha=0.3)

    return ax


def main():
    params = VehicleParams()

    a_range = (-params.max_brake_decel, 4.0)

    print("=" * 60)
    print("汽车轨迹簇与可达范围预测")
    print("=" * 60)
    print(f"控制量范围:")
    print(f"  加速度: [{a_range[0]:.1f}, {a_range[1]:.1f}] m/s^2")
    print(f"  最大转向角(机械): {np.degrees(params.max_steer):.1f} deg")
    print(f"  最大侧向加速度: {params.max_lat_accel:.1f} m/s^2")
    print()

    scenarios = [
        {
            'name': '中速直行 (v=15 m/s)',
            'x': 0, 'y': 0, 'v': 15.0, 'theta': 0,
            'n_a': 9, 'n_delta': 11,
        },
        {
            'name': '低速转弯 (v=5 m/s, theta=15 deg)',
            'x': 0, 'y': 0, 'v': 5.0, 'theta': np.radians(15),
            'n_a': 7, 'n_delta': 9,
        },
        {
            'name': '高速直行 (v=30 m/s)',
            'x': 0, 'y': 0, 'v': 30.0, 'theta': 0,
            'n_a': 9, 'n_delta': 11,
        },
    ]

    dt = 0.05
    duration = 5.0
    N = int(duration / dt) + 1

    for sc in scenarios:
        max_delta_v = params.max_steer_at_speed(sc['v'])
        print(f"\n--- {sc['name']} ---")
        print(f"  初始状态: pos=({sc['x']}, {sc['y']}), "
              f"v={sc['v']} m/s, theta={np.degrees(sc['theta']):.1f} deg")
        print(f"  当前速度下最大转向角: {np.degrees(max_delta_v):.1f} deg "
              f"(机械极限: {np.degrees(params.max_steer):.1f} deg)")

        trajectories, controls = generate_trajectory_bundle(
            sc['x'], sc['y'], sc['v'], sc['theta'],
            a_range=a_range,
            n_a=sc['n_a'], n_delta=sc['n_delta'],
            dt=dt, duration=duration, params=params
        )
        print(f"  生成轨迹数: {len(trajectories)}")

        time_indices = [N // 5, 2 * N // 5, 3 * N // 5, 4 * N // 5, N - 1]
        reachable_sets = compute_reachable_sets(trajectories, time_indices)
        print(f"  可达区域凸包数: {len(reachable_sets)}")

        final_points = np.array([traj[-1, :2] for traj in trajectories])
        try:
            hull_pts, hull_idx = convex_hull_2d(final_points)
            if len(hull_pts) >= 3:
                area = hull_area(hull_pts)
                center = hull_pts.mean(axis=0)
                radius = np.max(np.linalg.norm(hull_pts - center, axis=1))
                print(f"  末态可达面积: {area:.1f} m^2")
                print(f"  末态可达半径: {radius:.1f} m")
        except Exception:
            pass

        fig = plt.figure(figsize=(20, 14))
        gs = fig.add_gridspec(2, 2, hspace=0.3, wspace=0.3)

        ax1 = fig.add_subplot(gs[0, :])
        plot_trajectory_bundle(
            trajectories, controls, params=params,
            reachable_sets=reachable_sets, dt=dt,
            show_boxes=True, box_times=[5.0],
            title=f'{sc["name"]} — 轨迹簇与可达范围',
            ax=ax1
        )

        ax2 = fig.add_subplot(gs[1, 0])
        plot_terminal_states(trajectories, controls, params=params, ax=ax2)

        ax3 = fig.add_subplot(gs[1, 1])
        plot_reachable_evolution(trajectories, dt=dt, ax=ax3)

        fig.suptitle(
            f'可达范围预测 — {sc["name"]}\n'
            f'加速度: [{a_range[0]:.0f}, {a_range[1]:.0f}] m/s^2, '
            f'初始最大转向角: {np.degrees(max_delta_v):.1f} deg '
            f'(a_lat_max={params.max_lat_accel} m/s^2), '
            f'采样: {sc["n_a"]}x{sc["n_delta"]}={len(trajectories)} 条轨迹',
            fontsize=14, fontweight='bold', y=1.02
        )

        safe_name = sc['name'].replace(' ', '_').replace('(', '').replace(')', '') \
            .replace('/', '_').replace('=', '')
        fname = f'reachable_{safe_name}.png'
        plt.savefig(fname, dpi=150, bbox_inches='tight')
        print(f"  图已保存: {fname}")

    plt.show()
    print("\n全部完成!")


if __name__ == '__main__':
    main()
