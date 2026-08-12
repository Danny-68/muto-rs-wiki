#!/usr/bin/env python3
import sys
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import PoseWithCovarianceStamped

x = float(sys.argv[1]) if len(sys.argv) > 1 else 0.0
y = float(sys.argv[2]) if len(sys.argv) > 2 else 0.0
yaw_deg = float(sys.argv[3]) if len(sys.argv) > 3 else 0.0

import math
yaw = math.radians(yaw_deg)

rclpy.init()
node = Node('set_initial_pose')
pub = node.create_publisher(PoseWithCovarianceStamped, '/initialpose', 10)

import time
time.sleep(1.0)  # laat de publisher discoveren

msg = PoseWithCovarianceStamped()
msg.header.frame_id = 'map'
msg.header.stamp = node.get_clock().now().to_msg()
msg.pose.pose.position.x = x
msg.pose.pose.position.y = y
msg.pose.pose.orientation.z = math.sin(yaw / 2.0)
msg.pose.pose.orientation.w = math.cos(yaw / 2.0)
cov = [0.0] * 36
cov[0] = 0.25   # x
cov[7] = 0.25   # y
cov[35] = 0.06  # yaw
msg.pose.covariance = cov

pub.publish(msg)
time.sleep(0.5)
pub.publish(msg)  # nogmaals voor de zekerheid
print(f"initialpose gepubliceerd: x={x} y={y} yaw={yaw_deg} graden")
node.destroy_node()
rclpy.shutdown()
