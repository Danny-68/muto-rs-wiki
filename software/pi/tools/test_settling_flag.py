import rclpy, time
from rclpy.node import Node
from geometry_msgs.msg import Twist
from std_msgs.msg import Bool

class Test(Node):
    def __init__(self):
        super().__init__('test_settling_flag')
        self.settling = None
        self.create_subscription(Bool, 'pose_settling', self.cb, 10)
        self.pub = self.create_publisher(Twist, 'cmd_vel', 10)
    def cb(self, msg):
        self.settling = msg.data

rclpy.init()
n = Test()
for _ in range(5):
    rclpy.spin_once(n, timeout_sec=0.3)
print(f"VOOR beweging: settling={n.settling}")

msg = Twist()
msg.angular.z = 1.0
t0 = time.time()
while time.time() - t0 < 3.0:
    n.pub.publish(msg)
    rclpy.spin_once(n, timeout_sec=0.05)
    time.sleep(0.05)
stop = Twist()
n.pub.publish(stop)
rclpy.spin_once(n, timeout_sec=0.1)

t_cmd_stop = time.time()
print("Monitoren van pose_settling na stop-commando...")
for _ in range(60):
    rclpy.spin_once(n, timeout_sec=0.5)
    print(f"t={time.time()-t_cmd_stop:5.1f}s  settling={n.settling}")
    if n.settling is False and time.time() - t_cmd_stop > 5:
        break
    time.sleep(0.5)

n.destroy_node()
rclpy.shutdown()
