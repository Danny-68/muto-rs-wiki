#!/usr/bin/env python3
"""
Rotatie-kalibratietest voor phoenix_driver.py: stuurt een vaste angular.z
gedurende een vaste tijd, meet de daadwerkelijke yaw-verandering via /imu
(extern, ICM20948), om MAX_ANGULAR_SPEED_RADPS te kunnen kalibreren.
"""
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from sensor_msgs.msg import Imu
import math
import time
import sys


def quat_to_yaw_deg(q):
    yaw = math.atan2(2.0 * (q.w * q.z + q.x * q.y), 1.0 - 2.0 * (q.y * q.y + q.z * q.z))
    return math.degrees(yaw)


class RotCalib(Node):
    def __init__(self):
        super().__init__('rot_calib_test')
        self.yaw = None
        self.sub = self.create_subscription(Imu, '/imu', self._imu_cb, 10)
        self.pub = self.create_publisher(Twist, 'cmd_vel', 10)

    def _imu_cb(self, msg):
        self.yaw = quat_to_yaw_deg(msg.orientation)


def main():
    angular_z = float(sys.argv[1]) if len(sys.argv) > 1 else 0.45
    duration_s = float(sys.argv[2]) if len(sys.argv) > 2 else 2.0

    rclpy.init()
    node = RotCalib()

    while node.yaw is None and rclpy.ok():
        rclpy.spin_once(node, timeout_sec=0.5)
    yaw_before = node.yaw
    print(f"[YAW] voor: {yaw_before:.2f}")

    msg = Twist()
    msg.angular.z = angular_z
    t0 = time.time()
    while time.time() - t0 < duration_s:
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

    turned = yaw_after - yaw_before
    while turned > 180:
        turned -= 360
    while turned < -180:
        turned += 360
    print(f"[RESULTAAT] gedraaid: {turned:+.2f} graden, commando angular.z={angular_z} "
          f"gedurende {duration_s}s")

    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
