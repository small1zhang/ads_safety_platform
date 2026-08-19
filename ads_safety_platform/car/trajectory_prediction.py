"""
汽车轨迹预测脚本
=================
基于运动学自行车模型(Kinematic Bicycle Model)，考虑最大功率约束，
根据当前位置、速度、航向角以及油门/刹车、转向角输入，预测未来5秒轨迹。

状态量: [x, y, v, θ]  — 位置(x,y)、速度v、航向角θ
控制量: [a_cmd, δ]    — 油门/刹车指令加速度、转向角

车辆建模为 5m×2m 的盒子（考虑航向角旋转）。
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.transforms import Affine2D

plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'KaiTi']
plt.rcParams['axes.unicode_minus'] = False


class VehicleParams:
    mass = 1500.0
    length = 5.0
    width = 2.0
    wheelbase = 2.7
    lf = 1.35
    lr = 1.35
    max_power = 150000.0
    max_steer = np.radians(35)
    max_brake_decel = 8.0
    max_accel_force = 7000.0
    Cd = 0.3
    frontal_area = 2.2
    air_density = 1.225
    Cr = 0.015
    gravity = 9.81
    max_lat_accel = 4.5

    def max_steer_at_speed(self, v):
        """
        根据当前速度计算允许的最大转向角 (rad)。
        约束条件: 侧向加速度 a_lat = v^2 * tan(delta) / L <= max_lat_accel
        因此: delta_max(v) = arctan(max_lat_accel * L / v^2)
        低速时受机械最大转向角限制，高速时受侧向加速度限制。
        """
        if v < 1e-3:
            return self.max_steer
        delta_lat = np.arctan(self.max_lat_accel * self.wheelbase / (v * v))
        return min(delta_lat, self.max_steer)


def compute_acceleration(v, a_cmd, params):
    """
    根据油门/刹车指令和功率约束计算实际加速度。
    a_cmd > 0: 油门加速; a_cmd < 0: 刹车减速
    """
    if abs(v) < 1e-3 and a_cmd > 0:
        F_throttle = min(a_cmd * params.mass, params.max_accel_force)
    elif a_cmd > 0:
        F_power = params.max_power / max(abs(v), 0.5)
        F_throttle = min(a_cmd * params.mass, params.max_accel_force, F_power)
    else:
        F_throttle = 0.0

    F_drag = (0.5 * params.air_density * params.Cd *
              params.frontal_area * v * v)
    sign_v = 1.0 if v >= 0 else -1.0
    F_roll = params.Cr * params.mass * params.gravity * sign_v

    F_brake = 0.0
    if a_cmd < 0:
        F_brake = max(a_cmd * params.mass, -params.max_brake_decel * params.mass)
        if v > 0:
            F_brake = max(F_brake, -params.mass * v / 0.01)

    F_total = F_throttle - F_drag - F_roll + F_brake
    a_actual = F_total / params.mass

    if v <= 0 and a_actual < 0:
        a_actual = 0.0
    if v < 0:
        v = 0.0

    return a_actual


def kinematic_bicycle_deriv(state, a_cmd, delta, params):
    """
    运动学自行车模型微分方程。
    state = [x, y, v, theta]
    """
    x, y, v, theta = state

    max_delta = params.max_steer_at_speed(v)
    delta = np.clip(delta, -max_delta, max_delta)

    a = compute_acceleration(v, a_cmd, params)

    dx = v * np.cos(theta)
    dy = v * np.sin(theta)
    dtheta = v * np.tan(delta) / params.wheelbase
    dv = a

    return np.array([dx, dy, dv, dtheta])


def rk4_step(state, a_cmd, delta, params, dt):
    """四阶 Runge-Kutta 积分一步。"""
    k1 = kinematic_bicycle_deriv(state, a_cmd, delta, params)
    k2 = kinematic_bicycle_deriv(state + 0.5 * dt * k1, a_cmd, delta, params)
    k3 = kinematic_bicycle_deriv(state + 0.5 * dt * k2, a_cmd, delta, params)
    k4 = kinematic_bicycle_deriv(state + dt * k3, a_cmd, delta, params)
    new_state = state + (dt / 6.0) * (k1 + 2 * k2 + 2 * k3 + k4)
    new_state[2] = max(new_state[2], 0.0)
    return new_state


def predict_trajectory(x, y, v, theta, a_cmd, delta,
                       dt=0.05, duration=5.0, params=None):
    """
    预测未来轨迹。

    参数
    ----
    x, y : float
        初始位置 (m)
    v : float
        初始速度 (m/s), >= 0
    theta : float
        初始航向角 (rad), 0 为沿 +x 方向, 逆时针为正
    a_cmd : float
        油门/刹车指令加速度 (m/s^2)
        > 0 油门加速, < 0 刹车减速
    delta : float
        转向角 (rad), 左转为正, 右转为负
    dt : float
        积分时间步长 (s)
    duration : float
        预测时长 (s)
    params : VehicleParams, optional
        车辆参数

    返回
    ----
    traj : np.ndarray, shape (N, 4)
        每行 [x, y, v, theta], N = int(duration/dt) + 1
    """
    if params is None:
        params = VehicleParams()

    N = int(duration / dt) + 1
    traj = np.zeros((N, 4))
    state = np.array([x, y, max(v, 0.0), theta], dtype=float)
    traj[0] = state.copy()

    for i in range(1, N):
        state = rk4_step(state, a_cmd, delta, params, dt)
        traj[i] = state.copy()

    return traj


def make_vehicle_box(x, y, theta, length=5.0, width=2.0):
    """
    生成车辆盒子四个角点坐标（世界坐标系），后轴为中心参考点。
    这里将后轴设为车尾往后 lr 处，即盒子几何中心偏前。
    实际简化：以 (x,y) 为盒子中心。
    """
    corners = np.array([
        [-length / 2, -width / 2],
        [length / 2, -width / 2],
        [length / 2, width / 2],
        [-length / 2, width / 2],
    ])
    R = np.array([
        [np.cos(theta), -np.sin(theta)],
        [np.sin(theta), np.cos(theta)],
    ])
    rotated = corners @ R.T
    rotated[:, 0] += x
    rotated[:, 1] += y
    return rotated


def plot_trajectory(traj, a_cmd, delta, params=None, title=None,
                    show_boxes=True, box_interval=0.5, ax=None):
    """
    绘制轨迹及车辆盒子。

    参数
    ----
    traj : np.ndarray, shape (N, 4)
        predict_trajectory 的输出
    box_interval : float
        每隔多少秒绘制一个车辆盒子
    """
    if params is None:
        params = VehicleParams()
    if ax is None:
        fig, ax = plt.subplots(1, 1, figsize=(14, 8))

    xs, ys, vs, thetas = traj[:, 0], traj[:, 1], traj[:, 2], traj[:, 3]

    ax.plot(xs, ys, 'b-', linewidth=1.5, label='预测轨迹')

    ax.plot(xs[0], ys[0], 'go', markersize=10, label='起点', zorder=5)
    ax.plot(xs[-1], ys[-1], 'rs', markersize=10, label='终点', zorder=5)

    if show_boxes:
        dt_traj = 0.05
        step = max(1, int(box_interval / dt_traj))
        indices = list(range(0, len(traj), step))
        if indices[-1] != len(traj) - 1:
            indices.append(len(traj) - 1)

        n_boxes = len(indices)
        cmap = plt.cm.plasma
        for idx, i in enumerate(indices):
            color = cmap(idx / max(n_boxes - 1, 1))
            corners = make_vehicle_box(
                xs[i], ys[i], thetas[i],
                params.length, params.width
            )
            polygon = plt.Polygon(
                corners, closed=True,
                fill=False, edgecolor=color, linewidth=1.2, alpha=0.8
            )
            ax.add_patch(polygon)

            dx = np.cos(thetas[i]) * params.length * 0.4
            dy = np.sin(thetas[i]) * params.length * 0.4
            ax.annotate('', xy=(xs[i] + dx, ys[i] + dy), xytext=(xs[i], ys[i]),
                        arrowprops=dict(arrowstyle='->', color=color, lw=1.2))

    ax.set_xlabel('X (m)')
    ax.set_ylabel('Y (m)')
    ax.set_aspect('equal')
    ax.grid(True, alpha=0.3)
    ax.legend(loc='upper left', fontsize=9)

    steer_deg = np.degrees(delta)
    info_text = (
        f'指令加速度: {a_cmd:+.2f} m/s^2\n'
        f'转向角: {steer_deg:+.1f}°\n'
        f'初速度: {traj[0, 2]:.1f} m/s '
        f'({traj[0, 2] * 3.6:.1f} km/h)\n'
        f'末速度: {traj[-1, 2]:.1f} m/s '
        f'({traj[-1, 2] * 3.6:.1f} km/h)'
    )
    ax.text(0.98, 0.98, info_text, transform=ax.transAxes,
            fontsize=9, verticalalignment='top', horizontalalignment='right',
            bbox=dict(boxstyle='round,pad=0.4', facecolor='lightyellow', alpha=0.9))

    if title:
        ax.set_title(title)

    return ax


def demo():
    """运行多个场景的演示。"""
    params = VehicleParams()

    scenarios = [
        {
            'name': '场景1: 匀速直行',
            'x': 0, 'y': 0, 'v': 20.0, 'theta': 0,
            'a_cmd': 0.0, 'delta': 0.0,
        },
        {
            'name': '场景2: 油门加速 + 左转弯',
            'x': 0, 'y': 0, 'v': 10.0, 'theta': 0,
            'a_cmd': 2.0, 'delta': np.radians(10),
        },
        {
            'name': '场景3: 刹车减速 + 右转弯',
            'x': 0, 'y': 0, 'v': 25.0, 'theta': 0,
            'a_cmd': -3.0, 'delta': np.radians(-8),
        },
        {
            'name': '场景4: 急刹车直行',
            'x': 0, 'y': 0, 'v': 30.0, 'theta': 0,
            'a_cmd': -6.0, 'delta': 0.0,
        },
        {
            'name': '场景5: 大转向角蛇形',
            'x': 0, 'y': 0, 'v': 15.0, 'theta': 0,
            'a_cmd': 0.5, 'delta': np.radians(20),
        },
        {
            'name': '场景6: 原地起步 + 转弯',
            'x': 0, 'y': 0, 'v': 0.5, 'theta': np.radians(30),
            'a_cmd': 3.0, 'delta': np.radians(15),
        },
    ]

    fig, axes = plt.subplots(2, 3, figsize=(20, 12))
    axes = axes.flatten()

    for idx, sc in enumerate(scenarios):
        traj = predict_trajectory(
            sc['x'], sc['y'], sc['v'], sc['theta'],
            sc['a_cmd'], sc['delta'],
            dt=0.05, duration=5.0, params=params
        )
        plot_trajectory(
            traj, sc['a_cmd'], sc['delta'], params=params,
            title=sc['name'], ax=axes[idx],
            show_boxes=True, box_interval=0.5
        )

    fig.suptitle(
        '汽车轨迹预测 (运动学自行车模型 + 功率约束)\n'
        f'车辆: {params.length}m×{params.width}m, '
        f'质量: {params.mass}kg, '
        f'最大功率: {params.max_power / 1000:.0f}kW, '
        f'轴距: {params.wheelbase}m',
        fontsize=14, fontweight='bold'
    )
    plt.tight_layout()
    plt.savefig('trajectory_prediction_demo.png', dpi=150, bbox_inches='tight')
    plt.show()
    print("演示图已保存为 trajectory_prediction_demo.png")


def demo_single():
    """单一场景详细展示。"""
    params = VehicleParams()

    print("=" * 60)
    print("汽车轨迹预测演示")
    print("=" * 60)
    print(f"车辆参数:")
    print(f"  尺寸: {params.length}m × {params.width}m")
    print(f"  质量: {params.mass}kg")
    print(f"  最大功率: {params.max_power / 1000:.0f} kW")
    print(f"  轴距: {params.wheelbase}m")
    print(f"  最大转向角: {np.degrees(params.max_steer):.0f}°")
    print()

    x, y = 0.0, 0.0
    v = 15.0
    theta = 0.0
    a_cmd = 1.5
    delta = np.radians(12)

    print(f"初始状态: 位置=({x}, {y}), 速度={v}m/s ({v*3.6:.0f}km/h), "
          f"航向角={np.degrees(theta):.1f}°")
    print(f"控制输入: 油门加速度={a_cmd}m/s^2, 转向角={np.degrees(delta):.1f}°")
    print()

    traj = predict_trajectory(x, y, v, theta, a_cmd, delta,
                              dt=0.05, duration=5.0, params=params)

    print(f"预测结果 (5秒, {len(traj)} 个采样点):")
    print(f"  终点: ({traj[-1, 0]:.2f}, {traj[-1, 1]:.2f})")
    print(f"  末速度: {traj[-1, 2]:.2f} m/s ({traj[-1, 2]*3.6:.1f} km/h)")
    print(f"  末航向: {np.degrees(traj[-1, 3]):.1f}°")

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 7))

    plot_trajectory(traj, a_cmd, delta, params=params,
                    title='轨迹 + 车辆盒子', ax=ax1)

    t = np.linspace(0, 5, len(traj))
    ax2.plot(t, traj[:, 2], 'r-', linewidth=2, label='速度 (m/s)')
    ax2_twin = ax2.twinx()
    ax2_twin.plot(t, np.degrees(traj[:, 3]), 'b--', linewidth=2,
                  label='航向角 (°)')

    ax2.set_xlabel('时间 (s)')
    ax2.set_ylabel('速度 (m/s)', color='r')
    ax2_twin.set_ylabel('航向角 (°)', color='b')
    ax2.set_title('速度和航向角随时间变化')
    ax2.grid(True, alpha=0.3)

    lines1, labels1 = ax2.get_legend_handles_labels()
    lines2, labels2 = ax2_twin.get_legend_handles_labels()
    ax2.legend(lines1 + lines2, labels1 + labels2, loc='upper left')

    fig.suptitle('汽车轨迹预测 — 油门加速+左转弯', fontsize=14, fontweight='bold')
    plt.tight_layout()
    plt.savefig('trajectory_single_demo.png', dpi=150, bbox_inches='tight')
    plt.show()
    print("详细演示图已保存为 trajectory_single_demo.png")


if __name__ == '__main__':
    demo_single()
    demo()
