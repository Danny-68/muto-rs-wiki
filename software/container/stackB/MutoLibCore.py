import serial
import struct
import time
import threading

try:
    from .hexapod import Hexapod
except ImportError:
    from hexapod import Hexapod


__version__ = '1.2.3'
__last_modified__ = '2025/10/31'

"""
ORDER 用来存放命令地址和对应数据
ORDER is used to store the command address and corresponding data
"""
ORDER = {
    "BATTERY": [0x01, 100],#电压采集电量
    "FIRMWARE_VERSION": [0x07,0],#固件版本信息
    "RESET": [0x06, 0],#站立复位
    "SQUATS": [0x10, 0], #下蹲
    "STAY_PUT": [0x11, 0], #脚步衔接落地
    "FORWARD": [0x12, 0], #前进
    "BACKWARD": [0x13, 0], #后退
    "SHIFT_LEFT": [0x14, 0], #左移
    "SHIFT_RIGHT": [0x15, 0], #右移
    "TURN_LEFT": [0x16, 0], #原地左转
    "TURN_RIGHT": [0x17, 0], #原地右转
    "BUZZER": [0x18, 0], #蜂鸣器
    "HEIGHT": [0x19, 0], #身高调节
    "LOW": [0x20, 0], #低
    "MEDIUM": [0x21, 0], #中
    "HIGH": [0x22, 0], #高
    "RUN_TIME": [0x23, 0], #运行时间(速度)
    "HEAD": [0x24, 0], #上下抬头
    "PWM_SERVO": [0x25, 0, 0],  #二自由度云台
    "TORQUE_ON":[0x26,0], #关节舵机扭矩打开
    "TORQUE_OFF":[0x27,0], #关节舵机扭矩关闭
    "CALIBRATE":[0x28, 0, 0, 0], #关节校准角度偏差
    "ACTION": [0x3E, 0],#表演模式 
    "MOTOR": [0x40, 0, 0, 0, 0],#单个舵机ID角度控制
    "LEG": [0x41, 0, 0, 0, 0, 0, 0],#单腿上三个舵机角度控制
    "MOTOR_ANGLE": [0x50, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],#读取蜘蛛机器人舵机角度
    "ATTITUDE_ANGLE": [0x60, 0], #读取俯仰角度\横滚角度\偏航角度
    "IMU_RAW": [0x61, 0], #读取IMU原始数据
    "SERVO_OFFSET": [0x70, 0], #读取校准偏差角度值
}


class Muto():
    """
    在实例化Muto时需要指定上位机与六足机器人的串口通讯接口
    When instantiating Muto, you need to specify the serial 
    communication interface between the host computer and the Muto robot
    """

    def __init__(self, port="/dev/myserial", debug=False, speed_mapping=None):
        self.ser = serial.Serial(port, 115200, timeout=0.05)
        self.rx_FLAG = 0
        self.rx_COUNT = 0
        self.rx_ADDR = 0
        self.rx_LEN = 0
        self.rx_data = bytearray(30)
        self.__delay = 0.001
        self.__debug = debug

        self.__HEAD = 0x55
        self.__DEVICE_ID = 0x00
        self.__WRITE_CMD = 1
        self.__READ_CMD = 2
        self.__read_CMD = 2

        self.__hexapod = Hexapod(self.ser)

        self.__val_x = 0
        self.__val_y = 0
        self.__val_z = 0
        self.__move_state = 0
        
        # 速度映射表：档位(-30~30) -> 真实速度(m/s)
        # Speed mapping table: level(-30~30) -> real speed(m/s)
        if speed_mapping is None:
            # 默认速度映射表，可以通过初始化参数自定义
            # Default speed mapping, can be customized via initialization parameters
            self.__speed_mapping = {i: i * 0.01 for i in range(-30, 31)}  # 默认每档位0.01m/s
        else:
            self.__speed_mapping = speed_mapping


    def __send(self, key, index=1, len=1):
        mode = self.__WRITE_CMD
        order = ORDER[key][0] + index - 1
        value = []
        value_sum = 0
        for i in range(0, len):
            value.append(ORDER[key][index + i])
            value_sum = value_sum + ORDER[key][index + i]
        sum_data = ((len + 0x08) + mode + order + value_sum) % 256
        sum_data = 255 - sum_data
        tx = [self.__HEAD, self.__DEVICE_ID, (len + 0x08), mode, order]
        tx.extend(value)
        tx.extend([sum_data, 0x00, 0xAA])
        self.ser.write(tx)
        if self.__delay > 0:
            time.sleep(self.__delay)
        if self.__debug:
            print("send:", tx)

    def __read(self, addr, param=1):
        mode = self.__READ_CMD
        sum_data = (0x09 + mode + addr + param) % 256
        sum_data = 255 - sum_data
        tx = [self.__HEAD, self.__DEVICE_ID, 0x09, mode, addr, param, sum_data, 0x00, 0xAA]
        self.ser.flushInput()
        self.ser.flushOutput()
        self.ser.write(tx)
        if self.__debug:
            print("read:", tx)

    def __unpack(self):
        n = self.ser.inWaiting()
        rx_CHECK = 0
        if n:
            #print("OK")
            data = self.ser.read_all()
            if self.__debug:
                print("rx_data:", list(data))
            for num in data:
                if self.rx_FLAG == 0:
                    if num == self.__HEAD:
                        self.rx_FLAG = 1
                    else:
                        self.rx_FLAG = 0

                elif self.rx_FLAG == 1:
                    if num == self.__DEVICE_ID:
                        self.rx_FLAG = 2
                    else:
                        self.rx_FLAG = 0

                elif self.rx_FLAG == 2:
                    self.rx_LEN = num
                    self.rx_FLAG = 3

                elif self.rx_FLAG == 3:
                    self.rx_TYPE = num
                    self.rx_FLAG = 4

                elif self.rx_FLAG == 4:
                    self.rx_ADDR = num
                    self.rx_FLAG = 5

                elif self.rx_FLAG == 5:
                    if self.rx_COUNT == (self.rx_LEN - 9):
                        self.rx_data[self.rx_COUNT] = num
                        self.rx_COUNT = 0
                        self.rx_FLAG = 6
                    elif self.rx_COUNT < self.rx_LEN - 9:
                        self.rx_data[self.rx_COUNT] = num
                        self.rx_COUNT = self.rx_COUNT + 1

                elif self.rx_FLAG == 6:
                    for i in self.rx_data[0:(self.rx_LEN - 8)]:
                        rx_CHECK = rx_CHECK + i
                    rx_CHECK = 255 - (self.rx_LEN + self.rx_TYPE + self.rx_ADDR + rx_CHECK) % 256
                    if num == rx_CHECK:
                        self.rx_FLAG = 7
                    else:
                        self.rx_FLAG = 0
                        self.rx_COUNT = 0
                        self.rx_ADDR = 0
                        self.rx_LEN = 0

                elif self.rx_FLAG == 7:
                    if num == 0x00:
                        self.rx_FLAG = 8
                    else:
                        self.rx_FLAG = 0
                        self.rx_COUNT = 0
                        self.rx_ADDR = 0
                        self.rx_LEN = 0

                elif self.rx_FLAG == 8:
                    if num == 0xAA:
                        self.rx_FLAG = 0
                        self.rx_COUNT = 0
                        return True
                    else:
                        self.rx_FLAG = 0
                        self.rx_COUNT = 0
                        self.rx_ADDR = 0
                        self.rx_LEN = 0
        return False

    def __limit_value(self, value, val_min, val_max):
        if value < val_min:
            return val_min
        if value > val_max:
            return val_max
        return value
    
    def write(self, data):
        """
        写入数据到串口，用于兼容servo.py中的调用
        Write data to serial port, for compatibility with servo.py calls
        """
        return self.ser.write(data)

    def reset(self):
        """
        复位 reset robot
        """
        self.__send("RESET")

    def stop(self):
        """
        停下，脚步衔接落地 stop, put down leg
        """
        self.stay_put()

    def stay_put(self):
        """
        脚步衔接落地 put down leg
        """
        self.__send("STAY_PUT")
    
    def squats(self):
        """
        下蹲 squat
        """
        self.__send("SQUATS")

    def forward(self, step=10):
        """
        前进 forward 
        step=[10, 25]
        """
        step = self.__limit_value(step, 10, 25)
        ORDER["FORWARD"][1] = int(step)
        self.__send("FORWARD")

    def back(self, step=10):
        """
        后退 backward 
        step=[10, 25]
        """
        step = self.__limit_value(step, 10, 25)
        ORDER["BACKWARD"][1] = int(step)
        self.__send("BACKWARD")

    def left(self, step=10):
        """
        向左平移 move left 
        step=[10, 25]
        """
        step = self.__limit_value(step, 10, 25)
        ORDER["SHIFT_LEFT"][1] = int(step)
        self.__send("SHIFT_LEFT")

    def right(self, step=10):
        """
        向右平移 move right
        step=[10, 25]
        """
        step = self.__limit_value(step, 10, 25)
        ORDER["SHIFT_RIGHT"][1] = int(step)
        self.__send("SHIFT_RIGHT")

    def turnleft(self, step=10):
        """
        原地左转 turn left
        step=[10, 25]
        """
        step = self.__limit_value(step, 10, 25)
        ORDER["TURN_LEFT"][1] = int(step)
        self.__send("TURN_LEFT")

    def turnright(self, step=10):
        """
        原地右转 turn right
        step=[10, 25]
        """
        step = self.__limit_value(step, 10, 25)
        ORDER["TURN_RIGHT"][1] = int(step)
        self.__send("TURN_RIGHT")

    def height(self, level):
        '''
        设置机器人的身高 Set the height of the robot
        level=[1, 3], low:1,medium:2,high:3
        '''
        level = self.__limit_value(level, 1, 3)
        ORDER["HEIGHT"][1] = int(level)
        self.__send("HEIGHT")

    def low(self):
        '''
        机体高度：低 : Body height: Low
        '''
        self.__send("LOW")

    def medium(self):
        '''
        机体高度：中 Body height: Medium
        '''
        self.__send("MEDIUM")

    def high(self):
        '''
        机体高度：高 Body height: High
        '''
        self.__send("HIGH")
    

    def buzzer(self, timeout):
        """
        控制机器人蜂鸣器鸣笛, 如果timeout=0, 表示关闭蜂鸣器, timeout=255, 表示蜂鸣器一直响, timeout=1~254表示鸣笛timeout*100ms后自动关闭。
        Control the robot buzzer, If timeout=0, the buzzer is turned off. If timeout=255, the buzzer keeps ringing. 
        If timeout=1~254, the buzzer is turned off automatically after the buzzer buzzes in timeout*100ms
        timeout=[0, 255]
        """
        timeout = self.__limit_value(timeout, 0, 255)
        ORDER["BUZZER"][1] = int(timeout)
        self.__send("BUZZER")

    def speed(self, level):
        """
        控制机器人速度等级, level越大, 速度越快
        Control robot speed level, the smaller the level, the faster the speed
        level=[1, 5]
        """
        level = int(self.__limit_value(level, 1, 5))
        level = 5 - level
        ORDER["RUN_TIME"][1] = int(level)
        self.__send("RUN_TIME")

    def head_move(self, level):
        """
        控制机器人上下抬头
        Control the robot to look up and down
        level=[0, 10]
        """
        level = self.__limit_value(level, 0, 10)
        ORDER["HEAD"][1] = int(level)
        self.__send("HEAD")

    def Gimbal_1_2(self, angle1, angle2):
        """
        控制蜘蛛机器人云台1、2, -1<=angle1<=180, -1<=angle2<=115
        Control Spider Robot Gimbal 1, -1<=angle1<=180, -1<=angle2<=115
        """
        angle1 = self.__limit_value(angle1, -1, 180)
        angle2 = self.__limit_value(angle2, -1, 115)
        ORDER["PWM_SERVO"][1] = int(angle1) & 0xFF
        ORDER["PWM_SERVO"][2] = int(angle2) & 0xFF
        self.__send("PWM_SERVO", len=2)

    def Servo_torque_on(self, servo_id=0):
        """
        控制机器人关节舵机扭矩打开
        Turn on the torque of robot joint servo
        """
        if servo_id < 0 or servo_id > 18:
            return
        if int(servo_id) == 0:
            servo_id = 0xFE
        ORDER["TORQUE_ON"][1] = int(servo_id)
        self.__send("TORQUE_ON")

    def Servo_torque_off(self, servo_id=0):
        """
        控制机器人关节舵机扭矩关闭
        Turn off the torque of robot joint servo
        """
        if servo_id < 0 or servo_id > 18:
            return
        if servo_id == 0:
            servo_id = 0xFE
        ORDER["TORQUE_OFF"][1] = int(servo_id)
        self.__send("TORQUE_OFF")

    def load_leg(self, leg):
        '''
        加载腿部舵机
        Load leg servo
        '''
        if leg < 1 or leg > 6:
            return
        id = int(leg-1)*3+1
        for i in range (3):
            self.Servo_torque_on(id + i)
            time.sleep(.001)

    def unload_leg(self, leg):
        '''
        卸载腿部舵机
        Unload leg servo
        '''
        if leg < 1 or leg > 6:
            return
        id = int(leg-1)*3+1
        for i in range (3):
            self.Servo_torque_off(id + i)
            time.sleep(.001)


    def Calibrate_position(self, servo_id, value):
        """
        控制机器人校准位置, 可调整范围约±45°
        Control the robot calibration position. Adjustable range about ±45°
        servo_id=[1, 18]
        value=[-511, 511]
        """
        if servo_id < 1 or servo_id > 18:
            return
        if value < -511 or value > 511:
            return
        value_s = bytearray(struct.pack('h', int(value)))
        ORDER["CALIBRATE"][1] = int(servo_id)
        ORDER["CALIBRATE"][2] = value_s[1]
        ORDER["CALIBRATE"][3] = value_s[0]
        self.__send("CALIBRATE", len=3)


    def action(self, action_id):
        """
        机器人运行预设的动作, action_id(0-8)分别对应: 0复位、1伸懒腰、2打个招呼、3害怕退缩、4热身起蹲、5原地转圈、6挥手说不、7寄居蜷起、8大步向前
        The robot runs a preset action, action_id(0-8) corresponds to: 
        0-reset, 1-stretch, 2-say hello, 3-fear of retreating, 4-warm up, 5-circle in place, 6-say no, 7-curl up, 8-stride
        action_id=[0, 8]
        """
        if action_id < 0 or action_id > 8:
            print("ERROR!Illegal Action ID!")
            return
        ORDER["ACTION"][1] = int(action_id)
        self.__send("ACTION")

    def motor(self, servo_id, angle, runtime=100):
        """
        控制机器人单个舵机转动, 角度控制范围：-90~90
        Control the rotation of a servo, Angle control range: -90~90
        servo_id=[1, 18]
        angle=[-90, 90]
        runtime=[0, 2000]
        """
        if servo_id < 1 or servo_id > 18:
            return
        if angle < -90 or angle > 90:
            return
        runtime = self.__limit_value(runtime, 0, 2000)
        value_s = bytearray(struct.pack('h', int(runtime)))
        ORDER["MOTOR"][1] = int(servo_id)
        ORDER["MOTOR"][2] = angle & 0xFF
        ORDER["MOTOR"][3] = value_s[1]
        ORDER["MOTOR"][4] = value_s[0]
        self.__send("MOTOR", len=4)

    def leg_motor(self, leg_id, angles, runtime=100):
        """
        控制机器人腿部三个舵机转动，角度控制范围：-90~90
        Control the rotation of the three servo of the robot's legs, and the Angle control range is -90~90
        leg_id=[1, 6]
        angles=[a1, a2, a3], Param angles is an array that save the angle of three servo
        runtime=[0, 2000]
        """
        if leg_id < 1 or leg_id > 6:
            return
        if len(angles) != 3:
            return
        for i in range(3):
            if angles[i] < -90 or angles[i] > 90:
                return
        runtime = self.__limit_value(runtime, 0, 2000)
        value_s = bytearray(struct.pack('h', int(runtime)))
        ORDER["LEG"][1] = int(leg_id)
        ORDER["LEG"][2] = angles[0] & 0xFF
        ORDER["LEG"][3] = angles[1] & 0xFF
        ORDER["LEG"][4] = angles[2] & 0xFF
        ORDER["LEG"][5] = value_s[1]
        ORDER["LEG"][6] = value_s[0]
        self.__send("LEG", len=6)


    def read_motor(self):
        """
        读取18个舵机的角度, 返回一个数组
        Read the angles of the 18 servo, return an array
        """
        self.__read(ORDER["MOTOR_ANGLE"][0], 18)
        time.sleep(.1)
        angle = []
        if self.__unpack():
            for i in range(18):
                angle.append(struct.unpack('b', bytearray(self.rx_data[i:i+1]))[0])
            return angle
        return None

    def read_leg(self, leg_id):
        '''
        读取一条腿上三个舵机的角度，返回一个数组
        Reads the angles of the three servo on leg, return an array
        leg_id=[1, 6]
        '''
        if leg_id < 1 or leg_id > 6:
            return
        start_index = (int(leg_id) - 1) * 3
        end_index = start_index + 3
        leg_angles = self.read_motor()
        if leg_angles == None:
            return None
        leg_values = leg_angles[start_index:end_index]
        return leg_values

    def read_battery(self, voltage=True):
        '''
        返回电池电压或电量百分比
        Return battery voltage or percentage of battery 
        '''
        print(f"[DEBUG] MutoLibCore.read_battery called with voltage={voltage}")
        self.__read(ORDER["BATTERY"][0], 1)
        time.sleep(0.05)
        battery = 0
        def calculate_battery_percentage(voltage):
            """
            根据电压计算剩余电量百分比
            
            参数:
            voltage: 当前电池电压(V)
            
            返回:
            电量百分比(0-100)
            """
            # 电压-电量对应点 (电压, 百分比)
            voltage_table = [
                (5.6, 0),    # 低压保护点
                (6.0, 5),    # 几乎没电
                (6.8, 10),   # 低电量
                (7.0, 20),   
                (7.2, 30),   
                (7.4, 50),   # 标称电压
                (7.6, 70),   
                (7.8, 80),   
                (8.0, 90),   
                (8.4, 100)   # 满电
            ]
            
            # 边界检查
            if voltage <= 5.6:
                return 0
            if voltage >= 8.4:
                return 100
            
            # 线性插值计算
            for i in range(len(voltage_table) - 1):
                v1, p1 = voltage_table[i]
                v2, p2 = voltage_table[i + 1]
                
                if v1 <= voltage <= v2:
                    # 线性插值公式
                    percentage = p1 + (voltage - v1) * (p2 - p1) / (v2 - v1)
                    return round(percentage, 1)
            
            return 0
        
        if self.__unpack():
            # 真实百分比计算
            raw_voltage = self.rx_data[0]/100.0*8.4
            battery = calculate_battery_percentage(raw_voltage)
            print(f"[DEBUG] MutoLibCore.read_battery: raw_data={self.rx_data[0]}, calculated_voltage={raw_voltage}V, percentage={battery}%")
        else:
            print(f"[ERROR] MutoLibCore.read_battery: __unpack() failed, rx_data={getattr(self, 'rx_data', 'None')}")
            return None
            
        if not voltage:
            print(f"[DEBUG] MutoLibCore.read_battery: converting percentage {battery}% to voltage")
            battery = round(battery/100.0*8.4, 1)
            print(f"[DEBUG] MutoLibCore.read_battery: converted voltage={battery}V")
        
        print(f"[DEBUG] MutoLibCore.read_battery: returning {battery} ({'%' if voltage else 'V'})")
        return battery

    def read_version(self):
        '''
        返回固件版本号
        Return the firmware version number
        '''
        self.__read(ORDER["FIRMWARE_VERSION"][0], 1)
        time.sleep(0.05)
        firmware_version = None
        if self.__unpack():
            firmware_version = hex(self.rx_data[0])
        return firmware_version

    def read_IMU(self):
        '''
        返回IMU融合后的角度:[roll, pitch, yaw, temp]
        Return the IMU Angle:[roll, pitch, yaw, temp]
        '''
        self.__read(ORDER["ATTITUDE_ANGLE"][0], 7)
        time.sleep(0.05)
        if self.__unpack():
            roll = struct.unpack('>h', bytearray(self.rx_data[0:2]))[0] / 100.0
            pitch = struct.unpack('>h', bytearray(self.rx_data[2:4]))[0] / 100.0
            yaw = struct.unpack('>h', bytearray(self.rx_data[4:6]))[0] / 100.0
            temp = struct.unpack('B', bytearray(self.rx_data[6:7]))[0]
            return [roll, pitch, yaw, temp]
        else:
            return None

    def read_IMU_Raw(self):
        '''
        返回IMU原始数据: [acc_x, acc_y, acc_z, gyro_x, gyro_y, gyro_z, mag_x, mag_y, mag_z]
        Return the original IMU data: [acc_x, acc_y, acc_z, gyro_x, gyro_y, gyro_z, mag_x, mag_y, mag_z]
        '''
        self.__read(ORDER["IMU_RAW"][0], 18)
        time.sleep(0.05)
        if self.__unpack():
            acc_x = struct.unpack('>h', bytearray(self.rx_data[0:2]))[0]
            acc_y = struct.unpack('>h', bytearray(self.rx_data[2:4]))[0]
            acc_z = struct.unpack('>h', bytearray(self.rx_data[4:6]))[0]
            gyro_x = struct.unpack('>h', bytearray(self.rx_data[6:8]))[0]
            gyro_y = struct.unpack('>h', bytearray(self.rx_data[8:10]))[0]
            gyro_z = struct.unpack('>h', bytearray(self.rx_data[10:12]))[0]
            mag_x = struct.unpack('>h', bytearray(self.rx_data[12:14]))[0]
            mag_y = struct.unpack('>h', bytearray(self.rx_data[14:16]))[0]
            mag_z = struct.unpack('>h', bytearray(self.rx_data[16:18]))[0]
            return [acc_x, acc_y, acc_z, gyro_x, gyro_y, gyro_z, mag_x, mag_y, mag_z]
        else:
            return None


    def read_offset_angle(self, servo_id):
        '''
        返回舵机角度偏移值
        Return the servo angle offset
        servo_id=[1, 18]
        '''
        if servo_id < 1 or servo_id > 18:
            return
        self.__read(ORDER["SERVO_OFFSET"][0], int(servo_id))
        time.sleep(0.05)
        if self.__unpack():
            rx_id = self.rx_data[0]
            offset = struct.unpack('>h', bytearray(self.rx_data[1:3]))[0]
            # print("rx_id:", rx_id, offset)
            return offset
        else:
            return None

    
    def move(self, x, y, z):
        '''STM32 firmware gait — vervangt Python IK hexapod.move()'''
        def _cmd(addr, data=0):
            body = [0x01, addr, data]
            chk = (0xFF - ((0x09 + sum(body)) & 0xFF)) & 0xFF
            return bytes([0x55, 0x00, 0x09] + body + [chk, 0x00, 0xAA])

        if x == 0 and y == 0 and z == 0:
            self.ser.write(_cmd(0x11, 0x00))
            return
        level = 15
        if x > 0:
            self.ser.write(_cmd(0x12, level))
        elif x < 0:
            self.ser.write(_cmd(0x13, level))
        elif y > 0:
            self.ser.write(_cmd(0x14, level))
        elif y < 0:
            self.ser.write(_cmd(0x15, level))
        elif z > 0:
            self.ser.write(_cmd(0x16, level))
        elif z < 0:
            self.ser.write(_cmd(0x17, level))
    def forward_with_speed(self, speed_ms):
        '''
        以指定速度前进，使用move方法实现精细速度控制
        Forward with specified speed using move method for fine speed control
        speed_ms: 目标速度(米/秒) Target speed in m/s
        '''
        # 根据速度映射表找到最接近的档位
        # Find the closest level based on speed mapping
        best_level = 0
        min_diff = float('inf')
        for level, mapped_speed in self.__speed_mapping.items():
            if level > 0:  # 只考虑正向档位 Only consider positive levels
                diff = abs(mapped_speed - speed_ms)
                if diff < min_diff:
                    min_diff = diff
                    best_level = level
        
        if best_level > 0:
            self.move(best_level, 0, 0)
        else:
            self.move(0, 0, 0)  # 停止
    
    def back_with_speed(self, speed_ms):
        '''
        以指定速度后退，使用move方法实现精细速度控制
        Backward with specified speed using move method for fine speed control
        speed_ms: 目标速度(米/秒) Target speed in m/s
        '''
        # 根据速度映射表找到最接近的档位
        # Find the closest level based on speed mapping
        best_level = 0
        min_diff = float('inf')
        for level, mapped_speed in self.__speed_mapping.items():
            if level < 0:  # 只考虑负向档位 Only consider negative levels
                diff = abs(abs(mapped_speed) - speed_ms)
                if diff < min_diff:
                    min_diff = diff
                    best_level = level
        
        if best_level < 0:
            self.move(best_level, 0, 0)
        else:
            self.move(0, 0, 0)  # 停止
    
    def left_with_speed(self, speed_ms):
        '''
        以指定速度左移，使用move方法实现精细速度控制
        Left shift with specified speed using move method for fine speed control
        speed_ms: 目标速度(米/秒) Target speed in m/s
        '''
        # 根据速度映射表找到最接近的档位
        # Find the closest level based on speed mapping
        best_level = 0
        min_diff = float('inf')
        for level, mapped_speed in self.__speed_mapping.items():
            if level < 0:  # 左移使用负值 Left shift uses negative values
                diff = abs(abs(mapped_speed) - speed_ms)
                if diff < min_diff:
                    min_diff = diff
                    best_level = level
        
        if best_level < 0:
            self.move(0, best_level, 0)
        else:
            self.move(0, 0, 0)  # 停止
    
    def right_with_speed(self, speed_ms):
        '''
        以指定速度右移，使用move方法实现精细速度控制
        Right shift with specified speed using move method for fine speed control
        speed_ms: 目标速度(米/秒) Target speed in m/s
        '''
        # 根据速度映射表找到最接近的档位
        # Find the closest level based on speed mapping
        best_level = 0
        min_diff = float('inf')
        for level, mapped_speed in self.__speed_mapping.items():
            if level > 0:  # 右移使用正值 Right shift uses positive values
                diff = abs(mapped_speed - speed_ms)
                if diff < min_diff:
                    min_diff = diff
                    best_level = level
        
        if best_level > 0:
            self.move(0, best_level, 0)
        else:
            self.move(0, 0, 0)  # 停止
    
    def turnleft_with_speed(self, angular_speed_deg_s):
        '''
        以指定角速度左转，使用move方法实现精细速度控制
        角速度档位限制: 只支持10-20范围，超出范围使用默认值10
        Turn left with specified angular speed using move method for fine speed control
        Angular speed level limit: only supports 10-20 range, use default value 10 if out of range
        angular_speed_deg_s: 目标角速度(度/秒) Target angular speed in deg/s
        '''
        # 将角速度转换为线速度近似值（简化处理）
        # Convert angular speed to linear speed approximation (simplified)
        speed_ms = angular_speed_deg_s * 0.01  # 简化转换系数
        
        # 根据速度映射表找到最接近的档位，限制在10-20范围内
        best_level = 10  # 默认使用10档位
        min_diff = float('inf')
        for level, mapped_speed in self.__speed_mapping.items():
            if level > 0 and 10 <= level <= 20:  # 左转使用正值，限制范围
                diff = abs(mapped_speed - speed_ms)
                if diff < min_diff:
                    min_diff = diff
                    best_level = level
        
        # 检查档位是否在允许范围内
        if 10 <= best_level <= 20:
            self.move(0, 0, best_level)
        else:
            if self.debug:
                print(f"[WARNING] 角速度档位超出限制，使用默认档位10 / Angular speed level out of range, using default level 10")
            self.move(0, 0, 10)  # 使用默认档位
    
    def turnright_with_speed(self, angular_speed_deg_s):
        '''
        以指定角速度右转，使用move方法实现精细速度控制
        角速度档位限制: 只支持10-20范围，超出范围使用默认值10
        Turn right with specified angular speed using move method for fine speed control
        Angular speed level limit: only supports 10-20 range, use default value 10 if out of range
        angular_speed_deg_s: 目标角速度(度/秒) Target angular speed in deg/s
        '''
        # 将角速度转换为线速度近似值（简化处理）
        # Convert angular speed to linear speed approximation (simplified)
        speed_ms = angular_speed_deg_s * 0.01  # 简化转换系数
        
        # 根据速度映射表找到最接近的档位，限制在10-20范围内
        best_level = -10  # 默认使用-10档位
        min_diff = float('inf')
        for level, mapped_speed in self.__speed_mapping.items():
            if level < 0 and 10 <= abs(level) <= 20:  # 右转使用负值，限制范围
                diff = abs(abs(mapped_speed) - speed_ms)
                if diff < min_diff:
                    min_diff = diff
                    best_level = level
        
        # 检查档位是否在允许范围内
        if 10 <= abs(best_level) <= 20:
            self.move(0, 0, best_level)
        else:
            if self.debug:
                print(f"[WARNING] 角速度档位超出限制，使用默认档位-10 / Angular speed level out of range, using default level -10")
            self.move(0, 0, -10)  # 使用默认档位


if __name__ == '__main__':
    robot = Muto(debug=True)
    version = robot.read_version()
    print("version:", version)

