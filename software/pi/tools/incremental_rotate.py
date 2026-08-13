import rclpy, time, math
from rclpy.node import Node
from geometry_msgs.msg import Twist
from sensor_msgs.msg import Imu

def quat_to_yaw_deg(q):
    return math.degrees(math.atan2(2.0*(q.w*q.z+q.x*q.y), 1.0-2.0*(q.y*q.y+q.z*q.z)))

def wrap(d):
    while d > 180: d -= 360
    while d < -180: d += 360
    return d

class Rot(Node):
    def __init__(self):
        super().__init__('incremental_rotate')
        self.imu_yaw = None
        self.create_subscription(Imu, '/imu', self._cb, 10)
        self.pub = self.create_publisher(Twist, 'cmd_vel', 10)
    def _cb(self, msg):
        self.imu_yaw = quat_to_yaw_deg(msg.orientation)

rclpy.init()
node = Rot()
while node.imu_yaw is None and rclpy.ok():
    rclpy.spin_once(node, timeout_sec=0.5)

SIGN = -1.0  # rechtsom
SPEED = 0.049
SEGMENT_DEG = 30.0
N_SEGMENTS = 3
DURATION_S = math.radians(SEGMENT_DEG) / SPEED

yaw_start = node.imu_yaw
cumulative = 0.0
for i in range(N_SEGMENTS):
    yaw_before = node.imu_yaw
    msg = Twist()
    msg.angular.z = SIGN * 1.0
    t0 = time.time()
    while time.time() - t0 < DURATION_S:
        node.pub.publish(msg)
        rclpy.spin_once(node, timeout_sec=0.05)
        time.sleep(0.05)
    stop = Twist()
    node.pub.publish(stop)
    rclpy.spin_once(node, timeout_sec=0.1)
    time.sleep(3.0)
    for _ in range(27):
        rclpy.spin_once(node, timeout_sec=1.0)
    yaw_after = node.imu_yaw
    seg = wrap(yaw_after - yaw_before)
    cumulative += seg
    print(f"stap {i+1}/{N_SEGMENTS}: duur={DURATION_S:.1f}s  segment={seg:+.1f} graden  cumulatief={cumulative:+.1f} graden")

print(f"\nTotaal gedraaid: {wrap(node.imu_yaw - yaw_start):+.1f} graden")
node.destroy_node()
rclpy.shutdown()
