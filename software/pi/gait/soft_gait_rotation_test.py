#!/usr/bin/env python3
"""
Pad B-experiment: test of een 'zachtere' tripod-variant (lagere lift,
langzamere cyclus) de rf2o/EKF-yaw-fout verkleint t.o.v. de standaard
tripod-gait. Draait de gait rechtstreeks (geen phoenix_driver.py/ROS-node,
zelfde /dev/myserial-exclusiviteit als altijd) en leest /imu + /odom_fused
via rclpy voor/na, zelfde methodologie als isolate_odomfused_vs_imu.py.
GEEN wijziging aan phoenix_gait.py's standaard TRIPOD-parameters -- dit is
een losse testvariant, alleen actief tijdens dit script.
"""
import sys
import time
import math
import subprocess
import re

sys.path.insert(0, '/root')
from phoenix_gait import PhoenixGait, HardwareInterface, GaitParams, TRIPOD

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Imu

# -- 'zachte' tripod-variant: helft van de lift, 50% langzamere cyclus -----
SOFT_TRIPOD = GaitParams("soft_tripod",
                          TRIPOD.cycle_time_s * 1.5,   # 1.6 -> 2.4s
                          TRIPOD.duty_factor,
                          TRIPOD.leg_offsets,
                          TRIPOD.lift_height * 0.5,    # 40 -> 20mm
                          TRIPOD.step_length)

HZ = 50
DT = 1.0 / HZ
DURATION_S = 10.0
ROTATE = 1.0  # zelfde als isolate_odomfused_vs_imu.py (max rotatiesnelheid)


def quat_to_yaw_deg(q):
    return math.degrees(math.atan2(2.0 * (q.w * q.z + q.x * q.y), 1.0 - 2.0 * (q.y * q.y + q.z * q.z)))


def get_odom_fused_yaw():
    out = subprocess.run(
        ["bash", "-c",
         "source /opt/ros/humble/setup.bash && timeout 4 ros2 topic echo /odom_fused --once 2>/dev/null"],
        capture_output=True, text=True, timeout=10).stdout
    zs = re.findall(r"z:\s*(-?[\d.eE+-]+)", out)
    ws = re.findall(r"w:\s*(-?[\d.eE+-]+)", out)
    qz = float(zs[1])
    qw = float(ws[0])
    return math.degrees(2 * math.atan2(qz, qw))


class ImuReader(Node):
    def __init__(self):
        super().__init__('soft_gait_test_imu_reader')
        self.imu_yaw = None
        self.create_subscription(Imu, '/imu', self._cb, 10)

    def _cb(self, msg):
        self.imu_yaw = quat_to_yaw_deg(msg.orientation)


def wrap(d):
    while d > 180: d -= 360
    while d < -180: d += 360
    return d


def main():
    rclpy.init()
    node = ImuReader()
    while node.imu_yaw is None and rclpy.ok():
        rclpy.spin_once(node, timeout_sec=0.5)

    imu_before = node.imu_yaw
    odom_before = get_odom_fused_yaw()
    print(f"VOOR  -- imu_yaw={imu_before:.2f}  odom_fused_yaw={odom_before:.2f}")
    print(f"[soft_gait] cycle_time={SOFT_TRIPOD.cycle_time_s:.1f}s (vs {TRIPOD.cycle_time_s:.1f}s standaard), "
          f"lift={SOFT_TRIPOD.lift_height:.0f}mm (vs {TRIPOD.lift_height:.0f}mm standaard)")

    iface = HardwareInterface(port='/dev/myserial', exec_time_ms=18)
    engine = PhoenixGait()

    print(f"[soft_gait] rotatie-burst {DURATION_S}s...")
    global_phase = 0.0
    t0 = time.time()
    while time.time() - t0 < DURATION_S:
        positions, _ = engine.foot_targets(
            global_phase, SOFT_TRIPOD,
            travel_x=0.0, travel_z=0.0, rotate=ROTATE,
            target_speed=1.0, body_sway=True, body_dip=True)
        iface.send(positions)
        rclpy.spin_once(node, timeout_sec=0.0)
        time.sleep(DT)
        global_phase = (global_phase + DT / SOFT_TRIPOD.cycle_time_s) % 1.0

    print("[soft_gait] stop, terug naar neutraal...")
    iface.destroy()

    print("Wachten op settle...")
    time.sleep(3.0)
    for _ in range(10):
        rclpy.spin_once(node, timeout_sec=0.3)

    imu_after = node.imu_yaw
    odom_after = get_odom_fused_yaw()
    print(f"NA    -- imu_yaw={imu_after:.2f}  odom_fused_yaw={odom_after:.2f}")

    imu_delta = wrap(imu_after - imu_before)
    odom_delta = wrap(odom_after - odom_before)
    print(f"\nIMU (grondwaarheid)   gedraaid: {imu_delta:+.1f} graden")
    print(f"EKF /odom_fused gerapporteerd gedraaid: {odom_delta:+.1f} graden")
    if abs(imu_delta) > 0.5:
        print(f"Ratio odom_fused/IMU: {odom_delta / imu_delta:.2f}x")

    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
