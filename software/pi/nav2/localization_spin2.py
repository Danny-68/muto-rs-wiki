import rclpy, time, math
from rclpy.node import Node
from geometry_msgs.msg import Twist

rclpy.init()
node = Node('localization_spin2')
pub = node.create_publisher(Twist, 'cmd_vel', 10)
time.sleep(0.5)

msg = Twist()
msg.angular.z = 1.0
SPEED = 0.049  # nieuw gekalibreerd, na IMU-verplaatsing
DURATION_S = 2 * (2 * math.pi / SPEED)  # ~2 volle cirkels
print(f"Roteren voor {DURATION_S:.0f}s (~2 cirkels bij {SPEED} rad/s)...")
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
