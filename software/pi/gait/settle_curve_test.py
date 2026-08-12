#!/usr/bin/env python3
"""
Pad-4-onderzoek: is de resterende ~18% afwijking tussen /imu en /odom_fused
een permanente filterfout, of een convergentie-vertraging? Bemonstert
/odom_fused meerdere keren na de stop (i.p.v. eenmalig na 3s) om de
convergentiecurve te zien. /imu blijft de grondwaarheid (rf2o's yaw staat
uit, dus /imu is de enige yaw-bron voor de EKF/UKF).
"""
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from sensor_msgs.msg import Imu
import math
import time
import subprocess
import re


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


class Isolate(Node):
    def __init__(self):
        super().__init__('settle_curve_test')
        self.imu_yaw = None
        self.create_subscription(Imu, '/imu', self._imu_cb, 10)
        self.pub = self.create_publisher(Twist, 'cmd_vel', 10)

    def _imu_cb(self, msg):
        self.imu_yaw = quat_to_yaw_deg(msg.orientation)


def wrap(d):
    while d > 180: d -= 360
    while d < -180: d += 360
    return d


def main():
    rclpy.init()
    node = Isolate()

    while node.imu_yaw is None and rclpy.ok():
        rclpy.spin_once(node, timeout_sec=0.5)

    imu_before = node.imu_yaw
    odom_before = get_odom_fused_yaw()
    print(f"VOOR  -- imu_yaw={imu_before:.2f}  odom_fused_yaw={odom_before:.2f}")

    msg = Twist()
    msg.angular.z = 1.0
    t0 = time.time()
    while time.time() - t0 < 10.0:
        node.pub.publish(msg)
        rclpy.spin_once(node, timeout_sec=0.05)
        time.sleep(0.05)

    stop = Twist()
    node.pub.publish(stop)
    rclpy.spin_once(node, timeout_sec=0.1)

    print("Wachten op stop-sequentie (phoenix_driver's eigen stop, ~2s)...")
    time.sleep(2.5)

    print("\nConvergentiecurve na stop:")
    print(f"{'t (s)':>6} | {'imu_yaw':>8} | {'odom_fused':>10} | {'imu_delta':>9} | {'odom_delta':>10} | {'ratio':>6}")
    t_stop = time.time()
    for _ in range(15):
        rclpy.spin_once(node, timeout_sec=0.2)
        imu_now = node.imu_yaw
        try:
            odom_now = get_odom_fused_yaw()
        except (IndexError, ValueError):
            print(f"{time.time()-t_stop:6.1f} | (leesfout, overslaan)")
            time.sleep(2.0)
            continue
        imu_delta = wrap(imu_now - imu_before)
        odom_delta = wrap(odom_now - odom_before)
        ratio = odom_delta / imu_delta if abs(imu_delta) > 0.5 else float('nan')
        print(f"{time.time()-t_stop:6.1f} | {imu_now:8.2f} | {odom_now:10.2f} | {imu_delta:+9.2f} | {odom_delta:+10.2f} | {ratio:6.2f}")
        time.sleep(2.0)

    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
