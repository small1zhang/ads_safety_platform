"""
两车对向碰撞预测
==================
A车（可控）与B车（匀速直线）的碰撞预测判断。

输入:
  A车: 初始位置、速度、航向角
  B车: 初始位置、速度、航向角

输出:
  - 是否必然碰撞（所有可达轨迹均碰撞）
  - 若非必然碰撞，输出安全控制边界 [a_cmd, delta] 范围

碰撞检测采用 SAT (Separating Axis Theorem) 算法，
考虑两车的大小 (5m x 2m) 和航向角。
"""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MplPolygon

from .trajectory_prediction import (
    VehicleParams,
    predict_trajectory,
    make_vehicle_box,
)
from .reachable_set import (
    generate_trajectory_bundle,
    convex_hull_2d,
)

plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'KaiTi']
plt.rcParams['axes.unicode_minus'] = False


def predict_b_trajectory(x, y, v, theta, dt=0.05, duration=5.0):
    """
    B车匀速直线运动预测。
    输入:
      x, y: 初始位置
      v: 速度
      theta: 航向角
      dt: 时间间隔
      duration: 预测时长
    返回:
      traj: shape (N, 4) 的数组: [x, y, v, theta]
    """
    N = int(duration / dt) + 1
    traj = np.zeros((N, 4))
    for i in range(N):
        t = i * dt
        traj[i, 0] = x + v * np.cos(theta) * t
        traj[i, 1] = y + v * np.sin(theta) * t
        traj[i, 2] = v
        traj[i, 3] = theta
    return traj


def rect_axes(corners):
    """
    从矩形四角提取两条边的方向向量（SAT 投影轴）。
    corners: shape (4, 2), 顺序为 [FL, FR, BR, BL] 或类似
    """
    edge1 = corners[1] - corners[0]
    edge2 = corners[3] - corners[0]
    axes = []
    for edge in [edge1, edge2]:
        length = np.linalg.norm(edge)
        if length > 1e-10:
            normal = np.array([-edge[1], edge[0]]) / length
            axes.append(normal)
    return axes


def project_polygon(corners, axis):
    """将多边形顶点投影到轴上，返回 (min, max)。"""
    projections = corners @ axis
    return projections.min(), projections.max()


def rects_overlap(corners_a, corners_b):
    """
    SAT 判断两个凸多边形（矩形）是否重叠。
    返回 True 表示碰撞。
    """
    axes = rect_axes(corners_a) + rect_axes(corners_b)
    for axis in axes:
        min_a, max_a = project_polygon(corners_a, axis)
        min_b, max_b = project_polygon(corners_b, axis)
        if max_a < min_b or max_b < min_a:
            return False
    return True


def check_collision_at_time(traj_a, traj_b, ti, params):
    """
    检查第 ti 时刻两车是否碰撞。
    """
    corners_a = make_vehicle_box(
        traj_a[ti, 0], traj_a[ti, 1], traj_a[ti, 3],
        params.length, params.width
    )
    corners_b = make_vehicle_box(
        traj_b[ti, 0], traj_b[ti, 1], traj_b[ti, 3],
        params.length, params.width
    )
    return rects_overlap(corners_a, corners_b)


def check_trajectory_collision(traj_a, traj_b, params, check_interval=2):
    """
    检查整条 A 轨迹是否与 B 轨迹在任何时刻发生碰撞。
    check_interval: 每隔几个采样点检查一次（加速计算）。
    返回: (is_colliding, collision_time_index)
    """
    N = min(traj_a.shape[0], traj_b.shape[0])
    for ti in range(0, N, check_interval):
        if check_collision_at_time(traj_a, traj_b, ti, params):
            return True, ti
    return False, -1


def analyze_collision(x_a, y_a, v_a, theta_a,
                      x_b, y_b, v_b, theta_b,
                      a_range=(-8.0, 4.0),
                      n_a=11, n_delta=13,
                      dt=0.05, duration=5.0,
                      params=None):
    """
    两车碰撞预测分析。

    参数
    ----
    x_a, y_a, v_a, theta_a : A车初始状态
    x_b, y_b, v_b, theta_b : B车初始状态
    a_range : A车加速度采样范围
    n_a, n_delta : 采样网格密度

    返回
    ----
    result : dict
        inevitable : bool, 是否必然碰撞
        safe_controls : list of (a_cmd, delta), 安全控制组合
        unsafe_controls : list of (a_cmd, delta), 碰撞控制组合
        safe_boundary : dict with 'a_min', 'a_max', 'delta_min', 'delta_max'
        trajectories : list of traj
        controls : list of (a_cmd, delta)
        collision_flags : list of bool
        collision_times : list of int
        traj_b : B车轨迹
    """
    if params is None:
        params = VehicleParams()

    traj_b = predict_b_trajectory(x_b, y_b, v_b, theta_b, dt, duration)

    trajectories, controls = generate_trajectory_bundle(
        x_a, y_a, v_a, theta_a,
        a_range=a_range,
        n_a=n_a, n_delta=n_delta,
        dt=dt, duration=duration, params=params
    )

    collision_flags = []
    collision_times = []

    for traj_a in trajectories:
        is_colliding, col_ti = check_trajectory_collision(
            traj_a, traj_b, params, check_interval=2
        )
        collision_flags.append(is_colliding)
        collision_times.append(col_ti)

    n_total = len(trajectories)
    n_colliding = sum(collision_flags)
    n_safe = n_total - n_colliding

    inevitable = (n_safe == 0)

    safe_controls = []
    unsafe_controls = []
    for i, (a_cmd, delta) in enumerate(controls):
        if collision_flags[i]:
            unsafe_controls.append((a_cmd, delta))
        else:
            safe_controls.append((a_cmd, delta))

    safe_boundary = None
    if safe_controls:
        safe_a = [c[0] for c in safe_controls]
        safe_d = [c[1] for c in safe_controls]
        safe_boundary = {
            'a_min': min(safe_a),
            'a_max': max(safe_a),
            'delta_min': min(safe_d),
            'delta_max': max(safe_d),
        }

    return {
        'inevitable': inevitable,
        'n_total': n_total,
        'n_colliding': n_colliding,
        'n_safe': n_safe,
        'safe_controls': safe_controls,
        'unsafe_controls': unsafe_controls,
        'safe_boundary': safe_boundary,
        'trajectories': trajectories,
        'controls': controls,
        'collision_flags': collision_flags,
        'collision_times': collision_times,
        'traj_b': traj_b,
    }


def plot_collision_analysis(result, params=None, title=None):
    """
    绘制碰撞分析结果（大图，含轨迹簇、碰撞时序、控制边界）。
    """
    if params is None:
        params = VehicleParams()

    fig = plt.figure(figsize=(22, 16))
    gs = fig.add_gridspec(2, 2, hspace=0.3, wspace=0.3)

    ax_traj = fig.add_subplot(gs[0, :])
    ax_ctrl = fig.add_subplot(gs[1, 0])
    ax_time = fig.add_subplot(gs[1, 1])

    trajectories = result['trajectories']
    controls = result['controls']
    collision_flags = result['collision_flags']
    collision_times = result['collision_times']
    traj_b = result['traj_b']

    dt = 0.05

    # ===== 子图1: 轨迹簇 + B车 + 碰撞标记 =====
    ax = ax_traj

    for i, (traj_a, (a_cmd, delta)) in enumerate(zip(trajectories, controls)):
        if collision_flags[i]:
            col_ti = collision_times[i]
            ax.plot(traj_a[:col_ti + 1, 0], traj_a[:col_ti + 1, 1],
                    'r-', linewidth=0.5, alpha=0.4)
            ax.plot(traj_a[col_ti, 0], traj_a[col_ti, 1],
                    'rx', markersize=3, alpha=0.5)
        else:
            ax.plot(traj_a[:, 0], traj_a[:, 1],
                    'g-', linewidth=0.7, alpha=0.6)

    ax.plot(traj_b[:, 0], traj_b[:, 1], 'b-', linewidth=3, label='B车轨迹')

    for ti in range(0, traj_b.shape[0], traj_b.shape[0] // 5):
        corners_b = make_vehicle_box(
            traj_b[ti, 0], traj_b[ti, 1], traj_b[ti, 3],
            params.length, params.width
        )
        polygon = MplPolygon(corners_b, closed=True,
                             facecolor='blue', edgecolor='blue',
                             alpha=0.15, linewidth=1)
        ax.add_patch(polygon)

    box_step = max(1, len(trajectories) // 20)
    for i, (traj_a, (a_cmd, delta)) in enumerate(zip(trajectories, controls)):
        if i % box_step != 0:
            continue
        corners_a = make_vehicle_box(
            traj_a[-1, 0], traj_a[-1, 1], traj_a[-1, 3],
            params.length, params.width
        )
        color = 'red' if collision_flags[i] else 'green'
        polygon = MplPolygon(corners_a, closed=True,
                             fill=False, edgecolor=color,
                             linewidth=0.6, alpha=0.4)
        ax.add_patch(polygon)

    ax.plot(trajectories[0][0, 0], trajectories[0][0, 1],
            'r*', markersize=15, zorder=10, label='A车起点')
    ax.plot(traj_b[0, 0], traj_b[0, 1],
            'b*', markersize=15, zorder=10, label='B车起点')

    ax.set_xlabel('X (m)')
    ax.set_ylabel('Y (m)')
    ax.set_aspect('equal')
    ax.grid(True, alpha=0.3)
    ax.legend(loc='upper left', fontsize=9)

    status = "必然碰撞!" if result['inevitable'] else "可规避"
    color = 'red' if result['inevitable'] else 'green'
    ax.set_title(f'轨迹簇碰撞分析 — {status}', fontsize=13,
                 fontweight='bold', color=color)

    info = (f"A车: v={trajectories[0][0, 2]:.1f} m/s\n"
            f"B车: v={traj_b[0, 2]:.1f} m/s\n"
            f"碰撞轨迹: {result['n_colliding']}/{result['n_total']}\n"
            f"安全轨迹: {result['n_safe']}/{result['n_total']}")
    ax.text(0.98, 0.98, info, transform=ax.transAxes,
            fontsize=9, verticalalignment='top', horizontalalignment='right',
            bbox=dict(boxstyle='round,pad=0.4', facecolor='lightyellow', alpha=0.9))

    # ===== 子图2: 控制空间 (a_cmd vs delta) 安全/碰撞分布 =====
    ax = ax_ctrl

    if result['unsafe_controls']:
        ua = [c[0] for c in result['unsafe_controls']]
        ud = [np.degrees(c[1]) for c in result['unsafe_controls']]
        ax.scatter(ua, ud, c='red', s=15, alpha=0.5, label='碰撞区域')

    if result['safe_controls']:
        sa = [c[0] for c in result['safe_controls']]
        sd = [np.degrees(c[1]) for c in result['safe_controls']]
        ax.scatter(sa, sd, c='green', s=15, alpha=0.5, label='安全区域')

    if result['safe_boundary']:
        sb = result['safe_boundary']
        rect = plt.Rectangle(
            (sb['a_min'], np.degrees(sb['delta_min'])),
            sb['a_max'] - sb['a_min'],
            np.degrees(sb['delta_max']) - np.degrees(sb['delta_min']),
            fill=False, edgecolor='green', linewidth=2.5,
            linestyle='--', label='安全边界'
        )
        ax.add_patch(rect)
        ax.text(sb['a_min'], np.degrees(sb['delta_min']) - 0.5,
                f"  a:[{sb['a_min']:.1f}, {sb['a_max']:.1f}]\n"
                f"  delta:[{np.degrees(sb['delta_min']):.1f}, "
                f"{np.degrees(sb['delta_max']):.1f}] deg",
                fontsize=8, color='green',
                bbox=dict(facecolor='white', alpha=0.8))

    ax.set_xlabel('加速度 a_cmd (m/s^2)')
    ax.set_ylabel('转向角 delta (deg)')
    ax.set_title('控制空间安全/碰撞分布', fontsize=12, fontweight='bold')
    ax.grid(True, alpha=0.3)
    ax.legend(loc='upper left', fontsize=8)

    # ===== 子图3: 碰撞时间分布 =====
    ax = ax_time

    col_times_sec = []
    col_a_vals = []
    for i, (flag, ti) in enumerate(zip(collision_flags, collision_times)):
        if flag:
            col_times_sec.append(ti * dt)
            col_a_vals.append(controls[i][0])

    if col_times_sec:
        sc = ax.scatter(col_times_sec, col_a_vals, c='red', s=10, alpha=0.5)
        ax.set_xlabel('首次碰撞时间 (s)')
        ax.set_ylabel('加速度 (m/s^2)')
        ax.set_title('碰撞轨迹的首次碰撞时间分布', fontsize=12, fontweight='bold')
        ax.axvline(x=min(col_times_sec), color='orange', linestyle='--',
                   linewidth=1.5, label=f'最早碰撞: {min(col_times_sec):.2f}s')
        ax.axvline(x=max(col_times_sec), color='darkred', linestyle='--',
                   linewidth=1.5, label=f'最晚碰撞: {max(col_times_sec):.2f}s')
        ax.legend(fontsize=8)
    else:
        ax.text(0.5, 0.5, '无碰撞轨迹', transform=ax.transAxes,
                fontsize=16, ha='center', va='center', color='green',
                fontweight='bold')
        ax.set_title('碰撞时间分布', fontsize=12, fontweight='bold')
    ax.grid(True, alpha=0.3)

    if title:
        fig.suptitle(title, fontsize=14, fontweight='bold', y=1.01)

    return fig


def main():
    params = VehicleParams()

    scenarios = [
        {
            'name': '场景1: 近距离对撞 - 必然碰撞',
            'A': {'x': -15, 'y': -0.3, 'v': 20.0, 'theta': 0},
            'B': {'x': 15, 'y': 0.3, 'v': 20.0, 'theta': np.pi},
            'a_range': (-8.0, 4.0),
            'n_a': 11, 'n_delta': 13,
        },
        {
            'name': '场景2: 对向偏移 - 可规避',
            'A': {'x': -50, 'y': -3, 'v': 15.0, 'theta': 0},
            'B': {'x': 50, 'y': 3, 'v': 15.0, 'theta': np.pi},
            'a_range': (-8.0, 4.0),
            'n_a': 11, 'n_delta': 13,
        },
        {
            'name': '场景3: 侧面来车 - 可规避',
            'A': {'x': 0, 'y': 0, 'v': 15.0, 'theta': 0},
            'B': {'x': 50, 'y': -30, 'v': 15.0, 'theta': np.radians(110)},
            'a_range': (-8.0, 4.0),
            'n_a': 11, 'n_delta': 13,
        },
        {
            'name': '场景4: B车迎面斜插',
            'A': {'x': 0, 'y': 0, 'v': 10.0, 'theta': 0},
            'B': {'x': 30, 'y': -20, 'v': 12.0, 'theta': np.radians(150)},
            'a_range': (-8.0, 4.0),
            'n_a': 11, 'n_delta': 13,
        },
    ]

    print("=" * 60)
    print("两车碰撞预测分析")
    print("=" * 60)
    print(f"车辆尺寸: {params.length}m x {params.width}m")
    print(f"最大侧向加速度: {params.max_lat_accel} m/s^2")
    print()

    for sc in scenarios:
        print(f"\n{'='*50}")
        print(f"  {sc['name']}")
        print(f"{'='*50}")
        a = sc['A']
        b = sc['B']
        print(f"  A车: pos=({a['x']}, {a['y']}), v={a['v']} m/s, "
              f"theta={np.degrees(a['theta']):.1f} deg")
        print(f"  B车: pos=({b['x']}, {b['y']}), v={b['v']} m/s, "
              f"theta={np.degrees(b['theta']):.1f} deg")

        result = analyze_collision(
            a['x'], a['y'], a['v'], a['theta'],
            b['x'], b['y'], b['v'], b['theta'],
            a_range=sc['a_range'],
            n_a=sc['n_a'], n_delta=sc['n_delta'],
            params=params
        )

        print(f"\n  --- 分析结果 ---")
        if result['inevitable']:
            print(f"  [!] 必然碰撞! 所有 {result['n_total']} 条轨迹均碰撞")
            col_times = [t * 0.05 for t in result['collision_times'] if t >= 0]
            if col_times:
                print(f"  最早碰撞时间: {min(col_times):.2f}s")
                print(f"  最晚碰撞时间: {max(col_times):.2f}s")
        else:
            print(f"  [OK] 可规避!")
            print(f"    碰撞轨迹: {result['n_colliding']}/{result['n_total']}")
            print(f"    安全轨迹: {result['n_safe']}/{result['n_total']}")
            if result['safe_boundary']:
                sb = result['safe_boundary']
                print(f"    安全控制边界:")
                print(f"      加速度: [{sb['a_min']:.2f}, {sb['a_max']:.2f}] m/s^2")
                print(f"      转向角: [{np.degrees(sb['delta_min']):.2f}, "
                      f"{np.degrees(sb['delta_max']):.2f}] deg")

        fig = plot_collision_analysis(
            result, params=params,
            title=f'{sc["name"]} — '
                  f'A({a["v"]:.0f}m/s) vs B({b["v"]:.0f}m/s)'
        )

        safe_name = sc['name'].split(':')[0].replace(' ', '_')
        fname = f'collision_{safe_name}.png'
        plt.savefig(fname, dpi=150, bbox_inches='tight')
        print(f"  图已保存: {fname}")

    plt.show()
    print("\n全部完成!")


if __name__ == '__main__':
    main()
