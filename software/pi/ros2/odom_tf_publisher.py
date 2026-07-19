#!/usr/bin/env python3
"""
Dynamische odom TF publisher — publiceert odom -> base_link op /tf
met 50Hz zodat slam_toolbox hem altijd kan vinden.
"""
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import TransformStamped
from tf2_ros import TransformBroadcaster

class OdomTFPublisher(Node):
    def __init__(self):
        super().__init__('odom_tf_publisher')
        self.broadcaster = TransformBroadcaster(self)
        # 50Hz timer
        self.timer = self.create_timer(0.02, self.publish_transform)
        self.get_logger().info('odom -> base_link TF publisher gestart (50Hz)')

    def publish_transform(self):
        t = TransformStamped()
        t.header.stamp = self.get_clock().now().to_msg()
        t.header.frame_id = 'odom'
        t.child_frame_id = 'base_link'
        t.transform.translation.x = 0.0
        t.transform.translation.y = 0.0
        t.transform.translation.z = 0.0
        t.transform.rotation.x = 0.0
        t.transform.rotation.y = 0.0
        t.transform.rotation.z = 0.0
        t.transform.rotation.w = 1.0
        self.broadcaster.sendTransform(t)

def main():
    rclpy.init()
    node = OdomTFPublisher()
    rclpy.spin(node)

if __name__ == '__main__':
    main()
