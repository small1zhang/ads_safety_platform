import carla
import numpy as np
import math
import random

NORMAL_DRIVING_TEST = True

class LaneKeepingAgent:
    """车道保持 Agent"""
    def __init__(self, vehicle, target_speed=20.0):
        self.vehicle = vehicle
        self.target_speed = target_speed
        self.last_steer = 0.0

    def run_step(self, map):
        """执行一步控制"""
        wp = map.get_waypoint(self.vehicle.get_location(), lane_type=carla.LaneType.Driving)
        look_wp = wp.next(10.0)[0]
        target = np.array([look_wp.transform.location.x, look_wp.transform.location.y])

        ego = np.array([self.vehicle.get_location().x, self.vehicle.get_location().y])
        yaw = math.radians(self.vehicle.get_transform().rotation.yaw)
        dx = target[0] - ego[0]
        dy = target[1] - ego[1]

        alpha = math.atan2(dy, dx) - yaw
        alpha = math.atan2(math.sin(alpha), math.cos(alpha))

        if NORMAL_DRIVING_TEST:
            steer = 0.5 * alpha
        else:
            steer = 0.4 * alpha + random.uniform(-0.25, 0.25)
        
        steer = np.clip(steer, -0.3, 0.3)
        steer = 0.8 * self.last_steer + 0.2 * steer
        self.last_steer = steer

        speed = math.hypot(self.vehicle.get_velocity().x, self.vehicle.get_velocity().y)
        control = carla.VehicleControl()
        control.steer = steer

        if speed * 3.6 < self.target_speed - 2:
            control.throttle = 0.5
            control.brake = 0.0
        elif speed * 3.6 > self.target_speed + 2:
            control.brake = 0.2
            control.throttle = 0.0
        else:
            control.throttle = 0.2
            control.brake = 0.0

        return control