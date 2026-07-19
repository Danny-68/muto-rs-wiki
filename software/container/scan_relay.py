#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import LaserScan
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy

class ScanRelay(Node):
    def __init__(self):
        super().__init__('scan_relay')
        sub_qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=10
        )
        pub_qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
            depth=10
        )
        self.pub = self.create_publisher(LaserScan, '/scan_reliable', pub_qos)
        self.sub = self.create_subscription(LaserScan, '/scan', self.cb, sub_qos)
        self.get_logger().info('scan_relay: /scan (BEST_EFFORT) -> /scan_reliable (RELIABLE)')

    def cb(self, msg):
        self.pub.publish(msg)

def main():
    rclpy.init()
    node = ScanRelay()
    rclpy.spin(node)

if __name__ == '__main__':
    main()
