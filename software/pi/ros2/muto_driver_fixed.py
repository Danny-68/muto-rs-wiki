"""
muto_driver_fixed.py — v4
Directe STM32 serial commando's + IMU publisher
"""
import sys, math, serial, time, threading
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from sensor_msgs.msg import Imu

SERIAL_PORT = '/dev/myserial'
BAUD = 115200
IMU_READ_CMD = bytes([0x55, 0x00, 0x09, 0x02, 0x60, 0x07, 0x8D, 0x00, 0xAA])
IMU_RESPONSE_LEN = 15

def make_cmd(addr, data=0x00):
    wr = 0x01
    length = 0x09
    body = [wr, addr, data]
    chk = (0xFF - ((length + sum(body)) & 0xFF)) & 0xFF
    return bytes([0x55, 0x00, length] + body + [chk, 0x00, 0xAA])

def raw_to_signed(raw):
    if raw > 32767:
        raw -= 65536
    return raw

def deg_to_rad(deg):
    return deg * math.pi / 180.0

class MutoDriver(Node):
    def __init__(self):
        super().__init__('muto_driver_fixed')
        self._lock = threading.Lock()
        self._ser = serial.Serial(SERIAL_PORT, BAUD, timeout=0.1)
        self.sub = self.create_subscription(Twist, 'cmd_vel', self.cb, 10)
        self.imu_pub = self.create_publisher(Imu, '/imu', 10)
        self.last_cmd = self.get_clock().now()
        self.moving = False
        self.create_timer(0.3, self.timeout_check)
        self.create_timer(0.1, self.read_imu)
        self.get_logger().info('Muto driver v4 gestart (STM32 + IMU publisher)')

    def send(self, addr, data=0x00):
        with self._lock:
            self._ser.write(make_cmd(addr, data))

    def read_imu(self):
        try:
            with self._lock:
                self._ser.reset_input_buffer()
                self._ser.write(IMU_READ_CMD)
                time.sleep(0.02)
                response = self._ser.read(IMU_RESPONSE_LEN)
            if len(response) != IMU_RESPONSE_LEN:
                return
            if response[0] != 0x55 or response[3] != 0x12 or response[4] != 0x60:
                return
            roll_raw  = raw_to_signed((response[5] << 8) | response[6])
            pitch_raw = raw_to_signed((response[7] << 8) | response[8])
            yaw_raw   = raw_to_signed((response[9] << 8) | response[10])
            roll_rad  = deg_to_rad(roll_raw  / 100.0)
            pitch_rad = deg_to_rad(pitch_raw / 100.0)
            yaw_rad   = deg_to_rad(yaw_raw   / 100.0)
            cy = math.cos(yaw_rad * 0.5)
            sy = math.sin(yaw_rad * 0.5)
            cp = math.cos(pitch_rad * 0.5)
            sp = math.sin(pitch_rad * 0.5)
            cr = math.cos(roll_rad * 0.5)
            sr = math.sin(roll_rad * 0.5)
            msg = Imu()
            msg.header.stamp = self.get_clock().now().to_msg()
            msg.header.frame_id = 'imu_link'
            msg.orientation.w = cr * cp * cy + sr * sp * sy
            msg.orientation.x = sr * cp * cy - cr * sp * sy
            msg.orientation.y = cr * sp * cy + sr * cp * sy
            msg.orientation.z = cr * cp * sy - sr * sp * cy
            msg.orientation_covariance[0] = 0.01
            msg.orientation_covariance[4] = 0.01
            msg.orientation_covariance[8] = 0.01
            msg.angular_velocity_covariance[0] = -1
            msg.linear_acceleration_covariance[0] = -1
            self.imu_pub.publish(msg)
        except Exception as e:
            self.get_logger().warn(f'IMU read fout: {e}', throttle_duration_sec=5.0)

    def cb(self, msg):
        self.last_cmd = self.get_clock().now()
        x = msg.linear.x
        y = msg.linear.y
        z = msg.angular.z
        thr = 0.01
        if abs(z) > thr:
            if z > 0:
                self.get_logger().info('Draai links')
                self.send(0x16, 15)
            else:
                self.get_logger().info('Draai rechts')
                self.send(0x17, 15)
            self.moving = True
        elif abs(x) > thr:
            if x > 0:
                self.get_logger().info('Vooruit')
                self.send(0x12, 15)
            else:
                self.get_logger().info('Achteruit')
                self.send(0x13, 15)
            self.moving = True
        elif abs(y) > thr:
            if y > 0:
                self.get_logger().info('Links')
                self.send(0x14, 15)
            else:
                self.get_logger().info('Rechts')
                self.send(0x15, 15)
            self.moving = True
        else:
            if self.moving:
                self.get_logger().info('Stop')
                self.send(0x11, 0x00)
                self.moving = False

    def timeout_check(self):
        elapsed = (self.get_clock().now() - self.last_cmd).nanoseconds / 1e9
        if elapsed > 5.0 and self.moving:
            self.get_logger().info('Timeout stop')
            self.send(0x11, 0x00)
            self.moving = False

def main():
    rclpy.init()
    node = MutoDriver()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, Exception):
        pass
    finally:
        node.send(0x11, 0x00)
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

if __name__ == '__main__':
    main()
