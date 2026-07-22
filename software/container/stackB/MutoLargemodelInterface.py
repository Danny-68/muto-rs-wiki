#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
六足机器人高级控制接口
Hexapod Robot Advanced Control Interface

提供统一的动作接口，支持可配置的全局参数和校准数据
Provides unified action interface with configurable global parameters and calibration data

作者: YAHBOOM | Gentle Xu
Author: YAHBOOM | Gentle Xu
日期: 2025/09
Date: 2025/09
"""

import time
import random
import subprocess
import os
import signal
import json
import atexit
import sys
from typing import Optional, Union, Dict, Any
from .core.MutoLibCore import Muto
from .Largemodel import (
    ConfigManager, 
    RobotController, 
    SensorManager, 
    PositionManager, 
    ResponseValidator, 
    NavigationManager,
    ActionLearningManager,
    ensure_response_format
)
from .Largemodel.memory_manager import MemoryManager

# 导入语音模块
try:
    import sys
    import os
    # 添加语音模块路径
    voice_module_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'voice_module')
    if voice_module_path not in sys.path:
        sys.path.insert(0, voice_module_path)
    from voice_module.voice_interface import VoiceInterface
    VOICE_MODULE_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Voice module not available: {e}")
    VoiceInterface = None
    VOICE_MODULE_AVAILABLE = False


class MutoController:
    """
    六足机器人高级控制器
    Advanced controller for hexapod robot
    
    提供统一的动作接口，支持多种参数组合和优先级处理
    Provides unified action interface with multiple parameter combinations and priority handling
    """
    
    def __init__(self, port: str = "/dev/myserial", debug: bool = False, 
                 calibration_distance_cm: float = 28, calibration_steps: int = 10,
                 config_file: str = None):
        """
        初始化机器人控制器
        Initialize robot controller
        
        Args:
            port: 串口端口 Serial port
            debug: 调试模式 Debug mode
            calibration_distance_cm: 校准距离(厘米) Calibration distance in cm
            calibration_steps: 校准步数 Calibration steps
            config_file: Config file path Configuration file path
        """
        self.debug = debug  # 保存调试模式设置
        self.hardware_connected = False
        
        # 初始化硬件连接
        self.robot = Muto(port=port, debug=debug)
        self.hardware_connected = True
        
        # 初始化各个功能模块
        self.config_manager = ConfigManager(calibration_distance_cm, calibration_steps, debug, config_file)
        self.robot_controller = RobotController(self.robot, self.config_manager.default_config, self.config_manager.step_distance_cm, self.config_manager.speed_calibration, self.config_manager.angular_speed_calibration)
        self.sensor_manager = SensorManager(self.robot)
        self.position_manager = PositionManager(self)
        self.navigation_manager = NavigationManager(self)
        self.action_learning_manager = ActionLearningManager(self.robot_controller)
        self.response_validator = ResponseValidator(self)
        
        # 初始化记忆管理器
        self.memory_manager = MemoryManager(debug=debug)
        
        # 初始化语音接口
        self.voice_interface = None
        
        # 初始化巡线进程
        self.line_follow_process = None
        self.line_follow_launch_process = None
        
        # 初始化KCF追踪进程
        self.kcf_launch_process = None
        self.kcf_monitor_thread = None
        self.kcf_monitor_running = False

        # 注册清理函数
        atexit.register(self.cleanup)

        if VOICE_MODULE_AVAILABLE:
            try:
                self.voice_interface = VoiceInterface()
                if debug:
                    print("Voice interface initialized successfully")
            except Exception as e:
                if debug:
                    print(f"Warning: Failed to initialize voice interface: {e}")
        
        # lf.step_distance_cm = self.config_manager.step_distance_cm
        self.step_distance_m = self.config_manager.step_distance_m
        self.speed_calibration = self.config_manager.speed_calibration
        self.default_config = self.config_manager.default_config
    
    def cleanup(self):
        """
        程序退出时的清理函数
        Cleanup function when program exits
        """
        if self.debug:
            print("Cleaning up MutoController resources...")
            
        # 停止KCF追踪
        if self.kcf_launch_process:
            self.stop_kcf_tracking()
            
        # 停止巡线
        if self.line_follow_launch_process:
            self.stop_line_follow()
            
        if self.debug:
            print("Cleanup finished.")

    # ==================== 配置管理接口 Configuration Management Interface ====================
    
    def update_config(self, **kwargs) -> tuple:
        """更新全局配置 Update global configuration"""
        return self.config_manager.update_config(**kwargs)
    
    def get_config(self) -> tuple:
        """获取配置 Get configuration"""
        return self.config_manager.get_config()
    
    def update_calibration(self, calibration_distance_cm: float, calibration_steps: int) -> tuple:
        """更新校准参数 Update calibration parameters"""
        result = self.config_manager.update_calibration(calibration_distance_cm, calibration_steps)
        # 更新向后兼容性属性
        self.calibration_distance_cm = calibration_distance_cm
        self.calibration_steps = calibration_steps
        self.step_distance_m = self.config_manager.step_distance_m
        return result
    
    def update_speed_calibration(self, calibration_data: Dict[int, float]) -> tuple:
        """更新速度标定数据 Update speed calibration data"""
        result = self.config_manager.update_speed_calibration(calibration_data)
        self.speed_calibration = self.config_manager.speed_calibration
        return result
    
    def calibrate_speed_levels(self) -> tuple:
        """校准速度档位 Calibrate speed levels"""
        return self.config_manager.calibrate_speed_levels()
    
    # ==================== 基础移动接口 Basic Movement Interface ====================
    
    def forward(self, steps: Optional[int] = None, distance_m: Optional[float] = None,
                time_s: Optional[float] = None, speed_ms: Optional[float] = None) -> tuple:
        """前进动作 Forward movement"""
        result = self._execute_move_action('forward', steps, distance_m, time_s, speed_ms)
        # 物理复位：不设置取消标志，仅让机器人停下
        try:
            self.robot.move(0, 0, 0)
            time.sleep(0.05)
            self.robot.stay_put()
        except Exception:
            pass
        return result
    
    def backward(self, steps: Optional[int] = None, distance_m: Optional[float] = None,
                 time_s: Optional[float] = None, speed_ms: Optional[float] = None) -> tuple:
        """后退动作 Backward movement"""
        result = self._execute_move_action('backward', steps, distance_m, time_s, speed_ms)
        try:
            self.robot.move(0, 0, 0)
            time.sleep(0.05)
            self.robot.stay_put()
        except Exception:
            pass
        return result
    
    def shift_left(self, steps: Optional[int] = None, distance_m: Optional[float] = None,
                   time_s: Optional[float] = None, speed_ms: Optional[float] = None) -> tuple:
        """左平移动作 Left shift movement"""
        result = self._execute_move_action('left', steps, distance_m, time_s, speed_ms)
        try:
            self.robot.move(0, 0, 0)
            time.sleep(0.05)
            self.robot.stay_put()
        except Exception:
            pass
        return result
    
    def shift_right(self, steps: Optional[int] = None, distance_m: Optional[float] = None,
                    time_s: Optional[float] = None, speed_ms: Optional[float] = None) -> tuple:
        """右平移动作 Right shift movement"""
        result = self._execute_move_action('right', steps, distance_m, time_s, speed_ms)
        try:
            self.robot.move(0, 0, 0)
            time.sleep(0.05)
            self.robot.stay_put()
        except Exception:
            pass
        return result
    
    def rotate(self, direction: Optional[str] = None, angle_deg: Optional[float] = None,
               time_s: Optional[float] = None, angular_speed_deg_s: Optional[float] = None) -> tuple:
        """旋转动作 Rotation movement"""
        result = self.robot_controller.rotate(direction, angle_deg, time_s, angular_speed_deg_s)
        try:
            self.robot.move(0, 0, 0)
            time.sleep(0.05)
            self.robot.stay_put()
        except Exception:
            pass
        return result
    
    # ==================== 预设动作接口 Preset Action Interface ====================
    
    def adjust_height(self, level: Optional[int] = None) -> tuple:
        """调整身高 Adjust height"""
        return self.robot_controller.execute_preset_action('adjust_height', level=level)
    
    def head_move(self, level: Optional[int] = None, direction: Optional[str] = None) -> tuple:
        """头部移动 Head movement"""
        return self.robot_controller.execute_preset_action('head_move', level=level, direction=direction)
    
    def stretch(self) -> tuple:
        """伸展动作 Stretch action"""
        return self.robot_controller.execute_preset_action('stretch')
    
    def say_hello(self) -> tuple:
        """打招呼动作 Say hello action"""
        return self.robot_controller.execute_preset_action('say_hello')

    def raise_left_hand(self, hold_time: Optional[float] = None, amplitude: Optional[int] = None, speed_ms: Optional[int] = None) -> tuple:
        """举起左手 Raise left hand"""
        kwargs = {}
        if hold_time is not None:
            kwargs['hold_time'] = hold_time
        if amplitude is not None:
            kwargs['amplitude'] = amplitude
        if speed_ms is not None:
            kwargs['speed_ms'] = speed_ms
        return self.robot_controller.execute_preset_action('raise_left_hand', **kwargs)

    def raise_right_hand(self, hold_time: Optional[float] = None, amplitude: Optional[int] = None, speed_ms: Optional[int] = None) -> tuple:
        """举起右手 Raise right hand"""
        kwargs = {}
        if hold_time is not None:
            kwargs['hold_time'] = hold_time
        if amplitude is not None:
            kwargs['amplitude'] = amplitude
        if speed_ms is not None:
            kwargs['speed_ms'] = speed_ms
        return self.robot_controller.execute_preset_action('raise_right_hand', **kwargs)

    def point_left_front(self, hold_time: Optional[float] = None, amplitude: Optional[int] = None, speed_ms: Optional[int] = None) -> tuple:
        """指向左前方 Point left-front"""
        kwargs = {}
        if hold_time is not None:
            kwargs['hold_time'] = hold_time
        if amplitude is not None:
            kwargs['amplitude'] = amplitude
        if speed_ms is not None:
            kwargs['speed_ms'] = speed_ms
        return self.robot_controller.execute_preset_action('point_left_front', **kwargs)

    def point_right_front(self, hold_time: Optional[float] = None, amplitude: Optional[int] = None, speed_ms: Optional[int] = None) -> tuple:
        """指向右前方 Point right-front"""
        kwargs = {}
        if hold_time is not None:
            kwargs['hold_time'] = hold_time
        if amplitude is not None:
            kwargs['amplitude'] = amplitude
        if speed_ms is not None:
            kwargs['speed_ms'] = speed_ms
        return self.robot_controller.execute_preset_action('point_right_front', **kwargs)
    
    def fear_retreat(self) -> tuple:
        """恐惧后退动作 Fear retreat action"""
        result = self.robot_controller.execute_preset_action('fear_retreat')
        try:
            self.robot.move(0, 0, 0)
            time.sleep(0.05)
            self.robot.stay_put()
        except Exception:
            pass
        return result
    
    def warm_up_squat(self) -> tuple:
        """热身蹲起动作 Warm up squat action"""
        return self.robot_controller.execute_preset_action('warm_up_squat')
    
    def spin_in_place(self) -> tuple:
        """原地旋转动作 Spin in place action"""
        result = self.robot_controller.execute_preset_action('spin_in_place')
        try:
            self.robot.move(0, 0, 0)
            time.sleep(0.05)
            self.robot.stay_put()
        except Exception:
            pass
        return result
    
    def wave_no(self) -> tuple:
        """摆手说不动作 Wave no action"""
        return self.robot_controller.execute_preset_action('wave_no')
    
    def curl_up(self) -> tuple:
        """蜷缩动作 Curl up action"""
        return self.robot_controller.execute_preset_action('curl_up')
    
    def big_stride(self) -> tuple:
        """大步走动作 Big stride action"""
        result = self.robot_controller.execute_preset_action('big_stride')
        try:
            self.robot.move(0, 0, 0)
            time.sleep(0.05)
            self.robot.stay_put()
        except Exception:
            pass
        return result
    
    def stop_action(self) -> tuple:
        """停止动作 Stop action"""
        # 触发取消标志，确保循环动作能被打断
        try:
            self.robot_controller.request_cancel()
        except Exception:
            pass
        # 先停止所有持续性动作
        self.robot_controller.stop_all_continuous_actions()
        # 然后执行常规停止动作
        return self.robot_controller.execute_preset_action('stop_action')
    
    # ==================== 机器人状态接口 Robot Status Interface ====================
    
    def stop(self) -> tuple:
        """停止机器人 Stop robot"""
        try:
            # 设置取消标志，确保循环中的动作能够立刻跳出
            self.robot_controller.request_cancel()
            # 停止巡线任务
            self.stop_line_follow()
        except Exception:
            pass
        return self.robot_controller.stop()
    
    def move(self, x: int, y: int, z: int) -> tuple:
        """
        控制机器人运动，需要一直调用这个函数机器人才会一直动。
        Control robot movement, need to keep calling this function for continuous movement.
        
        Args:
            x: X轴运动参数 X-axis movement parameter [-30, 30]
            y: Y轴运动参数 Y-axis movement parameter [-30, 30] 
            z: Z轴运动参数 Z-axis movement parameter [-30, 30]
            
        Returns:
            tuple: (success: bool, message: str)
        """
        try:
            # 参数范围检查
            x = max(-30, min(30, int(x)))
            y = max(-30, min(30, int(y)))
            z = max(-30, min(30, int(z)))
            
            # 调用底层move方法
            self.robot.move(x, y, z)
            
            return True, f"Move command executed: x={x}, y={y}, z={z}"
        except Exception as e:
            return False, f"Move command failed: {str(e)}"
    
    def get_status(self) -> tuple:
        """获取机器人状态 Get robot status"""
        return self.robot_controller.get_status()
    
    def print_status(self) -> tuple:
        """打印机器人状态 Print robot status"""
        return self.robot_controller.print_status()
    
    def get_firmware_version(self) -> tuple:
        """获取固件版本 Get firmware version"""
        return self.robot_controller.get_firmware_version()
    
    def get_battery_info(self, as_voltage: bool = True) -> tuple:
        """获取电池信息 Get battery information"""
        return self.robot_controller.get_battery_info(as_voltage)
    
    def get_servo_angles(self, servo_id: Optional[int] = None) -> tuple:
        """获取舵机角度 Get servo angles"""
        return self.robot_controller.get_servo_angles(servo_id)
    
    def get_leg_angles(self, leg_id: int) -> tuple:
        """获取腿部角度 Get leg angles"""
        return self.robot_controller.get_leg_angles(leg_id)
    
    def get_attitude(self) -> tuple:
        """获取姿态信息 Get attitude information"""
        return self.robot_controller.get_attitude()
    
    def get_imu_raw_data(self) -> tuple:
        """获取IMU原始数据 Get IMU raw data"""
        return self.robot_controller.get_imu_raw_data()
    
    def get_servo_offset(self, servo_id: int) -> tuple:
        """获取舵机偏移 Get servo offset"""
        return self.robot_controller.get_servo_offset(servo_id)
    
    def print_system_info(self) -> tuple:
        """打印系统信息 Print system information"""
        return self.sensor_manager.print_system_info()
    
    # ==================== 传感器管理接口 Sensor Management Interface ====================
    
    def check_ros2_node_running(self, node_name: str, namespace: str = "/") -> tuple:
        """检查ROS2节点运行状态 Check ROS2 node running status"""
        return self.sensor_manager.check_ros2_node_running(node_name, namespace)
    
    def check_ros2_topic_active(self, topic_name: str, expected_type: str = "sensor_msgs/msg/Image") -> tuple:
        """检查ROS2话题活跃状态 Check ROS2 topic active status"""
        return self.sensor_manager.check_ros2_topic_active(topic_name, expected_type)
    
    def start_camera(self, check_before_start: bool = True, wait_time_s: float = 5.0) -> tuple:
        """启动相机 Start camera"""
        return self.sensor_manager.start_camera(check_before_start, wait_time_s)
    
    def get_camera_status(self) -> tuple:
        """获取相机状态 Get camera status"""
        return self.sensor_manager.get_camera_status()
    
    def check_camera_status(self) -> tuple:
        """检查相机状态 Check camera status"""
        return self.sensor_manager.check_camera_status()
    
    def stop_camera(self, force_kill: bool = False, wait_time_s: float = 3.0) -> tuple:
        """停止相机 Stop camera"""
        return self.sensor_manager.stop_camera(force_kill, wait_time_s)
    
    def capture_image(self, save_path: str = None, timeout_s: float = 10.0, 
                     check_camera_first: bool = True, image_format: str = "jpg") -> tuple:
        """拍摄图像 Capture image"""
        return self.sensor_manager.capture_image(save_path, timeout_s, check_camera_first, image_format)
    
    def get_depth_at_point(self, x: int, y: int, timeout_s: float = 10.0) -> tuple:
        """获取指定点的深度信息 Get depth information at specified point"""
        return self.sensor_manager.get_depth_at_point(x, y, timeout_s)
    
    def start_lidar(self, wait_time_s: float = 10.0, check_before_start: bool = True) -> tuple:
        """启动雷达 Start lidar"""
        return self.sensor_manager.start_lidar(wait_time_s, check_before_start)
    
    def get_lidar_data(self, timeout_s: float = 10.0, sample_count: int = 1) -> tuple:
        """获取雷达数据 Get lidar data"""
        return self.sensor_manager.get_lidar_data(timeout_s, sample_count)
    
    def _get_lidar_type(self) -> str:
        """
        获取当前雷达类型
        Get current lidar type from environment variable
        
        Returns:
            str: 雷达类型 ('a1' 或 '4ROS') Lidar type ('a1' or '4ROS')
        """
        return self.sensor_manager._get_lidar_type()
    
    def check_lidar_status(self) -> tuple:
        """检查雷达状态 Check lidar status"""
        return self.sensor_manager.check_lidar_status()
    
    def stop_lidar(self, force_kill: bool = False, wait_time_s: float = 3.0) -> tuple:
        """停止雷达 Stop lidar"""
        return self.sensor_manager.stop_lidar(force_kill, wait_time_s)
    
    def get_lidar_360_data(self, timeout_s: float = 5.0) -> tuple:
        """获取360度全方位雷达信息 Get 360-degree full range lidar data"""
        return self.sensor_manager.get_lidar_360_data(timeout_s)
    
    def get_lidar_range_at_angle(self, target_angle: float, angle_tolerance: float = 0.2, timeout_s: float = 5.0) -> tuple:
        """获取指定角度的雷达测距信息 Get lidar range data at specified angle"""
        return self.sensor_manager.get_lidar_range_at_angle(target_angle, angle_tolerance, timeout_s)
    
    def get_robot_position_in_map(self, timeout_s: float = 10.0) -> tuple:
        """获取机器人在地图中的位置 Get robot position in map"""
        return self.sensor_manager.get_robot_position_in_map(timeout_s)
    
    # ==================== 位置管理接口 Position Management Interface ====================
    
    def save_current_position(self, position_name: str, timeout_s: float = 10.0) -> tuple:
        """保存当前位置 Save current position"""
        return self.position_manager.save_current_position(position_name, timeout_s)
    
    def list_saved_positions(self) -> tuple:
        """列出已保存的位置 List saved positions"""
        return self.position_manager.list_saved_positions()
    
    def get_saved_position(self, position_name: str) -> tuple:
        """获取已保存的位置信息 Get saved position information"""
        return self.position_manager.get_saved_position(position_name)
    
    def delete_saved_position(self, position_name: str) -> tuple:
        """删除已保存的位置 Delete saved position"""
        return self.position_manager.delete_saved_position(position_name)
    
    def clear_all_positions(self, confirm: bool = True) -> tuple:
        return self.position_manager.clear_all_positions(confirm)
    
    # ==================== 导航管理接口 Navigation Management Interface ====================
    
    
    def set_initial_pose(self, x: float, y: float, yaw: float, timeout_s: float = 10.0) -> tuple:
        """设置机器人初始位姿 Set robot initial pose"""
        return self.navigation_manager.set_initial_pose(x, y, yaw)
    
    def navigate_to_pose(self, x: float, y: float, yaw: float, timeout_s: float = 120.0) -> tuple:
        """导航到指定位姿 Navigate to specified pose"""
        return self.navigation_manager.navigate_to_pose(x, y, yaw, timeout=timeout_s)
    
    def cancel_navigation(self) -> tuple:
        """取消当前导航任务 Cancel current navigation task"""
        return self.navigation_manager.cancel_navigation()

    def navigate_to_saved_position(self, position_name: str, timeout_s: float = 120.0) -> tuple:
        """导航到已保存的位置 Navigate to saved position"""
        return self.navigation_manager.navigate_to_saved_position(position_name, timeout_s)

    
    # ==================== 基于move方法的移动控制 Move-based Movement Control ====================
    
    def _execute_move_action(self, direction: str, steps: Optional[int] = None, 
                           distance_m: Optional[float] = None, time_s: Optional[float] = None, 
                           speed_ms: Optional[float] = None) -> tuple:
        """
        使用move方法执行移动动作
        Execute movement action using move method
        
        Args:
            direction: 移动方向 Movement direction ('forward', 'backward', 'left', 'right')
            steps: 步数 Number of steps
            distance_m: 距离(米) Distance in meters
            time_s: 时间(秒) Time in seconds
            speed_ms: 速度(米/秒) Speed in m/s
            
        Returns:
            tuple: (success: bool, message: str, data: dict)
        """
        try:
            print(f"[DEBUG] 执行移动动作: {direction}, 距离={distance_m}, 速度={speed_ms}, 步数={steps}, 时间={time_s}")
            
            # 参数解析和优先级处理
            if speed_ms is not None:
                print(f"[DEBUG] 目标速度: {speed_ms} m/s，开始选择最优速度档位...")
                # 使用配置的速度标定数据选择最优档位
                success, message, speed_data = self._select_optimal_speed_level(speed_ms)
                print(f"[DEBUG] 速度档位选择结果: success={success}, message={message}")
                if success:
                    speed_level = speed_data['level']
                    actual_speed = speed_data['speed']
                    print(f"[DEBUG] 选择的速度档位: {speed_level}, 实际速度: {actual_speed} m/s, 速度差: {speed_data.get('speed_diff', 'N/A')}")
                else:
                    speed_level = self.config_manager.default_config.get('robot_speed_level', 10)  # 使用配置文件中的默认档位
                    actual_speed = self.config_manager.speed_calibration.get(speed_level, 0.05)
                    print(f"[DEBUG] 速度档位选择失败，使用默认档位: {speed_level}, 实际速度: {actual_speed} m/s")
                    print(f"[DEBUG] 配置文件中档位{speed_level}的速度: {self.config_manager.speed_calibration.get(speed_level, '未找到')}")
            else:
                speed_level = self.config_manager.default_config.get('robot_speed_level', 10)  # 使用配置文件中的默认档位
                actual_speed = self.config_manager.speed_calibration.get(speed_level, 0.05)
                print(f"[DEBUG] 使用默认速度档位: {speed_level}, 实际速度: {actual_speed} m/s")
                print(f"[DEBUG] 配置文件中档位{speed_level}的速度: {self.config_manager.speed_calibration.get(speed_level, '未找到')}")
            
            # 计算执行时间
            if time_s is not None:
                execution_time = time_s
                print(f"[DEBUG] 使用指定时间: {execution_time} s")
            elif distance_m is not None:
                # 根据距离和实际标定速度计算时间
                execution_time = distance_m / actual_speed
                print(f"[DEBUG] 根据距离计算执行时间: {distance_m} m / {actual_speed} m/s = {execution_time} s")
            elif steps is not None:
                # 根据步数计算时间 (假设每步0.5秒)
                execution_time = steps * 0.5
                print(f"[DEBUG] 根据步数计算执行时间: {steps} steps * 0.5 s/step = {execution_time} s")
            else:
                execution_time = 1.0  # 默认1秒
                print(f"[DEBUG] 使用默认执行时间: {execution_time} s")
            
            # 根据方向设置move参数
            if direction == 'forward':
                x, y, z = speed_level, 0, 0
            elif direction == 'backward':
                x, y, z = -speed_level, 0, 0
            elif direction == 'left':
                x, y, z = 0, speed_level, 0  # 修复：左平移应该是正值
            elif direction == 'right':
                x, y, z = 0, -speed_level, 0  # 修复：右平移应该是负值
            else:
                return False, f"未知的移动方向: {direction}", None
            
            # 检查速度档位是否在有效范围内 Check if speed level is within valid range
            if abs(speed_level) > 30:
                print(f"[WARNING] 速度档位 {speed_level} 超出允许范围 [-30, 30]，将被截断")
                speed_level = max(-30, min(30, speed_level))
                
            print(f"[DEBUG] 移动参数: x={x}, y={y}, z={z}")
            
            # 执行移动
            start_time = time.time()
            end_time = start_time + execution_time
            print(f"[DEBUG] 开始执行移动，预计执行时间: {execution_time} s")
            
            # 获取取消事件对象 (避免在循环中重复查找)
            cancel_event = getattr(self.robot_controller, 'cancel_event', None)
            
            # 取消检查：在进入循环前立即检查一次
            if cancel_event and cancel_event.is_set():
                # 立即停止机器人
                try:
                    self.robot.move(0, 0, 0)
                    time.sleep(0.1)
                    # 尝试发送复位指令
                    if hasattr(self.robot, 'stay_put'):
                        self.robot.stay_put()
                except Exception:
                    pass
                return False, "移动已被取消 Movement canceled before start", {
                    'direction': direction,
                    'speed_level': speed_level,
                    'move_params': {'x': x, 'y': y, 'z': z},
                    'execution_time_s': execution_time,
                    'actual_time_s': 0.0,
                    'target_speed_ms': speed_ms,
                    'actual_speed_ms': actual_speed,
                    'estimated_distance_m': 0.0,
                    'canceled': True
                }
            
            while time.time() < end_time:
                # 高优先级取消检查 High-priority cancel check
                if cancel_event and cancel_event.is_set():
                    try:
                        # 立即停止机器人
                        self.robot.move(0, 0, 0)
                        time.sleep(0.1)
                        if hasattr(self.robot, 'stay_put'):
                            self.robot.stay_put()
                    except Exception:
                        pass
                    actual_time = time.time() - start_time
                    return False, "移动已被取消 Movement canceled", {
                        'direction': direction,
                        'speed_level': speed_level,
                        'move_params': {'x': x, 'y': y, 'z': z},
                        'execution_time_s': execution_time,
                        'actual_time_s': actual_time,
                        'target_speed_ms': speed_ms,
                        'actual_speed_ms': actual_speed,
                        'estimated_distance_m': actual_speed * actual_time,
                        'canceled': True
                    }
                self.robot.move(x, y, z)
                time.sleep(0.05)  # 20Hz控制频率
            
            # 停止机器人
            self.robot.move(0, 0, 0)
            time.sleep(0.1)
            
            actual_time = time.time() - start_time
            print(f"[DEBUG] 移动执行完成，实际执行时间: {actual_time:.3f} s")
            estimated_distance = actual_speed * actual_time
            
            return True, f"{direction}移动执行成功 {direction} movement executed successfully", {
                'direction': direction,
                'speed_level': speed_level,
                'move_params': {'x': x, 'y': y, 'z': z},
                'execution_time_s': execution_time,
                'actual_time_s': actual_time,
                'target_speed_ms': speed_ms,
                'actual_speed_ms': actual_speed,
                'estimated_distance_m': estimated_distance
            }
            
        except Exception as e:
            return False, f"移动执行失败: {str(e)}", None
    
    # ==================== 向后兼容性方法 Backward Compatibility Methods ====================
    
    def _get_calibration_data(self) -> Dict[str, Any]:
        """获取校准数据 Get calibration data (backward compatibility)"""
        return self.config_manager._get_calibration_data()
    
    def _calculate_steps_from_distance(self, distance_m: float) -> tuple:
        """根据距离计算步数 Calculate steps from distance (backward compatibility)"""
        return self.config_manager._calculate_steps_from_distance(distance_m)
    
    def _calculate_step_interval_from_speed(self, speed_ms: float) -> tuple:
        """根据速度计算步间隔 Calculate step interval from speed (backward compatibility)"""
        return self.config_manager._calculate_step_interval_from_speed(speed_ms)
    
    def _select_optimal_speed_level(self, target_speed_ms: float) -> tuple:
        """选择最优速度档位 Select optimal speed level (backward compatibility)"""
        return self.config_manager._select_optimal_speed_level(target_speed_ms)
    
    # ==================== 返回值校验方法 Response Validation Methods ====================
    
    def validate_all_responses(self) -> tuple:
        """验证所有接口方法的返回值格式 Validate return value format of all interface methods"""
        return self.response_validator.validate_all_responses()
    
    @ensure_response_format
    def test_response_format_decorator(self, test_value: Any = None) -> Any:
        """测试返回值格式装饰器 Test response format decorator"""
        return self.response_validator.test_response_format_decorator(test_value)
    
    # ==================== 动作学习接口 Action Learning Interface ====================
    
    def prepare_learning_posture(self) -> tuple:
        """进入准备学习的姿态 Enter the posture ready to learn"""
        try:
            success = self.action_learning_manager.prepare_learning_posture()
            return (True, "学习准备姿态设置完成" if success else "设置学习姿态失败")
        except Exception as e:
            return (False, f"设置学习姿态异常: {str(e)}")
    
    def start_action_learning(self) -> tuple:
        """开始动作学习模式 Start action learning mode"""
        try:
            success = self.action_learning_manager.start_learning()
            return (True, "动作学习模式已启动" if success else "启动学习模式失败")
        except Exception as e:
            return (False, f"启动学习模式异常: {str(e)}")
    
    def stop_action_learning(self) -> tuple:
        """停止动作学习模式 Stop action learning mode"""
        try:
            success = self.action_learning_manager.stop_learning()
            return (True, "动作学习模式已停止" if success else "停止学习模式失败")
        except Exception as e:
            return (False, f"停止学习模式异常: {str(e)}")
    
    def record_current_action(self) -> tuple:
        """记录当前动作 Record current action"""
        try:
            success = self.action_learning_manager.record_current_action()
            sequence_length = len(self.action_learning_manager.current_action_sequence)
            if success:
                return (True, f"动作已记录，当前序列长度: {sequence_length}")
            else:
                return (False, "记录动作失败")
        except Exception as e:
            return (False, f"记录动作异常: {str(e)}")
    
    def save_action_sequence(self, filename: str) -> tuple:
        """保存当前动作序列到文件 Save current action sequence to file"""
        try:
            success = self.action_learning_manager.save_action_sequence(filename)
            return (True, f"动作序列已保存到: {filename}.json" if success else "保存动作序列失败")
        except Exception as e:
            return (False, f"保存动作序列异常: {str(e)}")
    
    def load_action_sequence(self, filename: str) -> tuple:
        """从文件加载动作序列 Load action sequence from file"""
        try:
            actions = self.action_learning_manager.load_action_sequence(filename)
            if actions is not None:
                return (True, {"actions": actions, "count": len(actions)})
            else:
                return (False, "加载动作序列失败")
        except Exception as e:
            return (False, f"加载动作序列异常: {str(e)}")
    
    @ensure_response_format
    def play_action_sequence(self, actions: Optional[list] = None, filename: Optional[str] = None, 
                           speed: int = 800, delay: float = 1.0, speed_multiplier: float = 1.5) -> tuple:
        """播放动作序列 Play action sequence"""
        try:
            # 检查动作学习管理器是否可用
            if not hasattr(self, 'action_learning_manager') or self.action_learning_manager is None:
                return False, "动作学习管理器不可用", {}
            
            # 参数验证
            if actions is None and filename is None:
                return False, "必须提供动作序列数据或文件名", {}
            
            # 如果提供了文件名，从文件加载动作序列
            if filename and not actions:
                actions = self.action_learning_manager.load_action_sequence(filename)
                if not actions:
                    return False, f"无法从文件 {filename} 加载动作序列", {}
            
            # 如果没有提供动作序列，使用当前序列
            if not actions:
                if not self.action_learning_manager.current_action_sequence:
                    return False, "没有可播放的动作序列", {}
                actions = self.action_learning_manager.current_action_sequence
            
            # 在表演前进入准备姿态，确保后腿位置正确
            # Enter preparation posture before performance to ensure correct rear leg positioning
            self.action_learning_manager.prepare_learning_posture()
            import time
            time.sleep(0.5)  # 等待姿态稳定 Wait for posture to stabilize
            
            # 执行动作序列播放
            success = self.action_learning_manager.play_action_sequence(actions, speed, delay, speed_multiplier)
            
            speed_info = f"（{speed_multiplier}倍速）" if speed_multiplier != 1.0 else ""
            message = f"动作序列播放完成，共 {len(actions)} 个动作{speed_info}" if success else "播放动作序列失败"
            200
            return True, message, {
                "action_count": len(actions),
                "speed": speed,
                "delay": delay,
                "speed_multiplier": speed_multiplier,
                "success": success
            }
        except FileNotFoundError as e:
            return False, f"动作文件未找到: {str(e)}", {}
        except ValueError as e:
            return False, f"参数错误: {str(e)}", {}
        except Exception as e:
            return False, f"播放动作序列异常: {str(e)}", {}
    
    def clear_current_action_sequence(self) -> tuple:
        """清空当前动作序列 Clear current action sequence"""
        try:
            success = self.action_learning_manager.clear_current_sequence()
            return (True, "当前动作序列已清空" if success else "清空动作序列失败")
        except Exception as e:
            return (False, f"清空动作序列异常: {str(e)}")
    
    def delete_action_file(self, filename: str) -> tuple:
        """删除动作文件 Delete action file"""
        try:
            success = self.action_learning_manager.delete_action_file(filename)
            return (True, f"文件 {filename}.json 已删除" if success else "删除文件失败")
        except Exception as e:
            return (False, f"删除文件异常: {str(e)}")
    
    def list_action_files(self) -> tuple:
        """列出所有动作文件 List all action files"""
        try:
            files = self.action_learning_manager.list_action_files()
            return (True, {"files": files, "count": len(files)})
        except Exception as e:
            return (False, f"列出文件异常: {str(e)}")
    
    def get_action_learning_status(self) -> tuple:
        """获取动作学习状态 Get action learning status"""
        try:
            status = self.action_learning_manager.get_learning_status()
            return (True, status)
        except Exception as e:
            return (False, f"获取学习状态异常: {str(e)}")
    
    def print_action_learning_status(self) -> tuple:
        """打印动作学习状态 Print action learning status"""
        try:
            self.action_learning_manager.print_status()
            return (True, "状态信息已打印")
        except Exception as e:
            return (False, f"打印状态异常: {str(e)}")


    # ==================== 记忆功能接口 Memory Function Interface ====================
    
    def write_long_term_memory(self, timestamp: str, content: str) -> tuple:
        """
        写入长期记忆（存储到磁盘文件）
        Write to long-term memory (store to disk file)
        
        Args:
            timestamp: 时间戳标识 Timestamp identifier
            content: 记忆内容 Memory content
            
        Returns:
            tuple: (success: bool, message: str)
        """
        try:
            return self.memory_manager.write_long_term_memory(timestamp, content)
        except Exception as e:
            return (False, f"写入长期记忆失败: {str(e)}")
    
    def read_long_term_memory(self, timestamp: str = None, start_time: str = None, end_time: str = None, limit: int = None) -> tuple:
        """
        读取长期记忆（从磁盘文件读取）
        Read from long-term memory (read from disk file)
        
        Args:
            timestamp: 时间戳标识，为None时返回所有记忆 Timestamp identifier, return all if None
            start_time: 开始时间 Start time
            end_time: 结束时间 End time
            limit: 限制返回数量 Limit return count
            
        Returns:
            tuple: (success: bool, data: dict/list/str)
        """
        try:
            return self.memory_manager.read_long_term_memory(timestamp, start_time, end_time, limit)
        except Exception as e:
            return (False, f"读取长期记忆失败: {str(e)}")
    
    def write_short_term_memory(self, timestamp: str, content: str, ttl_seconds: int = None) -> tuple:
        """
        写入短期记忆（存储到内存）
        Write to short-term memory (store to memory)
        
        Args:
            timestamp: 时间戳标识 Timestamp identifier
            content: 记忆内容 Memory content
            ttl_seconds: 生存时间（秒），为None时永久保存直到程序结束 TTL in seconds, permanent if None
            
        Returns:
            tuple: (success: bool, message: str, timestamp: str)
        """
        try:
            return self.memory_manager.write_short_term_memory(timestamp, content, ttl_seconds)
        except Exception as e:
            return (False, f"写入短期记忆失败: {str(e)}", timestamp)
    
    def read_short_term_memory(self, timestamp: str = None, start_time: str = None, end_time: str = None) -> tuple:
        """
        读取短期记忆（从内存读取）
        Read from short-term memory (read from memory)
        
        Args:
            timestamp: 时间戳标识，为None时返回所有记忆 Timestamp identifier, return all if None
            start_time: 开始时间 Start time
            end_time: 结束时间 End time
            
        Returns:
            tuple: (success: bool, data: dict/str)
        """
        try:
            return self.memory_manager.read_short_term_memory(timestamp, start_time, end_time)
        except Exception as e:
            return (False, f"读取短期记忆失败: {str(e)}")
    
    def clear_short_term_memory(self, timestamp: str = None, start_time: str = None, end_time: str = None) -> tuple:
        """
        清除短期记忆
        Clear short-term memory
        
        Args:
            timestamp: 时间戳标识，为None时清除所有记忆 Timestamp identifier, clear all if None
            start_time: 开始时间 Start time
            end_time: 结束时间 End time
            
        Returns:
            tuple: (success: bool, message: str)
        """
        try:
            return self.memory_manager.clear_short_term_memory(timestamp, start_time, end_time)
        except Exception as e:
            return (False, f"清除短期记忆失败: {str(e)}")
    
    def get_memory_status(self) -> tuple:
        """
        获取记忆系统状态
        Get memory system status
        
        Returns:
            tuple: (success: bool, status: dict)
        """
        try:
            return self.memory_manager.get_memory_status()
        except Exception as e:
            return (False, f"获取记忆状态失败: {str(e)}")
    
    def alert_beep(self, frequency: int = 1000, duration: float = 0.5) -> tuple:
        """
        播放系统提示音
        Play system alert beep
        
        Args:
            frequency: 蜂鸣音频率 Beep frequency in Hz
            duration: 蜂鸣音持续时间 Beep duration in seconds
            
        Returns:
            tuple: (success: bool, message: str)
        """
        try:
            # 优先使用语音接口播放提示音
            if self.voice_interface is not None:
                success, message, _ = self.voice_interface.play_system_sound("beep")
                if success:
                    return (True, "系统提示音播放成功")
                else:
                    if self.debug:
                        print(f"语音接口播放提示音失败: {message}")
            
            # 备用方案：使用系统命令播放提示音
            try:
                import platform
                system = platform.system().lower()
                
                if system == "linux":
                    # Linux系统使用beep命令或speaker-test
                    try:
                        subprocess.run(["beep", "-f", str(frequency), "-l", str(int(duration * 1000))], 
                                     check=True, timeout=duration + 1.0, 
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        return (True, "系统提示音播放成功(beep命令)")
                    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
                        # 如果beep命令不可用，尝试使用speaker-test
                        try:
                            subprocess.run(["speaker-test", "-t", "sine", "-f", str(frequency), "-l", "1"], 
                                         timeout=duration + 1.0, 
                                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                            return (True, "系统提示音播放成功(speaker-test)")
                        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
                            pass
                
                elif system == "windows":
                    # Windows系统使用winsound
                    try:
                        import winsound
                        winsound.Beep(frequency, int(duration * 1000))
                        return (True, "系统提示音播放成功(winsound)")
                    except ImportError:
                        pass
                
                # 最后的备用方案：打印提示信息
                if self.debug:
                    print(f"BEEP! 频率: {frequency}Hz, 持续时间: {duration}s")
                return (True, "提示音信号已发送(调试模式)")
                
            except Exception as backup_error:
                if self.debug:
                    print(f"备用提示音播放失败: {backup_error}")
                return (False, f"所有提示音播放方案均失败")
                
        except Exception as e:
            return (False, f"播放系统提示音失败: {str(e)}")
    
    @ensure_response_format
    def start_continuous_action_learning(self, duration_seconds: float = 30.0, 
                                       sample_rate_hz: float = 0.5, 
                                       sequence_name: str = None) -> tuple:
        """
        开始连续高频动作学习
        
        Args:
            duration_seconds: 学习总时长（秒），默认20秒
            sample_rate_hz: 采样频率（Hz），默认1Hz（每1秒采样一次）
            sequence_name: 动作序列名称，默认自动生成
            
        Returns:
            tuple: (success: bool, message: str, data: dict)
        """
        try:
            # 参数验证
            if duration_seconds <= 0:
                return False, "学习时长必须大于0", {}
            if sample_rate_hz <= 0 or sample_rate_hz > 100:
                return False, "采样频率必须在0-100Hz之间", {}
            
            # 计算采样参数
            sample_interval = 1.0 / sample_rate_hz
            total_samples = int(duration_seconds * sample_rate_hz)
            
            # 生成序列名称
            if not sequence_name:
                from datetime import datetime
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                sequence_name = f"continuous_action_{timestamp}"
            
            # 准备学习姿态
            success, message = self.prepare_learning_posture()
            if not success:
                return False, f"准备学习姿态失败: {message}", {}
            
            # 开始动作学习
            success, message = self.start_action_learning()
            if not success:
                return False, f"开始动作学习失败: {message}", {}
            
            # 连续采样学习
            actions = []
            start_time = time.time()
            
            for sample_index in range(total_samples):
                current_time = time.time()
                timestamp = current_time - start_time
                
                # 记录当前动作
                success, message = self.record_current_action()
                if success:
                    # 获取最新记录的动作数据
                    if self.action_learning_manager.current_action_sequence:
                        latest_action = self.action_learning_manager.current_action_sequence[-1]
                        action_entry = {
                            "timestamp": round(timestamp, 3),
                            "sample_index": sample_index,
                            "angles": latest_action.get("angles", [])
                        }
                        actions.append(action_entry)
                
                # 等待下一次采样
                if sample_index < total_samples - 1:
                    time.sleep(sample_interval)
            
            # 停止动作学习
            self.stop_action_learning()
            
            # 构建连续动作数据
            continuous_data = {
                "metadata": {
                    "type": "continuous_action_sequence",
                    "duration_seconds": duration_seconds,
                    "sample_rate_hz": sample_rate_hz,
                    "total_samples": len(actions),
                    "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "sequence_name": sequence_name
                },
                "actions": actions
            }
            
            # 保存到文件
            filename = f"{sequence_name}.json"
            success, save_message = self.action_learning_manager.save_continuous_action_sequence(
                continuous_data, filename
            )
            
            if success:
                return True, f"连续动作学习完成，共采样{len(actions)}个动作点，已保存为{sequence_name}", {
                    "sequence_name": sequence_name,
                    "total_samples": len(actions),
                    "duration_seconds": duration_seconds,
                    "sample_rate_hz": sample_rate_hz,
                    "data": continuous_data
                }
            else:
                return False, f"连续动作学习完成但保存失败: {save_message}", {
                    "sequence_name": sequence_name,
                    "total_samples": len(actions),
                    "duration_seconds": duration_seconds,
                    "sample_rate_hz": sample_rate_hz,
                    "data": continuous_data
                }
                
        except Exception as e:
            # 确保停止学习状态
            try:
                self.stop_action_learning()
            except:
                pass
            return False, f"连续动作学习失败: {str(e)}", {}

    @ensure_response_format
    def play_continuous_action_sequence(self, actions: Optional[list] = None,
                                      filename: Optional[str] = None,
                                      playback_speed: float = 1.0,
                                      smooth_interpolation: bool = True,
                                      speed_multiplier: float = 5.0) -> tuple:
        """
        播放连续动作序列
        
        Args:
            actions: 动作序列数据
            filename: 动作文件名
            playback_speed: 播放速度倍率（1.0=原速，2.0=2倍速）
            smooth_interpolation: 是否启用平滑插值
            speed_multiplier: 额外速度倍数，默认5.0倍速用于演示
            
        Returns:
            tuple: (success: bool, message: str)
        """
        try:
            # 参数验证
            if playback_speed <= 0:
                return False, "播放速度必须大于0", {}
            
            # 获取动作数据
            if actions is None:
                if filename is None:
                    return False, "必须提供动作数据或文件名", {}
                
                # 从文件加载
                success, message, loaded_data = self.action_learning_manager.load_continuous_action_sequence(filename)
                if not success:
                    return False, f"加载动作文件失败: {message}", {}
                
                continuous_data = loaded_data
            else:
                # 直接使用提供的动作数据
                if isinstance(actions, dict) and "actions" in actions:
                    continuous_data = actions
                else:
                    # 兼容旧格式
                    continuous_data = {"actions": actions, "metadata": {}}
            
            action_list = continuous_data.get("actions", [])
            metadata = continuous_data.get("metadata", {})
            
            if not action_list:
                return False, "动作序列为空", {}
            
            # 获取原始采样频率
            original_sample_rate = metadata.get("sample_rate_hz", 1.0)
            # 应用速度倍数
            effective_playback_speed = playback_speed * speed_multiplier
            playback_interval = (1.0 / original_sample_rate) / effective_playback_speed
            
            # 播放开始前归位
            prepare_success, prepare_message = self.prepare_learning_posture()
            if not prepare_success:
                return False, f"播放前归位失败: {prepare_message}", {}
            
            # 播放开始提示音
            self.alert_beep(frequency=800, duration=0.3)
            time.sleep(0.5)
            
            # 播放动作序列
            for i, action in enumerate(action_list):
                angles = action.get("angles", [])
                if not angles:
                    continue
                
                # 设置舵机角度
                success, message = self.action_learning_manager.set_servo_angles(angles)
                if not success:
                    return False, f"设置舵机角度失败: {message}", {}
                
                # 等待播放间隔
                if i < len(action_list) - 1:
                    time.sleep(playback_interval)
            
            # 播放完成提示音
            self.alert_beep(frequency=1000, duration=0.5)
            
            # 播放结束后归位
            time.sleep(1.0)  # 等待一秒再归位
            final_prepare_success, final_prepare_message = self.prepare_learning_posture()
            if not final_prepare_success:
                return False, f"播放后归位失败: {final_prepare_message}", {}
            
            return True, f"连续动作序列播放完成，共播放{len(action_list)}个动作点{'（' + str(speed_multiplier) + '倍速）' if speed_multiplier != 1.0 else ''}", {
                "total_actions": len(action_list),
                "playback_speed": effective_playback_speed,
                "duration_seconds": len(action_list) * playback_interval
            }
            
        except Exception as e:
            return False, f"播放连续动作序列失败: {str(e)}", {}

    # ==================== KCF追踪接口 KCF Tracking Interface ====================
    
    @ensure_response_format
    def set_kcf_target(self, x1: int, y1: int, x2: int, y2: int, timeout: int = 300, kill_on_lost: bool = True) -> tuple:
        """
        设置并启动KCF追踪目标区域
        Set and start KCF tracking target area
        
        Args:
            x1 (int): 目标区域左上角x坐标 Target area top-left x coordinate
            y1 (int): 目标区域左上角y坐标 Target area top-left y coordinate  
            x2 (int): 目标区域右下角x坐标 Target area bottom-right x coordinate
            y2 (int): 目标区域右下角y坐标 Target area bottom-right y coordinate
            timeout (int): 命令执行超时时间(秒) Command execution timeout (seconds), default 300
            kill_on_lost (bool): 目标丢失时是否自动关闭节点 Auto close node when target lost, default True
            
        Returns:
            tuple: (success, message, data)
        """
        try:
            # 1. 启动KCF节点 launch 文件 / Start KCF launch file
            # 模拟打开终端运行命令 / Simulate opening terminal and running command
            # 添加 kill_on_lost 参数
            launch_cmd = f"ros2 launch yahboomcar_kcf_tracker kcf_tracker_launch.py kill_on_lost:={str(kill_on_lost)}"
            
            # 如果之前没有启动或者进程已死，则启动
            if self.kcf_launch_process is None or self.kcf_launch_process.poll() is not None:
                if self.debug:
                    print(f"Starting KCF launch file: {launch_cmd}")
                
                # 清理可能的残留
                if self.kcf_launch_process:
                    self.stop_kcf_tracking()

                self.kcf_launch_process = subprocess.Popen(
                    launch_cmd,
                    shell=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                    text=True,
                    start_new_session=True
                )
                
                # 等待节点启动 / Wait for node to start
                if self.debug:
                    print("Waiting 5s for KCF node to start...")
                time.sleep(5.0)
                
                # 检查 launch 进程是否存活 / Check if launch process is alive
                if self.kcf_launch_process.poll() is not None:
                    _, stderr = self.kcf_launch_process.communicate()
                    self.stop_kcf_tracking()
                    return False, f"KCF节点启动失败: {stderr}", {}

            # 确保坐标为整数
            x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
            
            # 计算宽高用于返回信息（可选）
            width = x2 - x1
            height = y2 - y1
            
            # 构建ROS2命令发布初始化矩形
            # 话题: /kcf_tracker/init_rect
            # 类型: std_msgs/msg/Int32MultiArray
            # 数据: [x1, y1, x2, y2]
            cmd = f'ros2 topic pub --once /kcf_tracker/init_rect std_msgs/msg/Int32MultiArray "{{data: [{x1}, {y1}, {x2}, {y2}]}}"'
            
            if self.debug:
                print(f"[DEBUG] Executing KCF init command: {cmd}")
            
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
            
            if result.returncode == 0:
                return True, f"KCF追踪初始化成功: 区域[{x1}, {y1}, {x2}, {y2}]", {
                    "target_bbox": {"x1": x1, "y1": y1, "x2": x2, "y2": y2, "width": width, "height": height},
                    "init_rect": [x1, y1, x2, y2]
                }
            else:
                return False, f"初始化KCF追踪失败: {result.stderr}", {}
                
        except subprocess.TimeoutExpired:
            return False, "设置KCF追踪目标超时", {}
        except Exception as e:
            return False, f"设置KCF追踪目标异常: {str(e)}", {}

    @ensure_response_format
    def start_kcf_tracking(self) -> tuple:
        """
        启动KCF追踪
        Start KCF tracking
        
        Note: 在新版本中，set_kcf_target 会自动启动追踪。此函数主要用于检查状态。
        In the new version, set_kcf_target automatically starts tracking. This function is mainly for checking status.
        
        Returns:
            tuple: (success, message, data)
        """
        return self.get_kcf_status()

    @ensure_response_format
    def stop_kcf_tracking(self) -> tuple:
        """
        停止KCF追踪
        Stop KCF tracking
        
        Returns:
            tuple: (success, message, data)
        """
        try:
            # 构建ROS2命令停止追踪
            # 话题: /kcf_tracker/command
            # 类型: std_msgs/msg/String
            # 数据: 'stop'
            cmd = 'ros2 topic pub --once /kcf_tracker/command std_msgs/msg/String "{data: \'stop\'}"'
            
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
            
            # 终止KCF节点 launch 进程 / Terminate KCF launch process
            if self.kcf_launch_process:
                try:
                    if self.kcf_launch_process.poll() is None:
                        if self.debug:
                            print("Terminating KCF launch process...")
                        
                        # Windows: Use taskkill to kill process tree
                        if os.name == 'nt':
                            subprocess.call(['taskkill', '/F', '/T', '/PID', str(self.kcf_launch_process.pid)],
                                          stdout=subprocess.DEVNULL,
                                          stderr=subprocess.DEVNULL)
                        else:
                            # Linux/Unix: Kill process group
                            try:
                                os.killpg(os.getpgid(self.kcf_launch_process.pid), signal.SIGTERM)
                                try:
                                    self.kcf_launch_process.wait(timeout=2)
                                except subprocess.TimeoutExpired:
                                    os.killpg(os.getpgid(self.kcf_launch_process.pid), signal.SIGKILL)
                                    self.kcf_launch_process.wait(timeout=1)
                            except Exception as e:
                                if self.debug:
                                    print(f"Error killing KCF process group: {e}")
                                self.kcf_launch_process.terminate()
    
                        try:
                            self.kcf_launch_process.wait(timeout=1)
                        except subprocess.TimeoutExpired:
                            pass
                            
                    self.kcf_launch_process = None
                except Exception as e:
                    print(f"Error stopping KCF launch process: {e}")

            if result.returncode == 0:
                return True, "KCF追踪已停止", {"command": "stop"}
            else:
                return False, f"停止KCF追踪失败: {result.stderr}", {}
                
        except subprocess.TimeoutExpired:
            return False, "停止KCF追踪超时", {}
        except Exception as e:
            return False, f"停止KCF追踪异常: {str(e)}", {}

    @ensure_response_format
    def reset_kcf_tracker(self) -> tuple:
        """
        重置KCF追踪器
        Reset KCF tracker
        
        Returns:
            tuple: (success, message, data)
        """
        try:
            # 构建ROS2命令重置追踪器
            # 话题: /kcf_tracker/command
            # 类型: std_msgs/msg/String
            # 数据: 'reset'
            cmd = 'ros2 topic pub --once /kcf_tracker/command std_msgs/msg/String "{data: \'reset\'}"'
            
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                return True, "KCF追踪器已重置", {"command": "reset"}
            else:
                return False, f"重置KCF追踪器失败: {result.stderr}", {}
                
        except subprocess.TimeoutExpired:
            return False, "重置KCF追踪器超时", {}
        except Exception as e:
            return False, f"重置KCF追踪器异常: {str(e)}", {}

    @ensure_response_format
    def get_kcf_status(self) -> tuple:
        """
        获取KCF追踪状态
        Get KCF tracking status
        
        Returns:
            tuple: (success, message, data)
        """
        try:
            # 监听 /kcf_tracker/status 话题
            cmd = 'ros2 topic echo /kcf_tracker/status --once --field data'
            
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
            
            if result.returncode == 0:
                status = result.stdout.strip()
                return True, f"KCF状态: {status}", {"status": status}
            else:
                return False, "获取KCF状态失败 (可能是话题未发布)", {"error": result.stderr}
                
        except subprocess.TimeoutExpired:
            return False, "获取KCF状态超时", {}
        except Exception as e:
            return False, f"获取KCF状态异常: {str(e)}", {}

    # ==================== Line Following Interface ====================

    @ensure_response_format
    def set_line_follow_hsv(self, hsv_threshold: Union[list, tuple]) -> tuple:
        """
        设置巡线功能的HSV阈值
        Set the HSV threshold for the line following feature

        Args:
            hsv_threshold (Union[list, tuple]): 6个整数的序列, 顺序为 [h_min, s_min, v_min, h_max, s_max, v_max]
                                              Sequence of 6 integers in the order [h_min, s_min, v_min, h_max, s_max, v_max]

        Returns:
            tuple: (success, message, data)
        """
        # 参数校验
        if not isinstance(hsv_threshold, (list, tuple)) or len(hsv_threshold) != 6:
            return False, "参数错误: hsv_threshold 必须是一个包含6个整数的列表或元组", {}

        if not all(isinstance(i, int) for i in hsv_threshold):
            return False, "参数错误: hsv_threshold 序列中的所有元素都必须是整数", {}

        try:
            # 构建ROS2命令字符串
            hsv_str = ', '.join(map(str, hsv_threshold))
            cmd = f'ros2 topic pub /linefollow/set_hsv std_msgs/msg/Int32MultiArray "{{data: [{hsv_str}]}}" --once'

            if self.debug:
                print(f"Executing command: {cmd}")

            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)

            if result.returncode == 0:
                return True, f"巡线HSV阈值设置成功: {list(hsv_threshold)}", {
                    "hsv_threshold": list(hsv_threshold)
                }
            else:
                return False, f"设置巡线HSV阈值失败: {result.stderr}", {}

        except subprocess.TimeoutExpired:
            return False, "设置巡线HSV阈值超时", {}
        except Exception as e:
            return False, f"设置巡线HSV阈值时发生异常: {str(e)}", {}

    @ensure_response_format
    def direct_line_follow(self, hsv_threshold: Union[str, list, tuple], timeout_s: Optional[float] = None) -> tuple:
        """
        巡线自动驾驶（接受颜色名或HSV阈值，映射后下发并启动一次跟踪）
        Line following autonomous drive (accept color name or HSV range, map and publish to trigger one-time direct tracking)

        Args:
            hsv_threshold (Union[str, list, tuple]):
                - 字符串：如 "yellow"、"黄色"、"red"、"红色" 等，将映射为预设HSV阈值
                - 列表/元组：6个整数的序列 [h_min, s_min, v_min, h_max, s_max, v_max]
                String or HSV sequence. If string (e.g., "yellow", "red", "蓝色"), it will be mapped to preset HSV range; 
                If list/tuple, it must be 6 integers [h_min, s_min, v_min, h_max, s_max, v_max].

        Returns:
            tuple: (success, message, data)
        """
        # 统一得到最终的HSV阈值
        final_hsv = None

        # 情况1：字符串颜色名，映射预设HSV
        if isinstance(hsv_threshold, str):
            color_key = hsv_threshold.strip().lower()
            # 颜色映射表（OpenCV HSV：H[0,180], S[0,255], V[0,255]），可按需调整
            color_map = {
                # Yellow / 黄色
                'yellow': [20, 100, 100, 40, 255, 255],
                '黄色': [20, 100, 100, 40, 255, 255],
                '黄': [20, 100, 100, 40, 255, 255],
                # Red / 红色（注意红色在HSV上可能需要两段范围，这里使用低段）
                'red': [0, 120, 70, 10, 255, 255],
                '红色': [0, 120, 70, 10, 255, 255],
                '红': [0, 120, 70, 10, 255, 255],
                # Orange / 橙色
                'orange': [10, 100, 100, 20, 255, 255],
                '橙色': [10, 100, 100, 20, 255, 255],
                '橙': [10, 100, 100, 20, 255, 255],
                # Green / 绿色
                'green': [40, 100, 100, 85, 255, 255],
                '绿色': [40, 100, 100, 85, 255, 255],
                '绿': [40, 100, 100, 85, 255, 255],
                # Blue / 蓝色
                'blue': [90, 100, 100, 130, 255, 255],
                '蓝色': [90, 100, 100, 130, 255, 255],
                '蓝': [90, 100, 100, 130, 255, 255],
                # Purple / 紫色
                'purple': [130, 100, 100, 160, 255, 255],
                '紫色': [130, 100, 100, 160, 255, 255],
                '紫': [130, 100, 100, 160, 255, 255],
                # White / 白色（低饱和度高亮度）
                'white': [0, 0, 200, 180, 30, 255],
                '白色': [0, 0, 200, 180, 30, 255],
                '白': [0, 0, 200, 180, 30, 255],
                # Black / 黑色（低亮度）
                'black': [0, 0, 0, 180, 255, 50],
                '黑色': [0, 0, 0, 180, 255, 50],
                '黑': [0, 0, 0, 180, 255, 50],
                # Cyan / 青色（可选）
                'cyan': [85, 100, 100, 100, 255, 255],
                '青色': [85, 100, 100, 100, 255, 255],
                '青': [85, 100, 100, 100, 255, 255],
            }

            # 兼容大小写英文
            final_hsv = color_map.get(color_key)
            # 如果是中文输入，lower()不会影响，已在字典中包含中文键
            if final_hsv is None:
                return False, (
                    "未知颜色名称: {}。支持的颜色: {}".format(
                        hsv_threshold,
                        ', '.join(sorted(set(['yellow','red','orange','green','blue','purple','white','black','cyan','黄色','红色','橙色','绿色','蓝色','紫色','白色','黑色','青色'])))
                    )
                ), {}

        # 情况2：直接传入HSV数组/元组
        elif isinstance(hsv_threshold, (list, tuple)):
            if len(hsv_threshold) != 6:
                return False, "参数错误: HSV阈值必须是长度为6的序列 [h_min, s_min, v_min, h_max, s_max, v_max]", {}
            if not all(isinstance(i, int) for i in hsv_threshold):
                return False, "参数错误: HSV阈值序列中的所有元素都必须是整数", {}
            final_hsv = list(hsv_threshold)
        else:
            return False, "参数类型错误: 仅支持字符串颜色名或长度为6的HSV序列", {}

        try:
            # 1. 启动巡线节点 launch 文件 / Start line follow launch file
            # 模拟打开终端运行命令 / Simulate opening terminal and running command
            launch_cmd = "ros2 launch yahboomcar_linefollow follow_line_launch.py"
            if self.debug:
                print(f"Starting launch file: {launch_cmd}")
            
            # 如果之前有遗留的进程，先清理
            if self.line_follow_launch_process and self.line_follow_launch_process.poll() is None:
                self.stop_line_follow()

            self.line_follow_launch_process = subprocess.Popen(
                launch_cmd,
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
                start_new_session=True
            )
            
            # 等待节点启动 / Wait for node to start
            if self.debug:
                print("Waiting 5s for line follow node to start...")
            time.sleep(5.0)
            
            # 检查 launch 进程是否存活 / Check if launch process is alive
            if self.line_follow_launch_process.poll() is not None:
                _, stderr = self.line_follow_launch_process.communicate()
                self.stop_line_follow()
                return False, f"巡线节点启动失败: {stderr}", {}

            # 2. 构建ROS2服务调用命令字符串（等待服务执行完成再返回）
            hsv_str = ', '.join(map(str, final_hsv))
            cmd = (
                'ros2 service call /linefollow/start_direct_track '
                'yahboomcar_linefollow/srv/StartDirectTrack '
                f'"{{hsv: [{hsv_str}]}}"'
            )

            if self.debug:
                print(f"Executing command: {cmd}")

            # timeout_s 为 None 时表示不限时等待服务返回（由服务端控制巡线过程与结束）
            try:
                if self.line_follow_process and self.line_follow_process.poll() is None:
                     self.stop_line_follow()

                # 使用 Popen 启动进程
                self.line_follow_process = subprocess.Popen(
                    cmd, 
                    shell=True, 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE, 
                    text=True
                )
                
                # 循环等待进程结束，支持中途打断
                start_time = time.time()
                while self.line_follow_process and self.line_follow_process.poll() is None:
                    # 1. 检查是否被外部置空（stop_line_follow 被调用）
                    # 注意：如果外部调用了stop_line_follow，self.line_follow_process会被置为None
                    if self.line_follow_process is None:
                        return False, "巡线任务已被强制中断", {}

                    # 2. 检查超时
                    if timeout_s is not None and (time.time() - start_time > timeout_s):
                        self.stop_line_follow()
                        return False, "巡线服务调用超时", {}
                    
                    # 3. 检查全局取消事件 (如果 robot_controller 有)
                    if hasattr(self.robot_controller, 'cancel_event') and \
                       self.robot_controller.cancel_event.is_set():
                        self.stop_line_follow()
                        return False, "巡线任务因全局取消而中断", {}

                    time.sleep(0.1)

                # 检查进程对象是否存在（防止被stop_line_follow置空后访问报错）
                if self.line_follow_process is None:
                    return False, "巡线任务已被强制中断", {}

                # 进程已结束，获取输出
                # 注意：如果进程被 kill，communicate 可能报错或返回空，需处理
                try:
                    stdout, stderr = self.line_follow_process.communicate(timeout=1)
                except Exception:
                    stdout, stderr = "", ""

                returncode = self.line_follow_process.returncode
                self.line_follow_process = None # Process finished
                
                # 无论成功失败，服务调用结束后都要清理环境（包括关闭 launch 进程）
                # Clean up environment (including closing launch process) after service call finishes
                self.stop_line_follow()

                if returncode == 0:
                    return True, f"巡线服务已执行完成，HSV: {list(final_hsv)}", {
                        "hsv_threshold": list(final_hsv),
                        "service": "/linefollow/start_direct_track",
                        "service_type": "yahboomcar_linefollow/srv/StartDirectTrack",
                        "stdout": stdout.strip() if stdout else ""
                    }
                else:
                    # 如果是被 kill 的 (通常 returncode != 0)，且是因为中断，这里会返回失败
                    # 但如果是我们主动 stop_line_follow 导致的，可能希望仅仅是"结束"而不是报错？
                    # 按照逻辑，被中断就是 False
                    return False, f"巡线服务调用异常结束 (Code: {returncode}): {stderr}", {
                        "service": "/linefollow/start_direct_track",
                        "service_type": "yahboomcar_linefollow/srv/StartDirectTrack",
                        "stdout": stdout.strip() if stdout else ""
                    }

            except Exception as e:
                self.stop_line_follow()
                return False, f"巡线服务调用异常: {str(e)}", {}
        except Exception as e:
            self.stop_line_follow()
            return False, f"巡线服务调用异常: {str(e)}", {}

    def stop_line_follow(self):
        """停止巡线任务 Stop line following task"""
        # 1. 物理停止：发送速度为0的指令，确保机器人立即停止移动
        try:
            subprocess.run(
                'ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist "{linear: {x: 0.0, y: 0.0, z: 0.0}, angular: {x: 0.0, y: 0.0, z: 0.0}}"',
                shell=True,
                stdout=subprocess.DEVNULL, 
                stderr=subprocess.DEVNULL,
                timeout=1
            )
        except Exception:
            pass

        # 2. 进程终止：停止巡线服务调用进程
        if self.line_follow_process:
            try:
                if self.line_follow_process.poll() is None:
                    if self.debug:
                        print("Terminating line follow process...")
                    self.line_follow_process.terminate()
                    try:
                        self.line_follow_process.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        if self.debug:
                            print("Force killing line follow process...")
                        self.line_follow_process.kill()
                        self.line_follow_process.wait(timeout=1)
                self.line_follow_process = None
            except Exception as e:
                print(f"Error stopping line follow process: {e}")

        # 3. 终止巡线节点 launch 进程 / Terminate line follow launch process
        if self.line_follow_launch_process:
            try:
                if self.line_follow_launch_process.poll() is None:
                    if self.debug:
                        print("Terminating line follow launch process...")
                    
                    # Windows: Use taskkill to kill process tree
                    if os.name == 'nt':
                        subprocess.call(['taskkill', '/F', '/T', '/PID', str(self.line_follow_launch_process.pid)],
                                      stdout=subprocess.DEVNULL,
                                      stderr=subprocess.DEVNULL)
                    else:
                        # Linux/Unix: Kill process group to ensure all child processes (like ros2 launch nodes) are killed
                        try:
                            os.killpg(os.getpgid(self.line_follow_launch_process.pid), signal.SIGTERM)
                            try:
                                self.line_follow_launch_process.wait(timeout=2)
                            except subprocess.TimeoutExpired:
                                os.killpg(os.getpgid(self.line_follow_launch_process.pid), signal.SIGKILL)
                                self.line_follow_launch_process.wait(timeout=1)
                        except Exception as e:
                            if self.debug:
                                print(f"Error killing process group: {e}")
                            # Fallback to standard terminate if killpg fails
                            self.line_follow_launch_process.terminate()

                    try:
                        self.line_follow_launch_process.wait(timeout=1)
                    except subprocess.TimeoutExpired:
                        pass
                        
                self.line_follow_launch_process = None
            except Exception as e:
                print(f"Error stopping line follow launch process: {e}")

        return True, "巡线任务已停止"

def main():
    """命令行入口点 Command line entry point"""
    print("🤖 Muto Hexapod Robot Controller")
    print("Version: 1.0.0")
    print("Author: YAHBOOM | Gentle Xu")
    print("Description: Six-legged robot control interface")
    print("\nInitializing robot controller...")
    
    try:
        # 创建机器人控制器实例
        controller = MutoController(debug=True)
        print("✅ Robot controller initialized successfully")
        
        # 打印系统信息
        success, info = controller.print_system_info()
        if success:
            print("\n📊 System Information:")
            print(info)
        
        # 获取状态信息
        success, status = controller.get_status()
        if success:
            print("\n🔍 Robot Status:")
            print(status)
            
        print("\n✨ Robot controller is ready for use!")
        print("You can now import and use MutoController in your Python scripts.")
        
    except Exception as e:
        print(f"❌ Failed to initialize robot controller: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
