"""
imu_publisher.py - Pimoroni ICM20948 ROS2 driver
Bus: 4, Adres: 0x68
Publiceert: /imu (sensor_msgs/Imu) op 100Hz
"""
import math
import smbus2
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Imu
from icm20948 import ICM20948

class ImuPublisher(Node):
    def __init__(self):
        super().__init__('icm20948_publisher')
        self.pub = self.create_publisher(Imu, '/imu', 10)
        bus = smbus2.SMBus(4)
        self.imu = ICM20948(i2c_bus=bus)
        self.create_timer(0.05, self.publish_imu)
        self.get_logger().info('ICM20948 IMU publisher gestart op bus 4 adres 0x68')

    def publish_imu(self):
        try:
            ax, ay, az, gx, gy, gz = self.imu.read_accelerometer_gyro_data()

            msg = Imu()
            msg.header.stamp = self.get_clock().now().to_msg()
            msg.header.frame_id = 'imu_link'

            msg.angular_velocity.x = math.radians(gx)
            msg.angular_velocity.y = math.radians(gy)
            msg.angular_velocity.z = math.radians(gz)
            msg.angular_velocity_covariance[0] = 0.0001
            msg.angular_velocity_covariance[4] = 0.0001
            msg.angular_velocity_covariance[8] = 0.0001

            msg.linear_acceleration.x = ax * 9.81
            msg.linear_acceleration.y = ay * 9.81
            msg.linear_acceleration.z = az * 9.81
            msg.linear_acceleration_covariance[0] = 0.001
            msg.linear_acceleration_covariance[4] = 0.001
            msg.linear_acceleration_covariance[8] = 0.001

            msg.orientation_covariance[0] = -1

            self.pub.publish(msg)

        except Exception as e:
            self.get_logger().warn(f'IMU leesfout: {e}', throttle_duration_sec=5.0)

def main():
    rclpy.init()
    node = ImuPublisher()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, Exception):
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

if __name__ == '__main__':
    main()
