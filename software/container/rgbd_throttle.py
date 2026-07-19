import rclpy
from rclpy.node import Node
from rtabmap_msgs.msg import RGBDImage

class Throttle(Node):
    def __init__(self):
        super().__init__('rgbd_throttle')
        self.pub = self.create_publisher(RGBDImage, '/rgbd_image_throttled', 10)
        self.sub = self.create_subscription(RGBDImage, '/rgbd_image', self.cb, 10)
        self.last = 0.0
        self.interval = 0.33  # 3fps

    def cb(self, msg):
        now = self.get_clock().now().nanoseconds / 1e9
        if now - self.last >= self.interval:
            self.last = now
            self.pub.publish(msg)

def main():
    rclpy.init()
    rclpy.spin(Throttle())

if __name__ == '__main__':
    main()
