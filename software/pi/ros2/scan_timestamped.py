#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import LaserScan
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy

class ScanTimestamped(Node):
    def __init__(self):
        super().__init__("scan_timestamped")
        qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=10
        )
        self.pub = self.create_publisher(LaserScan, "/scan_fixed", qos)
        self.sub = self.create_subscription(LaserScan, "/scan", self.cb, qos)
        self.get_logger().info("Scan fix: /scan -> /scan_fixed (BEST_EFFORT)")

    def cb(self, msg):
        msg.header.stamp = self.get_clock().now().to_msg()
        self.pub.publish(msg)

def main():
    rclpy.init()
    rclpy.spin(ScanTimestamped())

if __name__ == "__main__":
    main()
