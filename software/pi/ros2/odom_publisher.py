#!/usr/bin/env python3
"""
Gecombineerde odom + laser TF publisher voor SLAM.
Publiceert:
  - nav_msgs/Odometry op /odom (50Hz)
  - TF odom -> base_link (50Hz)
  - TF base_link -> laser (50Hz)
"""
import rclpy
from rclpy.node import Node
from nav_msgs.msg import Odometry
from geometry_msgs.msg import TransformStamped
from tf2_ros import TransformBroadcaster, StaticTransformBroadcaster

class OdomPublisher(Node):
    def __init__(self):
        super().__init__('odom_publisher')
        self.odom_pub = self.create_publisher(Odometry, '/odom', 10)
        self.tf_broadcaster = TransformBroadcaster(self)
        self.timer = self.create_timer(0.02, self.publish)
        self.get_logger().info('Odom+laser TF publisher gestart')

    def publish(self):
        now = self.get_clock().now().to_msg()

        # TF 1: odom -> base_link
        t1 = TransformStamped()
        t1.header.stamp = now
        t1.header.frame_id = 'odom'
        t1.child_frame_id = 'base_link'
        t1.transform.translation.x = 0.0
        t1.transform.translation.y = 0.0
        t1.transform.translation.z = 0.0
        t1.transform.rotation.w = 1.0
        self.tf_broadcaster.sendTransform(t1)

        # TF 2: base_link -> laser (LiDAR op 2cm hoogte)
        t2 = TransformStamped()
        t2.header.stamp = now
        t2.header.frame_id = 'base_link'
        t2.child_frame_id = 'laser'
        t2.transform.translation.x = 0.0
        t2.transform.translation.y = 0.0
        t2.transform.translation.z = 0.02
        t2.transform.rotation.w = 1.0
        self.tf_broadcaster.sendTransform(t2)

        # nav_msgs/Odometry
        odom = Odometry()
        odom.header.stamp = now
        odom.header.frame_id = 'odom'
        odom.child_frame_id = 'base_link'
        odom.pose.pose.orientation.w = 1.0
        self.odom_pub.publish(odom)

def main():
    rclpy.init()
    node = OdomPublisher()
    rclpy.spin(node)

if __name__ == '__main__':
    main()
