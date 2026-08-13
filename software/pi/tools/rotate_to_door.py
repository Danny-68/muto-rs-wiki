import rclpy, time, math
from rclpy.node import Node
from geometry_msgs.msg import Twist

rclpy.init()
node = Node('rotate_to_door')
pub = node.create_publisher(Twist, 'cmd_vel', 10)
time.sleep(0.5)

msg = Twist()
msg.angular.z = 1.0  # positief = links (vandaag bevestigd)
SPEED = 0.049
TARGET_DEG = 139.2
DURATION_S = math.radians(TARGET_DEG) / SPEED
print(f"Roteren +{TARGET_DEG} graden (links), duur={DURATION_S:.0f}s...")
t0 = time.time()
while time.time() - t0 < DURATION_S:
    pub.publish(msg)
    rclpy.spin_once(node, timeout_sec=0.05)
    time.sleep(0.05)

stop = Twist()
pub.publish(stop)
rclpy.spin_once(node, timeout_sec=0.1)
print("Stop-commando verstuurd.")
node.destroy_node()
rclpy.shutdown()
