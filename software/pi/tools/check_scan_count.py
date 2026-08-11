#!/usr/bin/env python3
"""Betrouwbare telling van het aantal punten in /scan, direct via rclpy
(geen tekst-parsing van 'ros2 topic echo' output, die grote arrays kan
afkappen bij het weergeven)."""
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import LaserScan

class Check(Node):
    def __init__(self):
        super().__init__('check_scan_count')
        self.got = False
        self.sub = self.create_subscription(LaserScan, '/scan', self.cb, 10)

    def cb(self, msg):
        n = len(msg.ranges)
        valid = sum(1 for r in msg.ranges if r == r and r != float('inf'))
        print(f"len(ranges)={n}  geldig={valid}  angle_min={msg.angle_min:.4f} "
              f"angle_max={msg.angle_max:.4f} angle_increment={msg.angle_increment:.6f}")
        self.got = True

def main():
    rclpy.init()
    node = Check()
    while not node.got and rclpy.ok():
        rclpy.spin_once(node, timeout_sec=1.0)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
