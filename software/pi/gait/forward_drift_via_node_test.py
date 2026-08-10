#!/usr/bin/env python3
"""
Yaw-drift test voor phoenix_driver.py via cmd_vel/ROS2 (i.p.v. directe
phoenix_gait-aanroepen zoals phoenix_yaw_drift_test.py deed). Zelfde
afstandsmethodologie: volle snelheid gedurende de tijd die overeenkomt met
5.3 gait-cycli (~50cm bij de gemeten ~9.5cm/cyclus), om te vergelijken met
de bestaande baseline (+2.80 graden vooruit, -1.36 graden achteruit).
"""
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from sensor_msgs.msg import Imu
import math
import time
import sys

MAX_LINEAR_SPEED_MPS = 0.0594
CYCLE_TIME_S = 1.6
TARGET_CYCLES = 5.3
DURATION_S = TARGET_CYCLES * CYCLE_TIME_S  # ~8.48s


def quat_to_yaw_deg(q):
    yaw = math.atan2(2.0 * (q.w * q.z + q.x * q.y), 1.0 - 2.0 * (q.y * q.y + q.z * q.z))
    return math.degrees(yaw)


class DriftTest(Node):
    def __init__(self):
        super().__init__('forward_drift_via_node_test')
        self.yaw = None
        self.sub = self.create_subscription(Imu, '/imu', self._imu_cb, 10)
        self.pub = self.create_publisher(Twist, 'cmd_vel', 10)

    def _imu_cb(self, msg):
        self.yaw = quat_to_yaw_deg(msg.orientation)


def main():
    direction = sys.argv[1] if len(sys.argv) > 1 else 'forward'
    sign = 1.0 if direction == 'forward' else -1.0

    rclpy.init()
    node = DriftTest()

    while node.yaw is None and rclpy.ok():
        rclpy.spin_once(node, timeout_sec=0.5)
    yaw_before = node.yaw
    print(f"[YAW] voor: {yaw_before:.2f}")
    print(f"[INFO] {direction}, {DURATION_S:.2f}s @ volle snelheid ({MAX_LINEAR_SPEED_MPS} m/s)")

    msg = Twist()
    msg.linear.x = sign * MAX_LINEAR_SPEED_MPS
    t0 = time.time()
    while time.time() - t0 < DURATION_S:
        node.pub.publish(msg)
        rclpy.spin_once(node, timeout_sec=0.05)
        time.sleep(0.05)

    stop = Twist()
    node.pub.publish(stop)
    rclpy.spin_once(node, timeout_sec=0.1)

    print("[INFO] wachten op vloeiende stop-sequentie...")
    time.sleep(2.5)
    rclpy.spin_once(node, timeout_sec=0.5)
    yaw_after = node.yaw
    print(f"[YAW] na: {yaw_after:.2f}")

    drift = yaw_after - yaw_before
    while drift > 180:
        drift -= 360
    while drift < -180:
        drift += 360
    print(f"[RESULTAAT] drift: {drift:+.2f} graden ({direction}, {TARGET_CYCLES} cycli)")
    print(f"[VERGELIJKING] baseline (directe phoenix_gait-aanroep, 10 aug): "
          f"+2.80 graden vooruit / -1.36 graden achteruit")

    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
