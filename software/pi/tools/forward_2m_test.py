#!/usr/bin/env python3
"""Rechtstreekse 2m-vooruit-test via cmd_vel naar phoenix_driver.py, los van
Nav2/AMCL. Leest /odom_fused positie voor/na, en de gebruiker meet de
werkelijke afstand fysiek voor onafhankelijke verificatie."""
import time
import math
import subprocess
import re

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist

import sys
DISTANCE_M = float(sys.argv[1]) if len(sys.argv) > 1 else 1.0
MAX_LINEAR_SPEED_MPS = 0.0594
DURATION_S = DISTANCE_M / MAX_LINEAR_SPEED_MPS
SETTLE_WAIT_S = 27.0  # empirisch bepaalde veilige wachttijd (zie PROBLEMS.md), i.p.v. de eerdere 3s


def get_odom_fused_xy():
    out = subprocess.run(
        ["bash", "-c",
         "source /opt/ros/humble/setup.bash && timeout 4 ros2 topic echo /odom_fused --once 2>/dev/null"],
        capture_output=True, text=True, timeout=10).stdout
    xs = re.findall(r"x:\s*(-?[\d.eE+-]+)", out)
    ys = re.findall(r"y:\s*(-?[\d.eE+-]+)", out)
    return float(xs[0]), float(ys[0])


def main():
    rclpy.init()
    node = Node('forward_2m_test')
    pub = node.create_publisher(Twist, 'cmd_vel', 10)
    time.sleep(0.5)

    x0, y0 = get_odom_fused_xy()
    print(f"VOOR -- odom_fused x={x0:.3f} y={y0:.3f}")
    print(f"[forward_2m] {DISTANCE_M}m vooruit, duur={DURATION_S:.1f}s...")

    msg = Twist()
    msg.linear.x = MAX_LINEAR_SPEED_MPS
    t0 = time.time()
    while time.time() - t0 < DURATION_S:
        pub.publish(msg)
        rclpy.spin_once(node, timeout_sec=0.05)
        time.sleep(0.05)

    stop = Twist()
    pub.publish(stop)
    rclpy.spin_once(node, timeout_sec=0.1)
    print(f"[forward_2m] stop-commando verstuurd, wachten op stopsequentie + settle ({SETTLE_WAIT_S:.0f}s)...")
    time.sleep(SETTLE_WAIT_S)

    x1, y1 = get_odom_fused_xy()
    traveled = math.hypot(x1 - x0, y1 - y0)
    print(f"NA   -- odom_fused x={x1:.3f} y={y1:.3f}")
    print(f"\nAfgelegde afstand volgens odom_fused: {traveled:.3f}m (doel was {DISTANCE_M}m)")
    print("Meet nu de werkelijke afstand fysiek na voor onafhankelijke verificatie.")

    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
