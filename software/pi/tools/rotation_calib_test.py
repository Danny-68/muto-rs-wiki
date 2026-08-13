#!/usr/bin/env python3
"""
Kalibratie van rotatiesnelheid + teken via de externe IMU (grondwaarheid).
VEILIGE versie (11 aug 2026, na een bijna-runaway door adaptieve duur-
berekening op een onzekere snelheidsschatting): elk segment heeft een
VASTE, korte, vooraf bepaalde duur -- nooit afgeleid van een eerdere
meting -- zodat een enkel segment nooit in de buurt van de 180 graden
wrap-grens van de yaw-uitlezing kan komen, ongeacht de werkelijke snelheid.

Gebruik: python3 rotation_calib_test.py <sign>
  sign = -1  -> rechtsom (aanname na vandaag se bevinding: + is linksom)
  sign = +1  -> linksom
"""
import sys
import time
import math

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from sensor_msgs.msg import Imu

# Vaste, veilige duren -- ruim onder wat zelfs bij een hoge onbekende
# snelheid (worst-case aanname: tot 0.5 rad/s) tot >150 graden zou leiden.
# Bij 0.5 rad/s geeft 5s -> 143 graden, dus 5s is de veiligste bovengrens
# voor de EERSTE, nog volledig onbekende meting.
FIXED_DURATIONS_S = [5.0, 5.0, 8.0, 8.0, 8.0]
SETTLE_WAIT_S = 27.0


def quat_to_yaw_deg(q):
    return math.degrees(math.atan2(2.0 * (q.w * q.z + q.x * q.y), 1.0 - 2.0 * (q.y * q.y + q.z * q.z)))


def wrap(d):
    while d > 180: d -= 360
    while d < -180: d += 360
    return d


class Calib(Node):
    def __init__(self):
        super().__init__('rotation_calib_test')
        self.imu_yaw = None
        self.create_subscription(Imu, '/imu', self._cb, 10)
        self.pub = self.create_publisher(Twist, 'cmd_vel', 10)

    def _cb(self, msg):
        self.imu_yaw = quat_to_yaw_deg(msg.orientation)


def main():
    sign = float(sys.argv[1]) if len(sys.argv) > 1 else -1.0
    richting = "rechtsom" if sign < 0 else "linksom"

    rclpy.init()
    node = Calib()
    while node.imu_yaw is None and rclpy.ok():
        rclpy.spin_once(node, timeout_sec=0.5)

    print(f"\n=== Kalibratie {richting} (sign={sign:+.0f}), VASTE duren ===")
    print(f"{'duur(s)':>8} | {'segment':>8} | {'cumulatief':>10} | {'snelheid(rad/s)':>16}")

    cumulative_deg = 0.0
    for duration_s in FIXED_DURATIONS_S:
        yaw_before = node.imu_yaw
        msg = Twist()
        msg.angular.z = sign * 1.0
        t0 = time.time()
        while time.time() - t0 < duration_s:
            node.pub.publish(msg)
            rclpy.spin_once(node, timeout_sec=0.05)
            time.sleep(0.05)
        stop = Twist()
        node.pub.publish(stop)
        rclpy.spin_once(node, timeout_sec=0.1)

        time.sleep(3.0)
        for _ in range(int(SETTLE_WAIT_S)):
            rclpy.spin_once(node, timeout_sec=1.0)

        yaw_after = node.imu_yaw
        segment_deg = wrap(yaw_after - yaw_before)
        cumulative_deg += segment_deg
        speed = abs(math.radians(segment_deg)) / duration_s

        print(f"{duration_s:8.1f} | {segment_deg:8.1f} | {cumulative_deg:10.1f} | {speed:16.4f}")

    print(f"\nKlaar. Gebruik de losse snelheidswaarden per rij (niet het gemiddelde\n"
          f"blind aannemen) om te zien of de snelheid constant is over verschillende duren.")
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
