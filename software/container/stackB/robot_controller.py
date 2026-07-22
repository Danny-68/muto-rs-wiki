#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
机器人控制模块
Robot Controller Module

包含基础移动控制和预设动作功能
Contains basic movement control and preset action functions
"""

import time
import random
import threading
from typing import Optional, Dict, Any


class RobotController:
    """
    机器人控制器
    Robot Controller
    
    负责机器人的基础移动控制和预设动作
    Responsible for basic robot movement control and preset actions
    """
    
    def __init__(self, muto_instance, default_config=None, step_distance_cm=None, speed_calibration=None, angular_speed_calibration=None):
        """
        初始化机器人控制器
        Initialize robot controller
        
        Args:
            muto_instance: 机器人实例 Robot instance
            default_config: 默认配置 Default configuration
            step_distance_cm: 步距(厘米) Step distance in cm
            speed_calibration: 速度标定数据 Speed calibration data
            angular_speed_calibration: 角速度标定数据 Angular speed calibration data
        """
        self.robot = muto_instance
        self.default_config = default_config or {}
        self.step_distance_cm = step_distance_cm or 10.0
        self.speed_calibration = speed_calibration or {}
        self.angular_speed_calibration = angular_speed_calibration or {}
        
        # 全局取消事件：用于在耗时循环中立即打断动作
        # Global cancel event: allows immediate interruption of long-running loops
        self.cancel_event = threading.Event()

        # 持续动作状态管理
        self.continuous_actions = {}  # 存储持续动作的状态
        self.action_threads = {}      # 存储动作线程
        self.action_locks = {}        # 存储动作锁

    def request_cancel(self) -> None:
        """
        请求打断当前正在执行的动作（例如移动循环）。
        Request to interrupt current executing actions (e.g., movement loops).
        """
        try:
            self.cancel_event.set()
        except Exception:
            # 保底：即使设置失败也不抛出影响主流程
            pass

    def clear_cancel(self) -> None:
        """
        清除打断状态，允许后续动作继续。
        Clear interruption state to allow subsequent actions to proceed.
        """
        try:
            self.cancel_event.clear()
        except Exception:
            pass
    
    def _resolve_movement_parameters(self, steps: Optional[int] = None, 
                                   distance_m: Optional[float] = None,
                                   time_s: Optional[float] = None,
                                   speed_ms: Optional[float] = None) -> tuple:
        """
        解析移动参数，处理优先级和默认值
        Resolve movement parameters, handle priorities and defaults
        
        参数优先级 Parameter priority:
        1. steps (步数优先) Steps have highest priority
        2. distance_m (距离次之) Distance second
        3. time_s + speed_ms (时间和速度组合) Time and speed combination
        4. 默认值 Default values
        
        Args:
            steps: 步数 Number of steps
            distance_m: 距离(米) Distance in meters
            time_s: 时间(秒) Time in seconds
            speed_ms: 速度(米/秒) Speed in m/s
            
        Returns:
            tuple: (success: bool, message: str, data: dict)
                success: 解析是否成功 Whether resolution was successful
                message: 解析结果消息 Resolution result message
                data: 解析后的参数 Resolved parameters
        
        Examples:
            success, msg, params = robot._resolve_movement_parameters(steps=5)
            success, msg, params = robot._resolve_movement_parameters(distance_m=1.0, speed_ms=0.5)
        """
        try:
            result = {
                'steps': None,
                'time_s': None,
                'step_interval_s': self.default_config['step_interval_s'],
                'total_time_s': None
            }
            
            # 优先级1: 步数 Priority 1: Steps
            if steps is not None:
                if steps <= 0:
                    return False, "步数必须大于0 Steps must be greater than 0", None
                result['steps'] = steps
                if speed_ms is not None:
                    # 计算步间隔
                    success, msg, step_interval = self._calculate_step_interval_from_speed(speed_ms)
                    if not success:
                        return False, f"计算步间隔失败: {msg}", None
                    result['step_interval_s'] = step_interval
                if time_s is not None:
                    result['step_interval_s'] = time_s / steps
                result['total_time_s'] = result['steps'] * result['step_interval_s']
                return True, "参数解析成功(步数优先) Parameters resolved successfully (steps priority)", result
            
            # 优先级2: 距离 Priority 2: Distance
            if distance_m is not None:
                if distance_m <= 0:
                    return False, "距离必须大于0 Distance must be greater than 0", None
                
                # 计算步数
                success, msg, steps = self._calculate_steps_from_distance(distance_m)
                if not success:
                    return False, f"计算步数失败: {msg}", None
                result['steps'] = steps
                
                if speed_ms is not None:
                    # 计算步间隔
                    success, msg, step_interval = self._calculate_step_interval_from_speed(speed_ms)
                    if not success:
                        return False, f"计算步间隔失败: {msg}", None
                    result['step_interval_s'] = step_interval
                    result['total_time_s'] = distance_m / speed_ms
                elif time_s is not None:
                    result['step_interval_s'] = time_s / result['steps']
                    result['total_time_s'] = time_s
                else:
                    result['total_time_s'] = result['steps'] * result['step_interval_s']
                return True, "参数解析成功(距离优先) Parameters resolved successfully (distance priority)", result
            
            # 优先级3: 时间和速度组合 Priority 3: Time and speed combination
            if time_s is not None and speed_ms is not None:
                if time_s <= 0 or speed_ms <= 0:
                    return False, "时间和速度必须大于0 Time and speed must be greater than 0", None
                distance_calculated = speed_ms * time_s
                success, msg, steps = self._calculate_steps_from_distance(distance_calculated)
                if not success:
                    return False, f"计算步数失败: {msg}", None
                result['steps'] = steps
                success, msg, step_interval = self._calculate_step_interval_from_speed(speed_ms)
                if not success:
                    return False, f"计算步间隔失败: {msg}", None
                result['step_interval_s'] = step_interval
                result['total_time_s'] = time_s
                return True, "参数解析成功(时间速度组合) Parameters resolved successfully (time-speed combination)", result
            
            # 优先级4: 仅时间 Priority 4: Time only
            if time_s is not None:
                if time_s <= 0:
                    return False, "时间必须大于0 Time must be greater than 0", None
                speed_default = self.default_config['default_speed_ms']
                distance_calculated = speed_default * time_s
                success, msg, steps = self._calculate_steps_from_distance(distance_calculated)
                if not success:
                    return False, f"计算步数失败: {msg}", None
                result['steps'] = steps
                success, msg, step_interval = self._calculate_step_interval_from_speed(speed_default)
                if not success:
                    return False, f"计算步间隔失败: {msg}", None
                result['step_interval_s'] = step_interval
                result['total_time_s'] = time_s
                return True, "参数解析成功(仅时间) Parameters resolved successfully (time only)", result
            
            # 优先级5: 仅速度 Priority 5: Speed only
            if speed_ms is not None:
                if speed_ms <= 0:
                    return False, "速度必须大于0 Speed must be greater than 0", None
                time_default = self.default_config['default_time_s']
                distance_calculated = speed_ms * time_default
                success, msg, steps = self._calculate_steps_from_distance(distance_calculated)
                if not success:
                    return False, f"计算步数失败: {msg}", None
                result['steps'] = steps
                success, msg, step_interval = self._calculate_step_interval_from_speed(speed_ms)
                if not success:
                    return False, f"计算步间隔失败: {msg}", None
                result['step_interval_s'] = step_interval
                result['total_time_s'] = time_default
                return True, "参数解析成功(仅速度) Parameters resolved successfully (speed only)", result
            
            # 默认情况: 随机时间 Default case: Random time
            random_time = random.uniform(*self.default_config['random_time_range'])
            default_speed = self.default_config['default_speed_ms']
            distance_calculated = default_speed * random_time
            success, msg, steps = self._calculate_steps_from_distance(distance_calculated)
            if not success:
                return False, f"计算步数失败: {msg}", None
            result['steps'] = steps
            success, msg, step_interval = self._calculate_step_interval_from_speed(default_speed)
            if not success:
                return False, f"计算步间隔失败: {msg}", None
            result['step_interval_s'] = step_interval
            result['total_time_s'] = random_time
            
            return True, "参数解析成功(默认随机) Parameters resolved successfully (default random)", result
            
        except Exception as e:
            return False, f"参数解析失败 Parameter resolution failed: {str(e)}", None
    
    def _calculate_steps_from_distance(self, distance_m: float) -> tuple:
        """
        根据距离计算步数
        Calculate steps from distance
        
        Args:
            distance_m: 距离(米) Distance in meters
            
        Returns:
            tuple: (success: bool, message: str, steps: int)
        """
        try:
            distance_cm = distance_m * 100
            steps = max(1, int(distance_cm / self.step_distance_cm))
            return True, "步数计算成功 Steps calculated successfully", steps
        except Exception as e:
            return False, f"步数计算失败 Steps calculation failed: {str(e)}", None
    
    def _calculate_step_interval_from_speed(self, speed_ms: float) -> tuple:
        """
        根据速度计算步间隔
        Calculate step interval from speed
        
        Args:
            speed_ms: 速度(米/秒) Speed in m/s
            
        Returns:
            tuple: (success: bool, message: str, step_interval: float)
        """
        try:
            if speed_ms <= 0:
                return False, "速度必须大于0 Speed must be greater than 0", None
            step_distance_m = self.step_distance_cm / 100
            step_interval = step_distance_m / speed_ms
            step_interval = max(0.1, step_interval)  # 最小间隔0.1秒
            return True, "步间隔计算成功 Step interval calculated successfully", step_interval
        except Exception as e:
            return False, f"步间隔计算失败 Step interval calculation failed: {str(e)}", None
    
    def _select_optimal_speed_level(self, target_speed_ms: float) -> tuple:
        """
        选择最优速度档位
        Select optimal speed level
        
        Args:
            target_speed_ms: 目标速度(米/秒) Target speed in m/s
            
        Returns:
            tuple: (success: bool, message: str, data: dict)
        """
        try:
            if not self.speed_calibration:
                return False, "速度标定数据为空", None
            
            best_level = None
            min_diff = float('inf')
            
            for level, speed in self.speed_calibration.items():
                diff = abs(speed - target_speed_ms)
                if diff < min_diff:
                    min_diff = diff
                    best_level = level
            
            if best_level is None:
                return False, "未找到合适的速度档位", None
            
            return True, "速度档位选择成功", {
                'level': best_level,
                'speed': self.speed_calibration[best_level],
                'target_speed': target_speed_ms,
                'difference': min_diff
            }
        except Exception as e:
            return False, f"速度档位选择失败: {str(e)}", None
    
    def _select_optimal_angular_speed_level(self, target_angular_speed_deg_s: float) -> tuple:
        """
        根据目标角速度选择最优的角速度档位
        Select optimal angular speed level based on target angular speed
        
        Args:
            target_angular_speed_deg_s: 目标角速度(度/秒) Target angular speed in deg/s
            
        Returns:
            tuple: (success: bool, message: str, data: dict)
                success: 选择是否成功 Whether selection was successful
                message: 选择结果消息 Selection result message
                data: 选择的档位数据 Selected level data
        """
        try:
            if not hasattr(self, 'angular_speed_calibration') or not self.angular_speed_calibration:
                return False, "角速度标定数据未加载 Angular speed calibration data not loaded", None
            
            # 找到最接近目标角速度的档位
            best_level = None
            min_diff = float('inf')
            
            for level, angular_speed in self.angular_speed_calibration.items():
                diff = abs(angular_speed - target_angular_speed_deg_s)
                if diff < min_diff:
                    min_diff = diff
                    best_level = level
            
            if best_level is None:
                return False, "未找到合适的角速度档位 No suitable angular speed level found", None
            
            # 确保档位在有效范围内 (10-20)
            if best_level < 10:
                best_level = 10
            elif best_level > 20:
                best_level = 20
            
            print(f"[DEBUG] 选择角速度档位 {best_level} (目标: {target_angular_speed_deg_s:.1f} deg/s, 实际: {self.angular_speed_calibration[best_level]:.1f} deg/s)")
            
            return True, f"选择角速度档位 {best_level} (实际角速度: {self.angular_speed_calibration[best_level]:.1f} deg/s)", {
                'level': best_level,
                'angular_speed': self.angular_speed_calibration[best_level],
                'target_angular_speed': target_angular_speed_deg_s,
                'angular_speed_diff': min_diff
            }
        except Exception as e:
            return False, f"角速度档位选择失败 Angular speed level selection failed: {str(e)}", None
    
    def _execute_movement_with_move(self, direction: str, params: Dict[str, Any], action_name: str, target_speed_ms: Optional[float] = None) -> tuple:
        """
        使用move方法执行移动动作
        Execute movement action using move method
        
        Args:
            direction: 移动方向 Movement direction ('forward', 'backward', 'left', 'right', 'turn_left', 'turn_right')
            params: 解析后的参数 Resolved parameters
            action_name: 动作名称 Action name
            target_speed_ms: 目标速度(米/秒) Target speed in m/s
            
        Returns:
            tuple: (success: bool, message: str, data: dict)
                success: 执行是否成功 Whether execution was successful
                message: 执行结果消息 Execution result message
                data: 执行数据 Execution data
        """
        total_time = params['total_time_s']
        estimated_distance_cm = params.get('steps', 0) * self.step_distance_cm
        
        # 根据动作类型和目标速度选择最优档位
        if direction in ['turn_left', 'turn_right']:
            # 旋转动作：使用角速度标定数据
            if target_speed_ms:  # 这里target_speed_ms实际上是angular_speed_deg_s
                success, msg, angular_data = self._select_optimal_angular_speed_level(target_speed_ms)
                if success:
                    speed_level = angular_data['level']
                    actual_speed = angular_data['angular_speed']
                    print(f"[DEBUG] 旋转使用角速度标定: 档位{speed_level}, 角速度{actual_speed}度/秒")
                else:
                    speed_level = self.default_config.get('robot_angular_speed_level', 10)  # 旋转默认档位
                    actual_speed = self.angular_speed_calibration.get(speed_level, 30.0)
                    print(f"[DEBUG] 旋转使用默认档位: {speed_level}, 角速度{actual_speed}度/秒")
            else:
                # 使用配置文件中的默认角速度档位
                speed_level = self.default_config.get('robot_angular_speed_level', 10)
                actual_speed = self.angular_speed_calibration.get(speed_level, 30.0)
                print(f"[DEBUG] 旋转使用配置默认档位: {speed_level}, 角速度{actual_speed}度/秒")
        else:
            # 直线移动：使用线速度标定数据
            if target_speed_ms:
                # 使用速度标定数据选择最优档位
                success, msg, speed_data = self._select_optimal_speed_level(target_speed_ms)
                if success:
                    speed_level = speed_data['level']
                    actual_speed = speed_data['speed']
                else:
                    speed_level = self.default_config.get('robot_speed_level', 10)  # 使用配置文件中的默认档位
                    actual_speed = self.speed_calibration.get(speed_level, 0.05)
            else:
                # 使用配置文件中的默认速度档位
                speed_level = self.default_config.get('robot_speed_level', 10)
                actual_speed = self.speed_calibration.get(speed_level, 0.05)
        
        # 根据方向设置move参数
        if direction == 'forward':
            x, y, z = speed_level, 0, 0
        elif direction == 'backward':
            x, y, z = -speed_level, 0, 0
        elif direction == 'left':
            x, y, z = 0, speed_level, 0
        elif direction == 'right':
            x, y, z = 0, -speed_level, 0
        elif direction == 'turn_left':
            # 修正：左转使用正值z / Correction: Turn left uses positive z
            x, y, z = 0, 0, speed_level
        elif direction == 'turn_right':
            # 修正：右转使用负值z / Correction: Turn right uses negative z
            x, y, z = 0, 0, -speed_level
        else:
            return False, f"未知的移动方向: {direction}", None
        
        # Yahboom STM32 firmware gait — identiek aan muto_driver_fixed.py
        def _stm32(addr, data=0):
            body = [0x01, addr, data]
            chk = (0xFF - ((0x09 + sum(body)) & 0xFF)) & 0xFF
            return bytes([0x55, 0x00, 0x09] + body + [chk, 0x00, 0xAA])

        STM32_CMD = {
            'forward':   _stm32(0x12, 15),
            'backward':  _stm32(0x13, 15),
            'left':      _stm32(0x14, 15),
            'right':     _stm32(0x15, 15),
            'turn_left': _stm32(0x16, 15),
            'turn_right':_stm32(0x17, 15),
        }
        STM32_STOP = _stm32(0x11, 0x00)

        cmd = STM32_CMD.get(direction)
        if cmd is None:
            return False, f"Onbekende richting: {direction}", None

        start_time = time.time()
        self.robot.ser.write(cmd)

        end_time = start_time + total_time
        canceled = False
        while time.time() < end_time:
            if self.cancel_event.is_set():
                canceled = True
                break
            time.sleep(0.05)

        self.robot.ser.write(STM32_STOP)
        time.sleep(0.1)

        if canceled:
            time.sleep(self.default_config.get('pause_between_actions_s', 0.5))
            return False, f"{action_name}已被取消 {action_name} canceled", {
                'action_name': action_name,
                'direction': direction,
                'speed_level': speed_level,
                'move_params': {'x': x, 'y': y, 'z': z},
                'total_time_s': total_time,
                'actual_time_s': time.time() - start_time,
                'estimated_distance_cm': estimated_distance_cm,
                'target_speed_ms': target_speed_ms,
                'actual_speed_ms': actual_speed,
                'canceled': True
            }
        
        actual_time = time.time() - start_time
        # actual_speed已在上面计算，使用标定数据
        measured_speed = (estimated_distance_cm / 100) / actual_time if actual_time > 0 else 0
        
        # 动作间暂停
        time.sleep(self.default_config.get('pause_between_actions_s', 0.5))
        
        return True, f"{action_name}执行成功 {action_name} executed successfully", {
            'action_name': action_name,
            'direction': direction,
            'speed_level': speed_level,
            'move_params': {'x': x, 'y': y, 'z': z},
            'total_time_s': total_time,
            'actual_time_s': actual_time,
            'estimated_distance_cm': estimated_distance_cm,
            'target_speed_ms': target_speed_ms,
            'actual_speed_ms': actual_speed,
            'measured_speed_ms': measured_speed
        }
    
    def _execute_movement(self, action_func, params: Dict[str, Any], action_name: str, target_speed_ms: Optional[float] = None) -> tuple:
        """
        执行移动动作（保持向后兼容性）
        Execute movement action (backward compatibility)
        
        Args:
            action_func: 动作函数 Action function
            params: 解析后的参数 Resolved parameters
            action_name: 动作名称 Action name
            target_speed_ms: 目标速度(米/秒) Target speed in m/s
            
        Returns:
            tuple: (success: bool, message: str, data: dict)
                success: 执行是否成功 Whether execution was successful
                message: 执行结果消息 Execution result message
                data: 执行数据 Execution data
        """
        # 根据动作函数确定方向
        direction_map = {
            self.robot.forward: 'forward',
            self.robot.back: 'backward', 
            self.robot.left: 'left',
            self.robot.right: 'right',
            self.robot.turnleft: 'turn_left',
            self.robot.turnright: 'turn_right'
        }
        
        direction = direction_map.get(action_func, 'unknown')
        if direction == 'unknown':
            return False, f"未知的动作函数: {action_func}", None
        
        # 使用新的move方法执行
        return self._execute_movement_with_move(direction, params, action_name, target_speed_ms)
    
    # ==================== 基础移动动作 Basic Movement Actions ====================
    
    def forward(self, steps: Optional[int] = None, distance_m: Optional[float] = None,
                time_s: Optional[float] = None, speed_ms: Optional[float] = None) -> tuple:
        """
        前进动作
        Forward movement
        
        Args:
            steps: 步数 Number of steps (highest priority)
            distance_m: 距离(米) Distance in meters
            time_s: 时间(秒) Time in seconds
            speed_ms: 速度(米/秒) Speed in m/s
        
        Returns:
            tuple: (success: bool, message: str, data: dict)
                success: 执行是否成功 Whether execution was successful
                message: 执行结果消息 Execution result message
                data: 执行数据(包含步数、时间等信息) Execution data (steps, time, etc.)
        
        Examples:
            success, msg, data = robot.forward()                    # 默认随机前进
            success, msg, data = robot.forward(steps=3)             # 前进3步
            success, msg, data = robot.forward(distance_m=1.0)      # 前进1米
            success, msg, data = robot.forward(time_s=5)            # 前进5秒
            success, msg, data = robot.forward(speed_ms=0.5, time_s=3)  # 以0.5m/s速度前进3秒
            success, msg, data = robot.forward(speed_ms=0.3, distance_m=2)  # 以0.3m/s速度前进2米
        """
        try:
            # 解析移动参数
            success, msg, params = self._resolve_movement_parameters(steps, distance_m, time_s, speed_ms)
            if not success:
                return False, f"前进动作参数解析失败 Forward movement parameter resolution failed: {msg}", None
            
            # 执行移动动作
            success, msg, execution_data = self._execute_movement_with_move('forward', params, "前进 Forward", speed_ms)
            if not success:
                return False, f"前进动作执行失败 Forward movement execution failed: {msg}", None
            
            return True, "前进动作执行成功 Forward movement executed successfully", execution_data
        except Exception as e:
            return False, f"前进动作执行失败 Forward movement failed: {str(e)}", None
    
    def backward(self, steps: Optional[int] = None, distance_m: Optional[float] = None,
                 time_s: Optional[float] = None, speed_ms: Optional[float] = None) -> tuple:
        """
        后退动作
        Backward movement
        
        Args:
            steps: 步数 Number of steps (highest priority)
            distance_m: 距离(米) Distance in meters
            time_s: 时间(秒) Time in seconds
            speed_ms: 速度(米/秒) Speed in m/s
        
        Returns:
            tuple: (success: bool, message: str, data: dict)
                success: 执行是否成功 Whether execution was successful
                message: 执行结果消息 Execution result message
                data: 执行数据(包含步数、时间等信息) Execution data (steps, time, etc.)
        
        Examples:
            success, msg, data = robot.backward()                   # 默认随机后退
            success, msg, data = robot.backward(distance_m=1.0)     # 后退1米
            success, msg, data = robot.backward(time_s=5)           # 后退5秒
            success, msg, data = robot.backward(speed_ms=0.2, time_s=5)  # 以0.2m/s速度后退5秒
        """
        try:
            # 解析移动参数
            success, msg, params = self._resolve_movement_parameters(steps, distance_m, time_s, speed_ms)
            if not success:
                return False, f"后退动作参数解析失败 Backward movement parameter resolution failed: {msg}", None
            
            # 执行移动动作
            success, msg, execution_data = self._execute_movement_with_move('backward', params, "后退 Backward", speed_ms)
            if not success:
                return False, f"后退动作执行失败 Backward movement execution failed: {msg}", None
            
            return True, "后退动作执行成功 Backward movement executed successfully", execution_data
        except Exception as e:
            return False, f"后退动作执行失败 Backward movement failed: {str(e)}", None
    
    def shift_left(self, steps: Optional[int] = None, distance_m: Optional[float] = None,
                   time_s: Optional[float] = None, speed_ms: Optional[float] = None) -> tuple:
        """
        左平移动作
        Left shift movement
        
        Args:
            steps: 步数 Number of steps (highest priority)
            distance_m: 距离(米) Distance in meters
            time_s: 时间(秒) Time in seconds
            speed_ms: 速度(米/秒) Speed in m/s
        
        Returns:
            tuple: (success: bool, message: str, data: dict)
                success: 执行是否成功 Whether execution was successful
                message: 执行结果消息 Execution result message
                data: 执行数据(包含步数、时间等信息) Execution data (steps, time, etc.)
        
        Examples:
            success, msg, data = robot.shift_left()                 # 默认随机左平移
            success, msg, data = robot.shift_left(distance_m=0.5)   # 向左平移0.5米
            success, msg, data = robot.shift_left(speed_ms=0.3, time_s=4)  # 以0.3m/s速度向左平移4秒
        """
        try:
            # 解析移动参数
            success, msg, params = self._resolve_movement_parameters(steps, distance_m, time_s, speed_ms)
            if not success:
                return False, f"左平移动作参数解析失败 Left shift movement parameter resolution failed: {msg}", None
            
            # 执行移动动作
            success, msg, execution_data = self._execute_movement_with_move('left', params, "左平移 Left Shift", speed_ms)
            if not success:
                return False, f"左平移动作执行失败 Left shift movement execution failed: {msg}", None
            
            return True, "左平移动作执行成功 Left shift movement executed successfully", execution_data
        except Exception as e:
            return False, f"左平移动作执行失败 Left shift movement failed: {str(e)}", None
    
    def shift_right(self, steps: Optional[int] = None, distance_m: Optional[float] = None,
                    time_s: Optional[float] = None, speed_ms: Optional[float] = None) -> tuple:
        """
        右平移动作
        Right shift movement
        
        Args:
            steps: 步数 Number of steps (highest priority)
            distance_m: 距离(米) Distance in meters
            time_s: 时间(秒) Time in seconds
            speed_ms: 速度(米/秒) Speed in m/s
        
        Returns:
            tuple: (success: bool, message: str, data: dict)
                success: 执行是否成功 Whether execution was successful
                message: 执行结果消息 Execution result message
                data: 执行数据(包含步数、时间等信息) Execution data (steps, time, etc.)
        
        Examples:
            success, msg, data = robot.shift_right()                # 默认随机右平移
            success, msg, data = robot.shift_right(distance_m=0.8)  # 向右平移0.8米
            success, msg, data = robot.shift_right(speed_ms=0.4, distance_m=1.5)  # 以0.4m/s速度向右平移1.5米
        """
        try:
            # 解析移动参数
            success, msg, params = self._resolve_movement_parameters(steps, distance_m, time_s, speed_ms)
            if not success:
                return False, f"右平移动作参数解析失败 Right shift movement parameter resolution failed: {msg}", None
            
            # 执行移动动作
            success, msg, execution_data = self._execute_movement_with_move('right', params, "右平移 Right Shift", speed_ms)
            if not success:
                return False, f"右平移动作执行失败 Right shift movement execution failed: {msg}", None
            
            return True, "右平移动作执行成功 Right shift movement executed successfully", execution_data
        except Exception as e:
            return False, f"右平移动作执行失败 Right shift movement failed: {str(e)}", None
    
    def rotate(self, direction: Optional[str] = None, angle_deg: Optional[float] = None,
               time_s: Optional[float] = None, angular_speed_deg_s: Optional[float] = None) -> tuple:
        """
        旋转动作
        Rotation movement
        
        Args:
            direction: 方向 Direction ('left'/'right' or '左'/'右')
            angle_deg: 角度(度) Angle in degrees
            time_s: 时间(秒) Time in seconds
            angular_speed_deg_s: 角速度(度/秒) Angular speed in deg/s
        
        Returns:
            tuple: (success: bool, message: str, data: dict)
                success: 执行是否成功 Whether execution was successful
                message: 执行结果消息 Execution result message
                data: 执行数据(包含方向、角度、时间等信息) Execution data (direction, angle, time, etc.)
        
        Examples:
            success, msg, data = robot.rotate()                     # 随机方向随机时间旋转
            success, msg, data = robot.rotate(direction='left')     # 向左旋转随机时间
            success, msg, data = robot.rotate(time_s=3)             # 随机方向旋转3秒
            success, msg, data = robot.rotate(angular_speed_deg_s=45, time_s=2)  # 以45°/s速度旋转2秒
            success, msg, data = robot.rotate(direction='right', angle_deg=90)    # 向右旋转90度
        """
        try:
            # 解析方向 Parse direction
            if direction is None:
                direction = random.choice(['left', 'right'])
            elif direction in ['左', 'left', 'Left', 'LEFT']:
                direction = 'left'
            elif direction in ['右', 'right', 'Right', 'RIGHT']:
                direction = 'right'
            else:
                print(f"未知方向 Unknown direction: {direction}, 使用随机方向 using random direction")
                direction = random.choice(['left', 'right'])
            
            # 选择旋转函数 Select rotation function
            rotate_func = self.robot.turnleft if direction == 'left' else self.robot.turnright
            direction_name = "左转 Turn Left" if direction == 'left' else "右转 Turn Right"
            
            # 解析旋转参数 Parse rotation parameters
            if angle_deg is not None and angular_speed_deg_s is not None:
                # 角度和角速度都指定 Both angle and angular speed specified
                time_calculated = angle_deg / angular_speed_deg_s
                steps = max(1, int(time_calculated / 0.5))  # 假设每步0.5秒 Assume 0.5s per step
                step_interval = time_calculated / steps
                angle_calculated = angle_deg
            elif angle_deg is not None:
                # 仅指定角度 Only angle specified
                # 使用默认档位的角速度标定值
                default_level = self.default_config.get('robot_angular_speed_level', 10)
                default_angular_speed = self.angular_speed_calibration.get(default_level, 30.0)
                time_calculated = angle_deg / default_angular_speed
                steps = max(1, int(time_calculated / 0.5))
                step_interval = time_calculated / steps
                angle_calculated = angle_deg
                print(f"[DEBUG] 角度计算: {angle_deg}度 ÷ {default_angular_speed}度/秒 = {time_calculated:.2f}秒")
            elif time_s is not None:
                # 指定时间 Time specified
                if angular_speed_deg_s is not None:
                    angle_calculated = angular_speed_deg_s * time_s
                else:
                    angle_calculated = self.default_config['default_angular_speed_deg_s'] * time_s
                steps = max(1, int(time_s / 0.5))
                step_interval = time_s / steps
                time_calculated = time_s
            elif angular_speed_deg_s is not None:
                # 仅指定角速度 Only angular speed specified
                time_default = self.default_config['default_time_s']
                angle_calculated = angular_speed_deg_s * time_default
                steps = max(1, int(time_default / 0.5))
                step_interval = time_default / steps
                time_calculated = time_default
            else:
                # 默认情况 Default case
                time_random = random.uniform(*self.default_config['random_time_range'])
                angle_calculated = self.default_config['default_angular_speed_deg_s'] * time_random
                steps = max(1, int(time_random / 0.5))
                step_interval = time_random / steps
                time_calculated = time_random
            
            # 执行旋转 Execute rotation
            # 旋转参数已计算 Rotation parameters calculated
            
            # 使用move方法执行旋转
            direction_move = 'turn_left' if direction == 'left' else 'turn_right'
            
            # 构造参数字典
            params = {
                'total_time_s': time_calculated,
                'steps': steps
            }
            
            # 使用新的move方法执行，传递角速度参数
            if angular_speed_deg_s is not None:
                target_angular_speed = angular_speed_deg_s
            else:
                # 没有指定角速度时，使用默认档位10的角速度
                default_level = self.default_config.get('robot_angular_speed_level', 10)
                target_angular_speed = self.angular_speed_calibration.get(default_level, 30.0)
                print(f"[DEBUG] rotate方法使用默认档位: {default_level}, 角速度{target_angular_speed}度/秒")
            success, msg, execution_data = self._execute_movement_with_move(direction_move, params, direction_name, target_angular_speed)
            if not success:
                return False, f"旋转动作执行失败 Rotation movement execution failed: {msg}", None
            
            start_time = execution_data.get('actual_time_s', time_calculated)
            
            actual_time = time.time() - start_time
            # 旋转完成 Rotation completed
            
            # 动作间暂停 Pause between actions
            time.sleep(self.default_config['pause_between_actions_s'])
            
            return True, f"{direction_name}执行成功 {direction_name} executed successfully", {
                'action': 'rotate',
                'direction': direction,
                'angle_deg': angle_calculated,
                'time_s': time_calculated if 'time_calculated' in locals() else actual_time,
                'angular_speed_deg_s': target_angular_speed,
                'steps': steps,
                'step_interval_s': step_interval,
                'actual_time_s': actual_time
            }
        except Exception as e:
            return False, f"旋转动作执行失败 Rotation failed: {str(e)}", None
    
    # ==================== 预设动作 Preset Actions ====================
    
    def adjust_height(self, level: Optional[int] = None) -> tuple:
        """
        调整身高
        Adjust body height
        
        Args:
            level: 高度档位 Height level (1=低, 2=中, 3=高) (1=low, 2=medium, 3=high)
                  如果不指定，则随机选择 If not specified, randomly select
        
        Returns:
            tuple: (success: bool, message: str, data: dict)
                success: 执行是否成功 Whether execution was successful
                message: 执行结果消息 Execution result message
                data: 执行数据(包含高度档位信息) Execution data (height level info)
        
        Examples:
            success, msg, data = robot.adjust_height(1)    # 调低身体
            success, msg, data = robot.adjust_height(2)    # 中等身高
            success, msg, data = robot.adjust_height(3)    # 调高身体
            success, msg, data = robot.adjust_height()     # 随机高度
        """
        try:
            if level is None:
                level = random.randint(1, 3)
            
            level = max(1, min(3, level))  # 限制范围 1-3
            
            height_names = {1: "低 Low", 2: "中 Medium", 3: "高 High"}
            
            # 调整身高 Adjust height
            self.robot.height(level)
            time.sleep(1.0)  # 等待动作完成
            
            # 身高调整完成 Height adjustment completed
            time.sleep(self.default_config['pause_between_actions_s'])
            
            return True, f"身高调整成功 Height adjustment successful: {height_names[level]}", {
                'action': 'adjust_height',
                'level': level,
                'height_name': height_names[level]
            }
        except Exception as e:
            return False, f"身高调整失败 Height adjustment failed: {str(e)}", None
    
    def head_move(self, level: Optional[int] = None, direction: Optional[str] = None) -> tuple:
        """
        头部移动
        Head movement
        
        Args:
            level: 头部高度档位 Head height level (1-3)
            direction: 头部方向 Head direction ('left'/'right'/'center' or '左'/'右'/'中')
        
        Returns:
            tuple: (success: bool, message: str, data: dict)
                success: 执行是否成功 Whether execution was successful
                message: 执行结果消息 Execution result message
                data: 执行数据(包含头部位置信息) Execution data (head position info)
        
        Examples:
            success, msg, data = robot.head_move(2, 'left')    # 头部中等高度向左
            success, msg, data = robot.head_move(3)            # 头部最高位置随机方向
            success, msg, data = robot.head_move()             # 随机头部位置
        """
        try:
            if level is None:
                level = random.randint(1, 3)
            if direction is None:
                direction = random.choice(['left', 'right', 'center'])
            
            level = max(1, min(3, level))
            
            # 解析方向
            if direction in ['左', 'left', 'Left', 'LEFT']:
                direction = 'left'
            elif direction in ['右', 'right', 'Right', 'RIGHT']:
                direction = 'right'
            elif direction in ['中', 'center', 'Center', 'CENTER']:
                direction = 'center'
            else:
                direction = 'center'
            
            direction_names = {'left': '左 Left', 'right': '右 Right', 'center': '中 Center'}
            
            # 执行头部移动 - 使用基础的head_move方法
            # 注意：MutoLib只支持上下移动，不支持左右转动
            self.robot.head_move(level)
            
            time.sleep(1.0)  # 等待动作完成
            
            # 头部移动完成
            time.sleep(self.default_config['pause_between_actions_s'])
            
            return True, f"头部移动成功 Head movement successful: Level {level}, {direction_names[direction]}", {
                'action': 'head_move',
                'level': level,
                'direction': direction,
                'direction_name': direction_names[direction]
            }
        except Exception as e:
            return False, f"头部移动失败 Head movement failed: {str(e)}", None
    
    def stretch(self) -> tuple:
        """
        伸展动作
        Stretch action
        
        Returns:
            tuple: (success: bool, message: str, data: dict)
        
        Examples:
            success, msg, data = robot.stretch()
        """
        try:
            self.robot.action(1)  # 动作ID 1: 伸懒腰
            time.sleep(2.0)  # 等待动作完成
            
            time.sleep(self.default_config['pause_between_actions_s'])
            
            return True, "伸展动作执行成功 Stretch action executed successfully", {
                'action': 'stretch'
            }
        except Exception as e:
            return False, f"伸展动作执行失败 Stretch action failed: {str(e)}", None
    
    def say_hello(self) -> tuple:
        """
        打招呼动作
        Say hello action
        
        Returns:
            tuple: (success: bool, message: str, data: dict)
        
        Examples:
            success, msg, data = robot.say_hello()
        """
        try:
            self.robot.action(2)  # 动作ID 2: 打个招呼
            time.sleep(2.0)  # 等待动作完成
            
            time.sleep(self.default_config['pause_between_actions_s'])
            
            return True, "打招呼动作执行成功 Say hello action executed successfully", {
                'action': 'say_hello'
            }
        except Exception as e:
            return False, f"打招呼动作执行失败 Say hello action failed: {str(e)}", None

    def raise_left_hand(self, hold_time: float = 1.5, amplitude: int = 40, speed_ms: int = 600) -> tuple:
        """
        举起左前手（左前腿）Raise left front hand (left foreleg)
        
        Args:
            hold_time: 保持举手姿态的时间(秒) hold duration in seconds
            amplitude: 举手幅度(角度，10-60) raise amplitude in degrees
            speed_ms: 舵机动作时间(毫秒) servo move duration in ms
        Returns:
            tuple: (success, message, data)
        """
        try:
            amplitude = max(10, min(60, int(amplitude)))
            speed_ms = max(200, min(1500, int(speed_ms)))

            # 左前腿舵机ID：1(肩/摆动), 2(肘/抬升), 3(腕/末端)
            shoulder, elbow, wrist = 1, 2, 3

            seq = [
                (shoulder, amplitude // 2, speed_ms),
                (elbow, -amplitude, speed_ms),
                (wrist, amplitude // 3, speed_ms)
            ]

            for sid, ang, dur in seq:
                if self.cancel_event.is_set():
                    return False, "动作被取消 Action cancelled", None
                try:
                    self.robot.motor(sid, ang, dur)
                    time.sleep(dur / 1000.0)
                except Exception as motor_error:
                    return False, f"左手舵机动作失败 Left hand servo move failed: {motor_error}", None

            end_time = time.time() + float(hold_time)
            while time.time() < end_time:
                if self.cancel_event.is_set():
                    break
                time.sleep(0.05)

            reset_seq = [
                (shoulder, 0, speed_ms),
                (elbow, 0, speed_ms),
                (wrist, 0, speed_ms)
            ]
            for sid, ang, dur in reset_seq:
                if self.cancel_event.is_set():
                    break
                try:
                    self.robot.motor(sid, ang, dur)
                    time.sleep(dur / 1000.0)
                except Exception:
                    pass

            return True, "左手举起完成 Left hand raised", {
                'action': 'raise_left_hand',
                'amplitude': amplitude,
                'hold_time': hold_time,
                'speed_ms': speed_ms
            }
        except Exception as e:
            return False, f"左手举起失败 Raise left hand failed: {str(e)}", None

    def raise_right_hand(self, hold_time: float = 1.5, amplitude: int = 40, speed_ms: int = 600) -> tuple:
        """
        举起右前手（右前腿）Raise right front hand (right foreleg)
        
        Args:
            hold_time: 保持举手姿态的时间(秒) hold duration in seconds
            amplitude: 举手幅度(角度，10-60) raise amplitude in degrees
            speed_ms: 舵机动作时间(毫秒) servo move duration in ms
        Returns:
            tuple: (success, message, data)
        """
        try:
            amplitude = max(10, min(60, int(amplitude)))
            speed_ms = max(200, min(1500, int(speed_ms)))

            # 右前腿舵机ID：16(肩/摆动), 17(肘/抬升), 18(腕/末端)
            shoulder, elbow, wrist = 16, 17, 18

            seq = [
                (shoulder, amplitude // 2, speed_ms),
                (elbow, -amplitude, speed_ms),
                (wrist, amplitude // 3, speed_ms)
            ]

            for sid, ang, dur in seq:
                if self.cancel_event.is_set():
                    return False, "动作被取消 Action cancelled", None
                try:
                    self.robot.motor(sid, ang, dur)
                    time.sleep(dur / 1000.0)
                except Exception as motor_error:
                    return False, f"右手舵机动作失败 Right hand servo move failed: {motor_error}", None

            end_time = time.time() + float(hold_time)
            while time.time() < end_time:
                if self.cancel_event.is_set():
                    break
                time.sleep(0.05)

            reset_seq = [
                (shoulder, 0, speed_ms),
                (elbow, 0, speed_ms),
                (wrist, 0, speed_ms)
            ]
            for sid, ang, dur in reset_seq:
                if self.cancel_event.is_set():
                    break
                try:
                    self.robot.motor(sid, ang, dur)
                    time.sleep(dur / 1000.0)
                except Exception:
                    pass

            return True, "右手举起完成 Right hand raised", {
                'action': 'raise_right_hand',
                'amplitude': amplitude,
                'hold_time': hold_time,
                'speed_ms': speed_ms
            }
        except Exception as e:
            return False, f"右手举起失败 Raise right hand failed: {str(e)}", None

    def point_left_front(self, hold_time: float = 1.2, amplitude: int = 85, speed_ms: int = 400) -> tuple:
        """
        指向左前方（左前腿）Point to left-front (left foreleg)

        Args:
            hold_time: 保持指向姿态的时间(秒)
            amplitude: 指向幅度(角度，10-90)
            speed_ms: 舵机动作时间(毫秒)
        Returns:
            tuple: (success, message, data)
        """
        try:
            amplitude = max(10, min(90, int(amplitude)))
            speed_ms = max(200, min(1500, int(speed_ms)))

            # 左手实际为ID：16(肩/摆动), 17(肘/抬升), 18(腕/末端)
            shoulder, elbow, wrist = 16, 17, 18

            # 左前方：肩先动（向内收），肘稍后跟随，腕保持(0)
            if self.cancel_event.is_set():
                return False, "动作被取消 Action cancelled", None
            try:
                # 左肩向内收：多数硬件定义为负方向
                self.robot.motor(shoulder, -(amplitude // 2), speed_ms)
                delta_ms = max(60, min(150, speed_ms // 3))
                time.sleep(delta_ms / 1000.0)
                self.robot.motor(elbow, -amplitude, speed_ms)
                self.robot.motor(wrist, 0, speed_ms)
                time.sleep((speed_ms + delta_ms) / 1000.0)
            except Exception as motor_error:
                return False, f"左前方指向舵机动作失败 Left-front servo move failed: {motor_error}", None

            end_time = time.time() + float(hold_time)
            while time.time() < end_time:
                if self.cancel_event.is_set():
                    break
                time.sleep(0.05)

            # 恢复默认状态时，靠近身体的肘关节略抬高(-10)
            try:
                self.robot.motor(shoulder, 0, speed_ms)
                delta_ms = max(60, min(150, speed_ms // 3))
                time.sleep(delta_ms / 1000.0)
                self.robot.motor(elbow, -15, speed_ms)
                self.robot.motor(wrist, 0, speed_ms)
                time.sleep((speed_ms + delta_ms) / 1000.0)
            except Exception:
                pass

            return True, "指向左前方完成 Point to left-front completed", {
                'action': 'point_left_front',
                'amplitude': amplitude,
                'hold_time': hold_time,
                'speed_ms': speed_ms
            }
        except Exception as e:
            return False, f"指向左前方失败 Point to left-front failed: {str(e)}", None

    def point_right_front(self, hold_time: float = 1.2, amplitude: int = 85, speed_ms: int = 300) -> tuple:
        """
        指向右前方（右前腿）Point to right-front (right foreleg)

        Args:
            hold_time: 保持指向姿态的时间(秒)
            amplitude: 指向幅度(角度，10-90)
            speed_ms: 舵机动作时间(毫秒)
        Returns:
            tuple: (success, message, data)
        """
        try:
            amplitude = max(10, min(90, int(amplitude)))
            speed_ms = max(200, min(1500, int(speed_ms)))

            # 右手实际为ID：1(肩/摆动), 2(肘/抬升), 3(腕/末端)
            shoulder, elbow, wrist = 1, 2, 3

            # 右前方：肩先动，肘稍后跟随（避免同时到位），腕保持(0)
            if self.cancel_event.is_set():
                return False, "动作被取消 Action cancelled", None
            try:
                self.robot.motor(shoulder, (amplitude // 2), speed_ms)
                delta_ms = max(60, min(150, speed_ms // 3))
                time.sleep(delta_ms / 1000.0)
                self.robot.motor(elbow, -amplitude, speed_ms)
                self.robot.motor(wrist, 0, speed_ms)
                time.sleep((speed_ms + delta_ms) / 1000.0)
            except Exception as motor_error:
                return False, f"右前方指向舵机动作失败 Right-front servo move failed: {motor_error}", None

            end_time = time.time() + float(hold_time)
            while time.time() < end_time:
                if self.cancel_event.is_set():
                    break
                time.sleep(0.05)

            # 恢复默认状态时，靠近身体的肘关节略抬高(-10)
            try:
                self.robot.motor(shoulder, 0, speed_ms)
                delta_ms = max(60, min(150, speed_ms // 3))
                time.sleep(delta_ms / 1000.0)
                self.robot.motor(elbow, -15, speed_ms)
                self.robot.motor(wrist, 0, speed_ms)
                time.sleep((speed_ms + delta_ms) / 1000.0)
            except Exception:
                pass

            return True, "指向右前方完成 Point to right-front completed", {
                'action': 'point_right_front',
                'amplitude': amplitude,
                'hold_time': hold_time,
                'speed_ms': speed_ms
            }
        except Exception as e:
            return False, f"指向右前方失败 Point to right-front failed: {str(e)}", None
    
    def fear_retreat(self) -> tuple:
        """
        恐惧后退动作
        Fear retreat action
        
        Returns:
            tuple: (success: bool, message: str, data: dict)
        
        Examples:
            success, msg, data = robot.fear_retreat()
        """
        try:
            self.robot.action(3)  # 动作ID 3: 害怕退缩
            time.sleep(2.0)  # 等待动作完成
            
            time.sleep(self.default_config['pause_between_actions_s'])
            
            return True, "恐惧后退动作执行成功 Fear retreat action executed successfully", {
                'action': 'fear_retreat'
            }
        except Exception as e:
            return False, f"恐惧后退动作执行失败 Fear retreat action failed: {str(e)}", None
    
    def warm_up_squat(self) -> tuple:
        """
        热身蹲起动作 - 单次执行
        Warm up squat action - single execution
        
        Returns:
            tuple: (success: bool, message: str, data: dict)
        
        Examples:
            success, msg, data = robot.warm_up_squat()
        """
        try:
            # 执行单次蹲起动作
            self.robot.action(4)  # 动作ID 4: 热身起蹲
            
            return True, "热身蹲起动作执行成功 Warm up squat action executed successfully", {
                'action': 'warm_up_squat',
                'mode': 'single'
            }
        except Exception as e:
            return False, f"热身蹲起动作执行失败 Warm up squat action failed: {str(e)}", None
    
    def spin_in_place(self) -> tuple:
        """
        原地旋转动作
        Spin in place action
        
        Returns:
            tuple: (success: bool, message: str, data: dict)
        
        Examples:
            success, msg, data = robot.spin_in_place()
        """
        try:
            self.robot.action(5)  # 动作ID 5: 原地转圈
            time.sleep(2.0)  # 等待动作完成
            
            time.sleep(self.default_config['pause_between_actions_s'])
            
            return True, "原地旋转动作执行成功 Spin in place action executed successfully", {
                'action': 'spin_in_place'
            }
        except Exception as e:
            return False, f"原地旋转动作执行失败 Spin in place action failed: {str(e)}", None
    
    def wave_no(self) -> tuple:
        """
        摆手说不动作
        Wave no action
        
        Returns:
            tuple: (success: bool, message: str, data: dict)
        
        Examples:
            success, msg, data = robot.wave_no()
        """
        try:
            self.robot.action(6)  # 动作ID 6: 摆手说不
            time.sleep(2.0)  # 等待动作完成
            
            time.sleep(self.default_config['pause_between_actions_s'])
            
            return True, "摆手说不动作执行成功 Wave no action executed successfully", {
                'action': 'wave_no'
            }
        except Exception as e:
            return False, f"摆手说不动作执行失败 Wave no action failed: {str(e)}", None
    
    def curl_up(self) -> tuple:
        """
        蜷缩动作
        Curl up action
        
        Returns:
            tuple: (success: bool, message: str, data: dict)
        
        Examples:
            success, msg, data = robot.curl_up()
        """
        try:
            self.robot.action(7)  # 动作ID 7: 蜷缩身体
            time.sleep(2.0)  # 等待动作完成
            
            time.sleep(self.default_config['pause_between_actions_s'])
            
            return True, "蜷缩动作执行成功 Curl up action executed successfully", {
                'action': 'curl_up'
            }
        except Exception as e:
            return False, f"蜷缩动作执行失败 Curl up action failed: {str(e)}", None
    
    def big_stride(self) -> tuple:
        """
        大步走动作
        Big stride action
        
        Returns:
            tuple: (success: bool, message: str, data: dict)
        
        Examples:
            success, msg, data = robot.big_stride()
        """
        try:
            self.robot.action(8)  # 动作ID 8: 大步向前
            time.sleep(2.0)  # 等待动作完成
            
            time.sleep(self.default_config['pause_between_actions_s'])
            
            return True, "大步走动作执行成功 Big stride action executed successfully", {
                'action': 'big_stride'
            }
        except Exception as e:
            return False, f"大步走动作执行失败 Big stride action failed: {str(e)}", None
    
    def stop_action(self) -> tuple:
        """
        停止动作
        Stop action
        
        Returns:
            tuple: (success: bool, message: str, data: dict)
        
        Examples:
            success, msg, data = robot.stop_action()
        """
        try:
            # 设置取消标志，打断所有耗时循环
            self.request_cancel()
            self.robot.stay_put()
            time.sleep(0.5)
            
            return True, "停止动作执行成功 Stop action executed successfully", {
                'action': 'stop_action'
            }
        except Exception as e:
            return False, f"停止动作执行失败 Stop action failed: {str(e)}", None
    
    def stop(self) -> tuple:
        """
        停止机器人
        Stop robot
        
        Returns:
            tuple: (success: bool, message: str, data: dict)
        
        Examples:
            success, msg, data = robot.stop()
        """
        try:
            # 设置取消标志，打断正在进行的循环
            self.request_cancel()
            self.robot.stay_put()
            return True, "机器人已停止 Robot stopped", {
                'action': 'stop',
                'status': 'stopped'
            }
        except Exception as e:
            return False, f"停止机器人失败 Stop robot failed: {str(e)}", None
    
    def execute_preset_action(self, action_name: str, **kwargs) -> tuple:
        """
        执行预设动作
        Execute preset action
        
        Args:
            action_name: 动作名称 Action name
            **kwargs: 动作参数 Action parameters
            
        Returns:
            tuple: (success: bool, message: str, data: dict)
        """
        try:
            # 预设动作映射
            action_map = {
                'adjust_height': self.adjust_height,
                'head_move': self.head_move,
                'stretch': self.stretch,
                'say_hello': self.say_hello,
                'fear_retreat': self.fear_retreat,
                'warm_up_squat': self.warm_up_squat,
                'spin_in_place': self.spin_in_place,
                'wave_no': self.wave_no,
                'curl_up': self.curl_up,
                'big_stride': self.big_stride,
                'stop_action': self.stop_action,
                # 兼容旧举手动作：映射到前方指向
                'raise_left_hand': self.point_left_front,
                'raise_right_hand': self.point_right_front,
                'point_left_front': self.point_left_front,
                'point_right_front': self.point_right_front
            }
            
            if action_name not in action_map:
                return False, f"未知的预设动作: {action_name} Unknown preset action: {action_name}", None
            
            action_func = action_map[action_name]
            return action_func(**kwargs)
            
        except Exception as e:
            return False, f"执行预设动作失败 Execute preset action failed: {str(e)}", None
    
    def get_status(self) -> tuple:
        """
        获取机器人状态
        Get robot status
        
        Returns:
            tuple: (success: bool, message: str, data: dict)
        """
        try:
            status_data = {
                'timestamp': time.time(),
                'robot_connected': self.robot is not None,
                'firmware_version': None,
                'battery_info': None,
                'attitude': None,
                'servo_angles': None,
                'config': self.get_config()
            }
            
            # 获取固件版本
            success, message, data = self.get_firmware_version()
            if success and data:
                status_data['firmware_version'] = data
            
            # 获取电池信息
            success, message, data = self.get_battery_info()
            if success and data:
                status_data['battery_info'] = data
            
            # 获取姿态信息
            success, message, data = self.get_attitude()
            if success and data:
                status_data['attitude'] = data
            
            # 获取所有舵机角度
            success, message, data = self.get_servo_angles()
            if success and data:
                status_data['servo_angles'] = data
            
            # 尝试获取实际机器人状态（如果支持）
            if hasattr(self.robot, 'get_status'):
                try:
                    robot_status = self.robot.get_status()
                    status_data['robot_internal_status'] = robot_status
                except Exception as e:
                    status_data['robot_internal_status'] = f"获取失败: {str(e)}"
            
            return True, "获取机器人状态成功 Robot status retrieved successfully", status_data
            
        except Exception as e:
            return False, f"获取机器人状态失败 Get robot status failed: {str(e)}", None
    
    def print_status(self) -> tuple:
        """
        打印机器人状态
        Print robot status
        
        Returns:
            tuple: (success: bool, message: str, data: dict)
        """
        try:
            success, message, status = self.get_status()
            if success and status:
                print("\n=== 机器人控制器状态 Robot Controller Status ===")
                
                # 基本信息
                print(f"\n🤖 基本信息:")
                print(f"  连接状态: {'✅ 已连接' if status.get('robot_connected') else '❌ 未连接'}")
                print(f"  时间戳: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(status.get('timestamp', 0)))}")
                
                # 固件版本
                firmware = status.get('firmware_version')
                if firmware:
                    print(f"\n💾 固件版本:")
                    print(f"  版本: {firmware.get('version', 'Unknown')}")
                else:
                    print(f"\n💾 固件版本: 获取失败")
                
                # 电池信息
                battery = status.get('battery_info')
                if battery:
                    print(f"\n🔋 电池信息:")
                    if 'voltage' in battery:
                        print(f"  电压: {battery['voltage']:.2f}V")
                    if 'percentage' in battery:
                        print(f"  电量: {battery['percentage']:.1f}%")
                else:
                    print(f"\n🔋 电池信息: 获取失败")
                
                # 姿态信息
                attitude = status.get('attitude')
                if attitude:
                    print(f"\n📐 姿态信息:")
                    print(f"  俯仰角: {attitude.get('pitch', 0):.2f}°")
                    print(f"  横滚角: {attitude.get('roll', 0):.2f}°")
                    print(f"  偏航角: {attitude.get('yaw', 0):.2f}°")
                else:
                    print(f"\n📐 姿态信息: 获取失败")
                
                # 舵机角度
                servo_angles = status.get('servo_angles')
                if servo_angles and isinstance(servo_angles, dict):
                    print(f"\n⚙️ 舵机角度:")
                    for servo_id, angle in servo_angles.items():
                        if isinstance(angle, (int, float)):
                            print(f"  舵机{servo_id}: {angle:.1f}°")
                else:
                    print(f"\n⚙️ 舵机角度: 获取失败")
                
                # 配置信息
                config = status.get('config', {})
                if config:
                    print(f"\n🔧 配置信息:")
                    print(f"  步距: {config.get('step_distance_cm', 'Unknown')}cm")
                    print(f"  速度校准: {config.get('speed_calibration', 'Unknown')}")
                
                print("\n✅ 机器人状态打印完成")
                
                return True, "打印机器人状态成功 Robot status printed successfully", status
            else:
                print(f"\n❌ 获取机器人状态失败: {message}")
                return False, f"打印机器人状态失败 Failed to print robot status: {message}", None
        except Exception as e:
            error_msg = f"打印机器人状态出错 Error printing robot status: {str(e)}"
            print(f"\n❌ {error_msg}")
            return False, error_msg, None
    
    def get_firmware_version(self) -> tuple:
        """
        获取固件版本
        Get firmware version
        
        Returns:
            tuple: (success: bool, message: str, data: dict)
        """
        try:
            # 尝试获取实际固件版本
            if hasattr(self.robot, 'read_version'):
                firmware_data = self.robot.read_version()
                return True, "获取固件版本成功 Firmware version retrieved successfully", {
                    'version': firmware_data
                }
            else:
                return False, "机器人不支持固件版本查询 Robot does not support firmware version query", None
        except Exception as e:
            return False, f"获取固件版本失败 Get firmware version failed: {str(e)}", None
    
    def get_battery_info(self, as_voltage: bool = True) -> tuple:
        """
        获取电池信息
        Get battery information
        
        Args:
            as_voltage: True返回电压值(V), False返回百分比(%)
                       True returns voltage(V), False returns percentage(%)
        
        Returns:
            tuple: (success: bool, message: str, data: dict)
        """
        try:
            # 尝试获取实际电池信息
            if hasattr(self.robot, 'read_battery'):
                # MutoLibCore的read_battery方法：
                # voltage=True时返回百分比，voltage=False时返回电压值
                # 所以我们需要传入相反的值
                battery_data = self.robot.read_battery(voltage=not as_voltage)
                unit = "V" if as_voltage else "%"
                print(f"[DEBUG] get_battery_info: as_voltage={as_voltage}, called read_battery(voltage={not as_voltage}), battery_data={battery_data}, unit={unit}")
                
                if battery_data is None:
                    print(f"[ERROR] get_battery_info: read_battery returned None")
                    return False, "获取电池信息失败：硬件返回空值 Get battery info failed: hardware returned None", None
                
                # 构建返回数据
                return_data = {
                    'value': battery_data,
                    'unit': unit,
                    'as_voltage': as_voltage
                }
                return_tuple = (True, f"获取电池信息成功 Battery info retrieved successfully: {battery_data}{unit}", return_data)
                print(f"[DEBUG] get_battery_info: returning tuple = {return_tuple}")
                return return_tuple
            else:
                return False, "机器人不支持电池信息查询 Robot does not support battery info query", None
        except Exception as e:
            print(f"[ERROR] get_battery_info exception: {str(e)}")
            return False, f"获取电池信息失败 Get battery info failed: {str(e)}", None
    
    def get_attitude(self) -> tuple:
        """
        获取姿态信息
        Get attitude information
        
        Returns:
            tuple: (success: bool, message: str, data: dict)
        """
        try:
            # 尝试获取实际姿态信息
            if hasattr(self.robot, 'read_IMU'):
                attitude_data = self.robot.read_IMU()
                if attitude_data:
                    roll, pitch, yaw, temp = attitude_data
                    return True, "获取姿态信息成功 Attitude info retrieved successfully", {
                        'roll': roll,
                        'pitch': pitch, 
                        'yaw': yaw,
                        'temperature': temp
                    }
                else:
                    return False, "获取姿态信息失败 Failed to read IMU data", None
            else:
                return False, "机器人不支持姿态信息查询 Robot does not support attitude info query", None
        except Exception as e:
            return False, f"获取姿态信息失败 Get attitude info failed: {str(e)}", None
    
    def get_imu_raw_data(self) -> tuple:
        """
        获取IMU原始数据
        Get IMU raw data
        
        Returns:
            tuple: (success: bool, message: str, data: dict)
        """
        try:
            # 尝试获取实际IMU原始数据
            if hasattr(self.robot, 'read_IMU_Raw'):
                imu_data = self.robot.read_IMU_Raw()
                if imu_data:
                    acc_x, acc_y, acc_z, gyro_x, gyro_y, gyro_z, mag_x, mag_y, mag_z = imu_data
                    return True, "获取IMU原始数据成功 IMU raw data retrieved successfully", {
                        'accelerometer': {'x': acc_x, 'y': acc_y, 'z': acc_z},
                        'gyroscope': {'x': gyro_x, 'y': gyro_y, 'z': gyro_z},
                        'magnetometer': {'x': mag_x, 'y': mag_y, 'z': mag_z}
                    }
                else:
                    return False, "获取IMU原始数据失败 Failed to read IMU raw data", None
            else:
                return False, "机器人不支持IMU原始数据查询 Robot does not support IMU raw data query", None
        except Exception as e:
            return False, f"获取IMU原始数据失败 Get IMU raw data failed: {str(e)}", None
    
    def get_servo_angles(self, servo_id: Optional[int] = None) -> tuple:
        """
        获取舵机角度
        Get servo angles
        
        Args:
            servo_id: 舵机ID Servo ID (1-18), 如果为None则返回所有舵机角度
            
        Returns:
            tuple: (success: bool, message: str, data: dict)
        """
        try:
            # 尝试获取实际舵机角度数据
            if hasattr(self.robot, 'read_motor'):
                all_angles = self.robot.read_motor()
                if all_angles:
                    if servo_id is None:
                        # 返回所有舵机角度
                        return True, "获取所有舵机角度成功 All servo angles retrieved successfully", {
                            'all_angles': all_angles
                        }
                    elif 1 <= servo_id <= 18:
                        servo_angle = all_angles[servo_id - 1]  # 转换为0索引
                        return True, f"获取舵机{servo_id}角度成功 Servo {servo_id} angles retrieved successfully", {
                            'servo_id': servo_id,
                            'angle': servo_angle
                        }
                    else:
                        return False, f"舵机ID必须在1-18范围内 Servo ID must be in range 1-18, got: {servo_id}", None
                else:
                    return False, f"获取舵机角度失败 Failed to read servo angles", None
            else:
                return False, f"机器人不支持舵机角度查询 Robot does not support servo angles query", None
        except Exception as e:
            return False, f"获取舵机角度失败 Get servo angles failed: {str(e)}", None
    
    def get_leg_angles(self, leg_id: int) -> tuple:
        """
        获取腿部角度
        Get leg angles
        
        Args:
            leg_id: 腿部ID Leg ID
            
        Returns:
            tuple: (success: bool, message: str, data: dict)
        """
        try:
            # 尝试获取实际腿部角度数据
            if hasattr(self.robot, 'read_leg'):
                leg_data = self.robot.read_leg(leg_id)
                if leg_data and 1 <= leg_id <= 6:
                    hip, knee, ankle = leg_data
                    return True, f"获取腿{leg_id}角度成功 Leg {leg_id} angles retrieved successfully", {
                        'leg_id': leg_id,
                        'hip': hip,
                        'knee': knee,
                        'ankle': ankle
                    }
                else:
                    return False, f"获取腿{leg_id}角度失败 Failed to read leg {leg_id} angles", None
            else:
                return False, f"机器人不支持腿{leg_id}角度查询 Robot does not support leg {leg_id} angles query", None
        except Exception as e:
            return False, f"获取腿{leg_id}角度失败 Get leg {leg_id} angles failed: {str(e)}", None
    
    def get_servo_offset(self, servo_id: int) -> tuple:
        """
        获取舵机偏移值
        Get servo offset
        
        Args:
            servo_id: 舵机ID Servo ID
            
        Returns:
            tuple: (success: bool, message: str, data: dict)
        """
        try:
            # 尝试获取实际舵机偏移数据
            if hasattr(self.robot, 'read_offset'):
                offset = self.robot.read_offset(servo_id)
                if offset is not None and 1 <= servo_id <= 18:
                    return True, f"获取舵机{servo_id}偏移值成功 Servo {servo_id} offset retrieved successfully", {
                        'servo_id': servo_id,
                        'offset': offset
                    }
                else:
                    return False, f"获取舵机{servo_id}偏移值失败 Failed to read servo {servo_id} offset", None
            else:
                return False, f"机器人不支持舵机{servo_id}偏移值查询 Robot does not support servo {servo_id} offset query", None
        except Exception as e:
            return False, f"获取舵机{servo_id}偏移值失败 Get servo {servo_id} offset failed: {str(e)}", None
    
    def stop_continuous_action(self, action_name: str, skip_reset: bool = False) -> tuple:
        """
        停止持续性动作
        Stop continuous action
        
        Args:
            action_name: 动作名称 Action name
            skip_reset: 是否跳过复位操作 Whether to skip reset operation
            
        Returns:
            tuple: (success: bool, message: str, data: dict)
        """
        try:
            if action_name in self.continuous_actions:
                # 设置停止标志
                self.continuous_actions[action_name] = False
                
                # 等待线程结束
                if action_name in self.action_threads:
                    thread = self.action_threads[action_name]
                    if thread.is_alive():
                        thread.join(timeout=3.0)  # 最多等待3秒
                    
                    # 清理线程引用
                    del self.action_threads[action_name]
                
                # 清理锁
                if action_name in self.action_locks:
                    del self.action_locks[action_name]
                
                # 清理状态
                del self.continuous_actions[action_name]
                
                # 停止动作后调用stop方法进行复位（除非明确跳过）
                if not skip_reset:
                    try:
                        self.robot.stop()
                    except Exception as stop_error:
                        # 如果复位失败，记录错误但不影响主要的停止操作
                        pass
                
                status_msg = "stopped_and_reset" if not skip_reset else "stopped"
                action_msg = "已停止并复位" if not skip_reset else "已停止"
                return True, f"持续动作 {action_name} {action_msg} Continuous action {action_name} stopped{'_and_reset' if not skip_reset else ''}", {
                    'action': action_name,
                    'status': status_msg
                }
            else:
                return False, f"持续动作 {action_name} 未在运行 Continuous action {action_name} is not running", None
                
        except Exception as e:
            return False, f"停止持续动作失败 Stop continuous action failed: {str(e)}", None
    
    def stop_all_continuous_actions(self) -> tuple:
        """
        停止所有持续性动作
        Stop all continuous actions
        
        Returns:
            tuple: (success: bool, message: str, data: dict)
        """
        try:
            stopped_actions = []
            
            # 复制键列表，避免在迭代时修改字典
            action_names = list(self.continuous_actions.keys())
            
            for action_name in action_names:
                if self.continuous_actions.get(action_name, False):
                    # 对于批量停止，跳过每个动作的单独复位，最后统一复位
                    success, message, data = self.stop_continuous_action(action_name, skip_reset=True)
                    if success:
                        stopped_actions.append(action_name)
            
            # 如果停止了任何动作，最后统一进行一次复位
            if stopped_actions:
                try:
                    self.robot.stop()
                except Exception as stop_error:
                    # 如果复位失败，记录错误但不影响主要的停止操作
                    pass
                
                return True, f"已停止 {len(stopped_actions)} 个持续动作并复位 Stopped {len(stopped_actions)} continuous actions and reset", {
                    'stopped_actions': stopped_actions,
                    'reset_performed': True
                }
            else:
                return True, "没有运行中的持续动作 No continuous actions running", {
                    'stopped_actions': [],
                    'reset_performed': False
                }
                
        except Exception as e:
            return False, f"停止所有持续动作失败 Stop all continuous actions failed: {str(e)}", None

    def get_config(self) -> dict:
        """
        获取当前配置
        Get current configuration
        
        Returns:
            dict: 当前配置信息 Current configuration info
        """
        return {
            'default_config': self.default_config,
            'step_distance_cm': self.step_distance_cm,
            'speed_calibration': self.speed_calibration
        }
