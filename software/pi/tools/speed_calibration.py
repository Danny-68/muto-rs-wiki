#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
30档速度标定脚本 (支持线速度和角速度)
30-Level Speed Calibration Script (Support Linear and Angular Speed)

该脚本用于标定六足机器人的30档速度，支持线速度和角速度的独立标定
This script calibrates 30 speed levels for hexapod robot with separate linear and angular speed calibration

作者: YAHBOOM | Gentle Xu
Author: YAHBOOM | Gentle Xu
"""

import time
import json
import os
import numpy as np
import threading
from typing import Dict, List, Tuple, Optional
from datetime import datetime

try:
    from muto_hexapod_lib.MutoLargemodelInterface import MutoController
except ImportError as e:
    print(f"❌ 导入MutoLargemodelInterface错误: {e}")
    print("请确保已正确安装muto_hexapod_lib包")
    exit(1)

# 全局文本资源
# Global text resources
TEXT_RES = {
    'en': {
        'init_success': "✅ Robot initialized successfully",
        'init_fail': "❌ Robot initialization failed: {}",
        'calib_linear': "Linear Speed",
        'calib_angular': "Angular Speed",
        'unit_linear': "m/s",
        'unit_angular': "deg/s",
        'start_calib': "\n🔧 Calibrating {} Level {}",
        'select_mode': "Select calibration mode:",
        'mode_test': "1. Robot {} test (Press Enter)",
        'mode_input': "2. Direct input {} (Type 'd')",
        'mode_undo': "3. Undo last input (Type 'u')",
        'move': "move",
        'rotate': "rotate",
        'choice_prompt': "Please select [Enter/d/u]: ",
        'undo_success': "✅ Undid calibration for level {}",
        'no_undo': "⚠️  Nothing to undo",
        'input_prompt': "Please input {} for level {} ({}): ",
        'neg_error': "{} cannot be negative",
        'input_success': "✅ Level {} direct input: {:.3f} {}",
        'invalid_num': "Please enter a valid number",
        'invalid_choice': "Invalid choice, please try again",
        'test_linear_desc': "Robot will move forward at level {} for 3 seconds",
        'test_angular_desc': "Robot will rotate at level {}, press Enter after 360 degrees",
        'press_enter': "Press Enter to start...",
        'preparing': "Preparing to start...",
        'start_move': "Start moving!",
        'move_done': "Movement completed!",
        'input_dist': "Enter actual distance (meters) [Type 'u' to undo]: ",
        'cancel_test': "Test cancelled",
        'invalid_val': "❌ Invalid value!",
        'error_options': "1. Next level (Enter)\n2. Re-input (r)\n3. Re-calibrate (c)",
        'error_choice': "Select [Enter/r/c]: ",
        're_calib': "🔄 Re-calibrating current level...",
        'skip_level': "⏭️ Skipping current level",
        'start_rotate': "Start rotating! Press Enter after 360 degrees...",
        'rotate_done': "Rotation stopped! Time: {:.2f}s",
        'test_result': "Test Result:",
        'time_res': "  Time: {:.2f}s",
        'dist_res': "  Distance: {:.3f}m",
        'speed_res': "  Actual Speed: {:.3f} m/s",
        'angle_res': "  Angle: {:.1f} deg",
        'ang_speed_res': "  Actual Angular Speed: {:.1f} deg/s",
        'test_error': "❌ Test error: {}",
        'start_flow': "\n🚀 Starting interactive calibration",
        'levels_info': "Levels to calibrate: {}",
        'repeats_info': "Repeats per level: {}",
        'notes': "\nNotes:\n1. Ensure safe area\n2. Prepare measuring tools\n3. Observe movement",
        'progress': "\n" + "="*50 + "\nProgress: {}/{} - Level {}\n" + "="*50,
        'calib_success': "✅ Level {} calibrated successfully",
        'calib_fail': "❌ Level {} calibration failed",
        'retry_prompt': "Retry this level? (y/n): ",
        're_calib_success': "✅ Level {} re-calibrated successfully",
        'continue_prompt': "\nContinue to next level {}? (y/n): ",
        'flow_interrupt': "Calibration interrupted",
        'flow_complete': "\n✅ Calibration complete, {} levels calibrated",
        'start_interp': "\n🔄 Starting linear interpolation...",
        'interp_complete': "\n✅ Interpolation complete",
        'save_success': "\n💾 Results saved to: {}",
        'save_fail': "❌ Save failed: {}",
        'load_success': "✅ Results loaded from {}",
        'load_fail': "❌ Load failed: {}",
        'summary': "\n📈 Calibration Summary",
        'header': "{:<4} {:<12} {:<12}",
        'stats': "\n📈 Statistics:",
        'stats_detail': "  Calibrated: {}\n  Interpolated: {}\n  Total: 30",
        'config_missing': "⚠️  Config file not found: {}",
        'calib_method': "Calibrated",
        'interp_method': "Interpolated",
        
        # New keys
        'sys_title': "🤖 Hexapod Robot 30-Level Speed Interactive Calibration System",
        'sys_funcs': "\nSystem Functions:",
        'sys_func1': "1. Interactive calibration - Precise level-by-level calibration",
        'sys_func2': "2. Support independent linear and angular speed calibration",
        'sys_func3': "3. Real-time input - Input speed based on actual measurement",
        'sys_func4': "4. Smart interpolation - Auto-calculate uncalibrated levels",
        'sys_func5': "5. Data save/load - Persist calibration results",
        'sys_ensure': "\n⚠️  Please ensure before use:",
        'sys_ensure1': "- Robot connected and initialized",
        'sys_ensure2': "- Safe moving space (recommended > 3m)",
        'sys_ensure3': "- Measuring tools ready (tape, protractor)",
        'sys_ensure4': "- Robot battery sufficient",
        'select_func': "\n📋 Please select function mode:",
        'func_linear': "1. Linear Speed Calibration (m/s) - Test movement speed",
        'func_angular': "2. Angular Speed Calibration (deg/s) - Test rotation speed",
        'func_load_angular': "3. Load Angular Calibration File to Config",
        'func_load_linear': "4. Load Linear Calibration File to Config",
        'select_mode_prompt': "\nPlease select function mode [1/2/3/4]: ",
        'mode_linear_selected': "✅ Linear speed calibration mode selected",
        'mode_angular_selected': "✅ Angular speed calibration mode selected",
        'mode_load_angular_selected': "✅ Load angular calibration file mode selected",
        'mode_load_linear_selected': "✅ Load linear calibration file mode selected",
        'invalid_mode': "❌ Invalid choice, please enter 1, 2, 3 or 4",
        'start_flow_msg': "\n🚀 Starting calibration flow...",
        'init_sys': "\n🔧 Initializing calibration system...",
        'init_complete': "✅ System initialized - {} calibration mode",
        'congrats': "\n🎊 Congratulations! Calibration complete!",
        'saved_to': "📁 Results saved to: {}",
        'view_res_prompt': "\nView calibration summary? (y/n): ",
        'show_res': "\n📖 Calibration Results:",
        'use_current': "✅ Using current calibration data",
        'write_config_prompt': "\nAutomatically write {} calibration results to robot_config.json? (y/n): ",
        'write_success': "🎉 {} calibration results successfully written to config!",
        'write_fail': "❌ Write to config failed",
        'calib_incomplete': "\n⚠️  Calibration incomplete or cancelled",
        'retry_msg': "You can re-run the program to continue",
        'load_mode_title': "\n📂 Load {} calibration file mode",
        'no_files': "❌ No {} calibration files found in current directory",
        'file_hint': "Please ensure filename contains '{}' and 'calibration'",
        'found_files': "\n📋 Found following {} calibration files:",
        'select_file_prompt': "\nPlease select file to load [1-{}]: ",
        'file_selected': "✅ File selected: {}",
        'invalid_file_choice': "❌ Invalid choice, please enter number between 1 and {}",
        'load_success_msg': "🎉 {} calibration data successfully loaded to config!",
        'load_fail_msg': "❌ Load calibration file failed",
        'user_interrupt': "\n\n👋 User interrupted, exiting",
        'prog_error': "\n❌ Program error: {}",
        'thanks': "\n👋 Thank you for using Hexapod Robot Calibration System!",
        
        # update_robot_config keys
        'update_angular': "\n🔄 Updating angular speed data to config...",
        'update_linear': "\n🔄 Updating linear speed data to config...",
        'config_updated': "✅ Config file updated: {}",
        'data_updated': "📊 Updated data for {} levels",
        'update_fail': "❌ Update config failed: {}",
        'angular_comment': "Angular speed calibration data (deg/s)",
        
        # load_and_update keys
        'calib_file_missing': "❌ Calibration file not found: {}",
        'calib_format_error': "❌ File format error: missing calibration_data or complete_table",
        'unknown_type': "❌ Unknown calibration type: {}",
        'load_angular_file': "\n🔄 Loading angular calibration data from: {}",
        'load_linear_file': "\n🔄 Loading linear calibration data from: {}",
        'load_file_fail': "❌ Load file failed: {}",
        'loaded_levels': "📊 Loaded {} levels of {} data",
        
        # run_full_calibration keys
        'welcome_sys': "\n🎯 30-Level Speed Interactive Calibration System",
        'welcome_msg': "\nWelcome to Hexapod Robot Speed Calibration System!",
        'sys_desc1': "\nThis system helps you calibrate 30 speed levels.",
        'sys_desc2': "Robot will move for 3 seconds at different levels,",
        'sys_desc3': "You need to measure actual distance and input to system.",
        'phase1': "\n📊 Phase 1: Fixed level calibration",
        'phase1_levels': "We will calibrate levels: {}",
        'phase1_fail': "❌ Fixed level calibration failed, cannot continue",
        'phase1_done': "Phase 1 complete!",
        'interp_prompt': "Continue to interpolate other levels? (y/n): ",
        'phase2': "\n🔄 Phase 2: Interpolating other levels",
        'skip_interp': "Skipping interpolation, saving only calibrated levels",
        'save_prompt': "Save calibration results to file? (y/n): ",
        'flow_done': "\n🎉 Calibration flow complete!",
        'patience_thanks': "Thank you for your patience!",
        'interrupt_msg': "\n\n⚠️  User interrupted calibration flow",
        'save_partial_prompt': "Save partial calibration data? (y/n): ",
        'partial_saved': "✅ Partial calibration data saved",
        'calib_error': "❌ Calibration error: {}"
    },
    'zh_cn': {
        'init_success': "✅ 机器人初始化成功",
        'init_fail': "❌ 机器人初始化失败: {}",
        'calib_linear': "线速度",
        'calib_angular': "角速度",
        'unit_linear': "m/s",
        'unit_angular': "deg/s",
        'start_calib': "\n🔧 标定{}档位 {}",
        'select_mode': "选择标定方式:",
        'mode_test': "1. 机器人{}测试（按回车）",
        'mode_input': "2. 直接输入{}值（输入 'd'）",
        'mode_undo': "3. 撤回上一次输入（输入 'u'）",
        'move': "移动",
        'rotate': "旋转",
        'choice_prompt': "请选择 [回车/d/u]: ",
        'undo_success': "✅ 已撤回档位 {} 的标定结果",
        'no_undo': "⚠️  没有可撤回的操作",
        'input_prompt': "请直接输入档位 {} 的{}值（{}）: ",
        'neg_error': "{}不能为负数，请重新输入",
        'input_success': "✅ 档位 {} 直接输入完成: {:.3f} {}",
        'invalid_num': "请输入有效的数字",
        'invalid_choice': "无效选择，请重新输入",
        'test_linear_desc': "机器人将以档位 {} 的速度前进 3 秒",
        'test_angular_desc': "机器人将以档位 {} 的角速度持续旋转，您需要观察旋转360度后按回车停止",
        'press_enter': "按回车键开始测试...",
        'preparing': "准备开始测试...",
        'start_move': "开始移动！",
        'move_done': "移动完成！",
        'input_dist': "请输入机器人实际移动的距离（米）[输入'u'撤回]: ",
        'cancel_test': "取消本次测试",
        'invalid_val': "❌ 输入的数值无效！",
        'error_options': "1. 进入下一个档位的标定 (默认，直接按回车)\n2. 重新输入距离值 (输入 'r')\n3. 重新标定当前档位 (输入 'c')",
        'error_choice': "请选择 [回车/r/c]: ",
        're_calib': "🔄 重新标定当前档位...",
        'skip_level': "⏭️ 跳过当前档位，进入下一个档位的标定",
        'start_rotate': "开始旋转！机器人正在旋转，请等待旋转360度后按回车停止...",
        'rotate_done': "旋转停止！旋转时间: {:.2f}秒",
        'test_result': "测试结果:",
        'time_res': "  移动时间: {:.2f}秒",
        'dist_res': "  移动距离: {:.3f}米",
        'speed_res': "  实际线速度: {:.3f}米/秒",
        'angle_res': "  旋转角度: {:.1f}度",
        'ang_speed_res': "  实际角速度: {:.1f}度/秒",
        'test_error': "❌ 测试过程出错: {}",
        'start_flow': "\n🚀 开始交互式档位标定",
        'levels_info': "将要标定的档位: {}",
        'repeats_info': "每个档位重复测试: {} 次",
        'notes': "\n注意事项:\n1. 每次测试前请确保机器人处于安全位置\n2. 准备好测量工具（如卷尺）\n3. 机器人将移动3秒，请观察并测量实际移动距离",
        'progress': "\n" + "="*50 + "\n标定进度: {}/{} - 档位 {}\n" + "="*50,
        'calib_success': "✅ 档位 {} 标定成功",
        'calib_fail': "❌ 档位 {} 标定失败",
        'retry_prompt': "是否重新标定此档位？(y/n): ",
        're_calib_success': "✅ 档位 {} 重新标定成功",
        'continue_prompt': "\n是否继续标定下一个档位 {}？(y/n): ",
        'flow_interrupt': "标定流程已中断",
        'flow_complete': "\n✅ 标定流程完成，成功标定 {} 个档位",
        'start_interp': "\n🔄 开始线性插值...",
        'interp_complete': "\n✅ 插值完成",
        'save_success': "\n💾 标定结果已保存到: {}",
        'save_fail': "❌ 保存失败: {}",
        'load_success': "✅ 标定结果已从 {} 加载",
        'load_fail': "❌ 加载失败: {}",
        'summary': "\n📈 标定摘要",
        'header': "{:<4} {:<12} {:<12}",
        'stats': "\n📈 统计信息:",
        'stats_detail': "  标定档位: {}\n  插值档位: {}\n  总计档位: 30",
        'config_missing': "⚠️  配置文件不存在: {}",
        'calib_method': "标定",
        'interp_method': "插值",
        
        # New keys
        'sys_title': "🤖 六足机器人30档速度交互式标定系统",
        'sys_funcs': "\n系统功能:",
        'sys_func1': "1. 交互式速度标定 - 逐档位进行精确标定",
        'sys_func2': "2. 支持线速度和角速度独立标定",
        'sys_func3': "3. 实时用户输入 - 根据实际测量输入速度值",
        'sys_func4': "4. 智能插值计算 - 自动计算未标定档位的速度",
        'sys_func5': "5. 数据保存加载 - 支持标定结果的持久化存储",
        'sys_ensure': "\n⚠️  使用前请确保:",
        'sys_ensure1': "- 机器人已正确连接并初始化",
        'sys_ensure2': "- 有足够的安全移动空间（建议3米以上）",
        'sys_ensure3': "- 准备好测量工具（卷尺、量角器等）",
        'sys_ensure4': "- 确保机器人电量充足",
        'select_func': "\n📋 请选择功能模式:",
        'func_linear': "1. 线速度标定 (m/s) - 测试前进后退左右平移速度",
        'func_angular': "2. 角速度标定 (deg/s) - 测试旋转速度",
        'func_load_angular': "3. 载入角速度标定文件到配置 - 从现有文件载入角速度数据",
        'func_load_linear': "4. 载入线速度标定文件到配置 - 从现有文件载入线速度数据",
        'select_mode_prompt': "\n请选择功能模式 [1/2/3/4]: ",
        'mode_linear_selected': "✅ 已选择线速度标定模式",
        'mode_angular_selected': "✅ 已选择角速度标定模式",
        'mode_load_angular_selected': "✅ 已选择载入角速度标定文件模式",
        'mode_load_linear_selected': "✅ 已选择载入线速度标定文件模式",
        'invalid_mode': "❌ 无效选择，请输入 1、2、3 或 4",
        'start_flow_msg': "\n🚀 开始标定流程...",
        'init_sys': "\n🔧 初始化标定系统...",
        'init_complete': "✅ 标定系统初始化完成 - {}标定模式",
        'congrats': "\n🎊 恭喜！标定完成！",
        'saved_to': "📁 结果已保存到: {}",
        'view_res_prompt': "\n是否查看标定结果摘要？(y/n): ",
        'show_res': "\n📖 显示标定结果:",
        'use_current': "✅ 使用刚完成的标定数据",
        'write_config_prompt': "\n是否将{}标定结果自动写入robot_config.json？(y/n): ",
        'write_success': "🎉 {}标定结果已成功写入配置文件！",
        'write_fail': "❌ 写入配置文件失败",
        'calib_incomplete': "\n⚠️  标定未完成或被取消",
        'retry_msg': "您可以稍后重新运行程序继续标定",
        'load_mode_title': "\n📂 载入{}标定文件模式",
        'no_files': "❌ 当前目录下未找到{}标定文件",
        'file_hint': "请确保文件名包含 '{}' 和 'calibration' 关键词",
        'found_files': "\n📋 找到以下{}标定文件:",
        'select_file_prompt': "\n请选择要载入的文件 [1-{}]: ",
        'file_selected': "✅ 已选择文件: {}",
        'invalid_file_choice': "❌ 无效选择，请输入 1 到 {} 之间的数字",
        'load_success_msg': "🎉 {}标定数据已成功载入到配置文件！",
        'load_fail_msg': "❌ 载入标定文件失败",
        'user_interrupt': "\n\n👋 用户中断，程序退出",
        'prog_error': "\n❌ 程序运行出错: {}",
        'thanks': "\n👋 感谢使用六足机器人标定系统！",
        
        # update_robot_config keys
        'update_angular': "\n🔄 更新角速度标定数据到配置文件...",
        'update_linear': "\n🔄 更新线速度标定数据到配置文件...",
        'config_updated': "✅ 配置文件已更新: {}",
        'data_updated': "📊 已更新 {} 个档位的数据",
        'update_fail': "❌ 更新配置文件失败: {}",
        'angular_comment': "角速度标定数据 (度/秒) Angular speed calibration data (deg/s)",
        
        # load_and_update keys
        'calib_file_missing': "❌ 标定文件不存在: {}",
        'calib_format_error': "❌ 标定文件格式错误: 缺少calibration_data或complete_table字段",
        'unknown_type': "❌ 未知的标定类型: {}",
        'load_angular_file': "\n🔄 从文件载入角速度标定数据: {}",
        'load_linear_file': "\n🔄 从文件载入线速度标定数据: {}",
        'load_file_fail': "❌ 载入标定文件失败: {}",
        'loaded_levels': "📊 已载入 {} 个档位的{}数据",
        
        # run_full_calibration keys
        'welcome_sys': "\n🎯 30档速度交互式标定系统",
        'welcome_msg': "\n欢迎使用六足机器人速度标定系统！",
        'sys_desc1': "\n本系统将帮助您标定机器人的30个速度档位。",
        'sys_desc2': "标定过程中，机器人会以不同档位移动3秒，",
        'sys_desc3': "您需要测量实际移动距离并输入系统。",
        'phase1': "\n📊 第一阶段：固定间隔档位标定",
        'phase1_levels': "我们将标定以下档位: {}",
        'phase1_fail': "❌ 固定间隔标定失败，无法继续",
        'phase1_done': "第一阶段完成！",
        'interp_prompt': "是否继续进行插值计算其他档位？(y/n): ",
        'phase2': "\n🔄 第二阶段：插值计算其他档位",
        'skip_interp': "跳过插值计算，仅保存已标定的档位数据",
        'save_prompt': "是否保存标定结果到文件？(y/n): ",
        'flow_done': "\n🎉 标定流程完成！",
        'patience_thanks': "感谢您的耐心配合！",
        'interrupt_msg': "\n\n⚠️  用户中断了标定流程",
        'save_partial_prompt': "是否保存已完成的标定数据？(y/n): ",
        'partial_saved': "✅ 部分标定数据已保存",
        'calib_error': "❌ 标定过程出错: {}"
    }
}

class SpeedCalibration30Levels:
    """
    30档速度标定器 (支持线速度和角速度)
    30-Level Speed Calibrator (Support Linear and Angular Speed)
    """
    
    def __init__(self, port: str = "/dev/myserial", debug: bool = True, calibration_type: str = "linear"):
        """
        初始化标定器
        Initialize calibrator
        
        Args:
            port: 串口端口 Serial port
            debug: 调试模式 Debug mode
            calibration_type: 标定类型 "linear" 或 "angular" Calibration type "linear" or "angular"
        """
        self.debug = debug
        self.robot = None
        self.calibration_data = {}  # 存储标定数据
        self.interpolated_data = {}  # 存储插值数据
        self.calibration_type = calibration_type  # 标定类型
        
        # 标定配置
        # 依据 muto_hexapod_lib 包分析：
        # 1. PathPlanning.gen_move_x 默认 radius=25，这是最常用的标准档位
        # 2. forward_fast 模式暗示了 30 左右的高速范围
        # 3. 15 作为低速参考点，用于插值计算
        if calibration_type == "linear":
            self.calibration_levels = [10, 20]  # 线速度标定档位
            self.calibration_distance_m = 0.5  # 线速度标定距离(米)
        else:  # angular
            self.calibration_levels = [10, 20]  # 角速度标定档位 (仅10-20有效)
            self.calibration_angle_deg = 360  # 角速度标定角度(度)
            
        self.calibration_repeats = 1  # 每个档位重复测试次数(改为1次)
        
        # 语言配置
        self.lang = os.environ.get('VOICE_LANGUAGE', 'en').lower()
        if self.lang != 'zh_cn':
            self.lang = 'en'
            
        # 文本资源
        self.text_res = TEXT_RES
        
        # 撤回功能支持
        self.calibration_history = []  # 标定历史记录，支持撤回
        self.input_history = []  # 输入历史，用于撤回功能
        
        # 初始化机器人
        try:
            self.robot = MutoController(port=port, debug=debug)
            print(self.text_res[self.lang]['init_success'])
        except Exception as e:
            print(self.text_res[self.lang]['init_fail'].format(e))
            raise
    
    def calibrate_single_level(self, level: int, test_param: float = None) -> Dict:
        """
        交互式标定单个档位（支持线速度和角速度标定）
        Interactive calibration of single speed level (support linear and angular speed)
        
        Args:
            level: 速度档位 Speed level (1-30)
            test_param: 测试参数 - 线速度时为距离(m)，角速度时为角度(deg)
            
        Returns:
            Dict: 标定结果 Calibration result
        """
        if test_param is None:
            if self.calibration_type == "linear":
                test_param = self.calibration_distance_m
            else:  # angular
                test_param = self.calibration_angle_deg
        
        calibration_name = self.text_res[self.lang]['calib_linear'] if self.calibration_type == "linear" else self.text_res[self.lang]['calib_angular']
        unit = self.text_res[self.lang]['unit_linear'] if self.calibration_type == "linear" else self.text_res[self.lang]['unit_angular']
        move_action = self.text_res[self.lang]['move'] if self.calibration_type == "linear" else self.text_res[self.lang]['rotate']
        
        print(self.text_res[self.lang]['start_calib'].format(calibration_name, level))
        print(self.text_res[self.lang]['select_mode'])
        print(self.text_res[self.lang]['mode_test'].format(move_action))
        print(self.text_res[self.lang]['mode_input'].format(calibration_name))
        print(self.text_res[self.lang]['mode_undo'])
        
        while True:
            choice = input(self.text_res[self.lang]['choice_prompt']).strip().lower()
            
            if choice == 'u':
                # 撤回功能
                if self.input_history:
                    last_input = self.input_history.pop()
                    if last_input['level'] in self.calibration_data:
                        del self.calibration_data[last_input['level']]
                    print(self.text_res[self.lang]['undo_success'].format(last_input['level']))
                    return None  # 返回None表示撤回操作
                else:
                    print(self.text_res[self.lang]['no_undo'])
                    continue
            
            elif choice == 'd':
                # 直接输入速度值
                while True:
                    try:
                        speed_input = input(self.text_res[self.lang]['input_prompt'].format(calibration_name, level, unit))
                        speed_value = float(speed_input)
                        if speed_value < 0:
                            print(self.text_res[self.lang]['neg_error'].format(calibration_name))
                            continue
                        
                        # 创建直接输入的结果
                        if self.calibration_type == "linear":
                            calibration_result = {
                                'level': level,
                                'avg_time_s': 3.0,
                                'avg_speed_ms': speed_value,
                                'std_speed_ms': 0.0,
                                'avg_distance_m': speed_value * 3.0,
                                'repeats': 1,
                                'raw_results': [{'speed_ms': speed_value, 'time_s': 3.0, 'distance_m': speed_value * 3.0}],
                                'timestamp': datetime.now().isoformat(),
                                'input_method': 'direct'
                            }
                        else:  # angular
                            calibration_result = {
                                'level': level,
                                'avg_time_s': 3.0,
                                'avg_angular_speed_deg_s': speed_value,
                                'std_angular_speed_deg_s': 0.0,
                                'avg_angle_deg': speed_value * 3.0,
                                'repeats': 1,
                                'raw_results': [{'angular_speed_deg_s': speed_value, 'time_s': 3.0, 'angle_deg': speed_value * 3.0}],
                                'timestamp': datetime.now().isoformat(),
                                'input_method': 'direct'
                            }
                        
                        # 记录到输入历史
                        self.input_history.append({
                            'level': level,
                            'result': calibration_result,
                            'method': 'direct'
                        })
                        
                        print(self.text_res[self.lang]['input_success'].format(level, speed_value, unit))
                        return calibration_result
                        
                    except ValueError:
                        print(self.text_res[self.lang]['invalid_num'])
            
            elif choice == '' or choice == '\n':
                # 机器人移动测试
                break
            else:
                print(self.text_res[self.lang]['invalid_choice'])
        
        # 执行机器人测试
        if self.calibration_type == "linear":
            print(self.text_res[self.lang]['test_linear_desc'].format(level))
        else:  # angular
            print(self.text_res[self.lang]['test_angular_desc'].format(level))
        
        if self.calibration_type == "linear":
            input(self.text_res[self.lang]['press_enter'])
        
        print(self.text_res[self.lang]['preparing'])
        time.sleep(1)  # 给用户准备时间
        
        # 记录开始时间
        start_time = time.time()
        
        # 执行测试
        try:
            if self.calibration_type == "linear":
                # 线速度测试：固定时间移动
                move_duration = 3.0  # 固定移动3秒
                end_time = start_time + move_duration
                
                print(self.text_res[self.lang]['start_move'])
                while time.time() < end_time:
                    if self.robot:
                        self.robot.move(level, 0, 0)  # 前进
                    time.sleep(0.05)  # 20Hz控制频率
                
                # 停止机器人
                if self.robot:
                    self.robot.move(0, 0, 0)
                print(self.text_res[self.lang]['move_done'])
                
                actual_time = time.time() - start_time
                
                # 询问用户实际移动距离
                while True:
                    try:
                        distance_input = input(self.text_res[self.lang]['input_dist'])
                        
                        if distance_input.strip().lower() == 'u':
                            print(self.text_res[self.lang]['cancel_test'])
                            return None
                        
                        actual_distance = float(distance_input)
                        if actual_distance < 0:
                            print(self.text_res[self.lang]['neg_error'].format("Distance"))
                            continue
                        break
                    except ValueError:
                        print(self.text_res[self.lang]['invalid_val'])
                        print(self.text_res[self.lang]['error_options'])
                        
                        error_choice = input(self.text_res[self.lang]['error_choice']).strip().lower()
                        
                        if error_choice == 'r':
                            continue  # 重新输入距离
                        elif error_choice == 'c':
                            print(self.text_res[self.lang]['re_calib'])
                            return self.calibrate_single_level(level, test_param)  # 递归重新标定
                        else:  # 默认选择：进入下一个档位
                            print(self.text_res[self.lang]['skip_level'])
                            return None  # 返回None表示跳过当前档位
                
                measured_speed = actual_distance / actual_time if actual_time > 0 else 0
                
            else:  # angular 角速度测试
                # 角速度测试：用户控制开始和停止
                print(self.text_res[self.lang]['test_angular_desc'].format(level))
                input(self.text_res[self.lang]['press_enter'])
                
                print(self.text_res[self.lang]['start_rotate'])
                start_time = time.time()  # 重新记录开始时间
                
                # 开始持续旋转，使用循环保持旋转状态
                rotation_active = True
                
                def rotation_loop():
                    while rotation_active and self.robot:
                        self.robot.move(0, 0, level)  # 持续发送旋转指令
                        time.sleep(0.05)  # 20Hz控制频率
                
                # 启动旋转线程
                if self.robot:
                    rotation_thread = threading.Thread(target=rotation_loop)
                    rotation_thread.daemon = True
                    rotation_thread.start()
                
                # 等待用户按回车停止
                input()  # 用户按回车停止旋转
                
                # 停止旋转
                rotation_active = False
                if self.robot:
                    self.robot.move(0, 0, 0)
                    time.sleep(0.1)  # 确保停止指令生效
                
                end_time = time.time()
                actual_time = end_time - start_time
                
                print(self.text_res[self.lang]['rotate_done'].format(actual_time))
                
                # 固定角度为360度
                actual_angle = 360.0
                measured_angular_speed = actual_angle / actual_time if actual_time > 0 else 0
            
            # 创建标定结果
            if self.calibration_type == "linear":
                calibration_result = {
                    'level': level,
                    'avg_time_s': actual_time,
                    'avg_speed_ms': measured_speed,
                    'std_speed_ms': 0.0,  # 单次测试无标准差
                    'avg_distance_m': actual_distance,
                    'repeats': 1,
                    'raw_results': [{
                        'time_s': actual_time,
                        'speed_ms': measured_speed,
                        'distance_m': actual_distance
                    }],
                    'timestamp': datetime.now().isoformat(),
                    'input_method': 'test'  # 标记为测试获得
                }
                
                print(self.text_res[self.lang]['test_result'])
                print(self.text_res[self.lang]['time_res'].format(actual_time))
                print(self.text_res[self.lang]['dist_res'].format(actual_distance))
                print(self.text_res[self.lang]['speed_res'].format(measured_speed))
                
            else:  # angular
                calibration_result = {
                    'level': level,
                    'avg_time_s': actual_time,
                    'avg_angular_speed_deg_s': measured_angular_speed,
                    'std_angular_speed_deg_s': 0.0,  # 单次测试无标准差
                    'avg_angle_deg': actual_angle,
                    'repeats': 1,
                    'raw_results': [{
                        'time_s': actual_time,
                        'angular_speed_deg_s': measured_angular_speed,
                        'angle_deg': actual_angle
                    }],
                    'timestamp': datetime.now().isoformat(),
                    'input_method': 'test'  # 标记为测试获得
                }
                
                print(self.text_res[self.lang]['test_result'])
                print(self.text_res[self.lang]['time_res'].format(actual_time))
                print(self.text_res[self.lang]['angle_res'].format(actual_angle))
                print(self.text_res[self.lang]['ang_speed_res'].format(measured_angular_speed))
            
            # 记录到输入历史
            self.input_history.append({
                'level': level,
                'result': calibration_result,
                'method': 'test'
            })
            
            return calibration_result
            
        except Exception as e:
            print(self.text_res[self.lang]['test_error'].format(e))
            return None
    
    def calibrate_fixed_levels(self) -> Dict:
        """
        交互式标定固定间隔的档位
        Interactive calibration of fixed interval levels
        
        Returns:
            Dict: 标定结果 Calibration results
        """
        print(self.text_res[self.lang]['start_flow'])
        print(self.text_res[self.lang]['levels_info'].format(self.calibration_levels))
        print(self.text_res[self.lang]['repeats_info'].format(self.calibration_repeats))
        print(self.text_res[self.lang]['notes'])
        
        input("\n" + self.text_res[self.lang]['press_enter'])
        
        calibration_results = {}
        
        for i, level in enumerate(self.calibration_levels):
            print(self.text_res[self.lang]['progress'].format(i+1, len(self.calibration_levels), level))
            
            result = self.calibrate_single_level(level)
            if result:
                calibration_results[level] = result
                # 根据标定类型使用不同的字段
                if self.calibration_type == "linear":
                    self.calibration_data[level] = result['avg_speed_ms']
                else:  # angular
                    self.calibration_data[level] = result['avg_angular_speed_deg_s']
                print(self.text_res[self.lang]['calib_success'].format(level))
            else:
                print(self.text_res[self.lang]['calib_fail'].format(level))
                retry = input(self.text_res[self.lang]['retry_prompt'])
                if retry.lower() == 'y':
                    result = self.calibrate_single_level(level)
                    if result:
                        calibration_results[level] = result
                        # 根据标定类型使用不同的字段
                        if self.calibration_type == "linear":
                            self.calibration_data[level] = result['avg_speed_ms']
                        else:  # angular
                            self.calibration_data[level] = result['avg_angular_speed_deg_s']
                        print(self.text_res[self.lang]['re_calib_success'].format(level))
            
            # 询问是否继续
            if i < len(self.calibration_levels) - 1:
                continue_calibration = input(self.text_res[self.lang]['continue_prompt'].format(self.calibration_levels[i+1]))
                if continue_calibration.lower() != 'y':
                    print(self.text_res[self.lang]['flow_interrupt'])
                    break
        
        print(self.text_res[self.lang]['flow_complete'].format(len(calibration_results)))
        
        return calibration_results
    
    def interpolate_missing_levels(self) -> Dict:
        """
        基于运动控制物理特性的线性插值计算
        Linear interpolation based on movement control physics
        
        Returns:
            Dict: 插值结果 Interpolation results
        """
        print(self.text_res[self.lang]['start_interp'])
        
        if len(self.calibration_data) < 2:
            return {}
            
        interpolated_results = {}
        
        # 确保有基准点 (0, 0)
        # Ensure base point (0, 0) exists
        if 0 not in self.calibration_data:
            self.calibration_data[0] = 0.0
            
        # 获取排序后的标定点
        # Get sorted calibration points
        sorted_levels = sorted(self.calibration_data.keys())
        
        # 目标插值范围
        # Target interpolation range
        target_range = range(1, 31)
        
        for target_level in target_range:
            if target_level in self.calibration_data:
                continue
                
            # 找到插值区间
            # Find interpolation interval
            lower_level = None
            upper_level = None
            
            for level in sorted_levels:
                if level < target_level:
                    lower_level = level
                elif level > target_level:
                    upper_level = level
                    break
            
            final_speed = 0.0
            
            if lower_level is not None and upper_level is not None:
                # 区间内线性插值
                # Linear interpolation within interval
                lower_speed = self.calibration_data[lower_level]
                upper_speed = self.calibration_data[upper_level]
                
                # y = y1 + (x - x1) * (y2 - y1) / (x2 - x1)
                slope = (upper_speed - lower_speed) / (upper_level - lower_level)
                final_speed = lower_speed + (target_level - lower_level) * slope
                
            elif lower_level is not None:
                # 向上外推 (使用最后两个点的斜率)
                # Extrapolate upwards (use slope of last two points)
                if len(sorted_levels) >= 2:
                    l1 = sorted_levels[-2]
                    l2 = sorted_levels[-1]
                    s1 = self.calibration_data[l1]
                    s2 = self.calibration_data[l2]
                    slope = (s2 - s1) / (l2 - l1)
                    final_speed = s2 + (target_level - l2) * slope
                else:
                    # 只有一个点，假设通过原点
                    # Only one point, assume passing through origin
                    slope = self.calibration_data[lower_level] / lower_level if lower_level > 0 else 0
                    final_speed = target_level * slope
                    
            elif upper_level is not None:
                # 向下外推 (使用0到第一个点的斜率)
                # Extrapolate downwards (use slope from 0 to first point)
                slope = self.calibration_data[upper_level] / upper_level if upper_level > 0 else 0
                final_speed = target_level * slope
            
            # 确保速度非负
            # Ensure non-negative speed
            final_speed = max(0.0, final_speed)
            
            interpolated_results[target_level] = final_speed
            self.interpolated_data[target_level] = final_speed
            
        print(self.text_res[self.lang]['interp_complete'])
        return interpolated_results

    
    def generate_complete_calibration_table(self) -> Dict:
        """
        生成完整的标定表
        角速度标定：仅生成10-20档位的标定表
        线速度标定：生成完整的30档标定表
        Generate complete calibration table
        Angular calibration: only generate 10-20 level calibration table
        Linear calibration: generate complete 30-level calibration table
        
        Returns:
            Dict: 完整标定表 Complete calibration table
        """
        complete_table = {}
        
        # 根据标定类型确定范围 - 统一为1-30
        level_range = range(1, 31)
        
        # 合并标定数据和插值数据
        for level in level_range:
            if level in self.calibration_data:
                speed_value = self.calibration_data[level]
                complete_table[level] = {
                    'speed_ms' if self.calibration_type == "linear" else 'angular_speed_deg_s': speed_value,
                    'source': 'calibrated'
                }
            elif level in self.interpolated_data:
                speed_value = self.interpolated_data[level]
                complete_table[level] = {
                    'speed_ms' if self.calibration_type == "linear" else 'angular_speed_deg_s': speed_value,
                    'source': 'interpolated'
                }
            else:
                # 使用线性估算
                if self.calibration_type == "angular":
                    estimated_speed = level * 2.0  # 角速度估算：每档位约2度/秒
                else:
                    estimated_speed = level * 0.01  # 线速度估算：每档位约0.01m/s
                complete_table[level] = {
                    'speed_ms' if self.calibration_type == "linear" else 'angular_speed_deg_s': estimated_speed,
                    'source': 'estimated'
                }
        
        return complete_table
    
    def save_calibration_results(self, filename: str = None) -> str:
        """
        保存标定结果
        Save calibration results
        
        Args:
            filename: 文件名 Filename
            
        Returns:
            str: 保存的文件路径 Saved file path
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            calibration_prefix = "linear" if self.calibration_type == "linear" else "angular"
            filename = f"{calibration_prefix}_speed_calibration_30levels_{timestamp}.json"
        
        # 生成完整标定表
        complete_table = self.generate_complete_calibration_table()
        
        # 准备保存数据
        metadata = {
            'calibration_type': self.calibration_type,
            'timestamp': datetime.now().isoformat(),
            'calibration_levels': self.calibration_levels,
            'calibration_repeats': self.calibration_repeats,
            'total_levels': 30
        }
        
        # 只有线速度标定才需要calibration_distance_m
        if self.calibration_type == "linear" and hasattr(self, 'calibration_distance_m'):
            metadata['calibration_distance_m'] = self.calibration_distance_m
        
        save_data = {
            'metadata': metadata,
            'calibrated_data': self.calibration_data,
            'interpolated_data': self.interpolated_data,
            'complete_table': complete_table
        }
        
        # 保存到文件
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, indent=2, ensure_ascii=False)
            
            print(self.text_res[self.lang]['saved_to'].format(filename))
            return filename
            
        except Exception as e:
            print(self.text_res[self.lang]['save_fail'].format(e))
            return None
    
    def load_calibration_results(self, filename: str) -> bool:
        """
        加载标定结果
        Load calibration results
        
        Args:
            filename: 文件名 Filename
            
        Returns:
            bool: 加载是否成功 Whether loading was successful
        """
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self.calibration_data = data.get('calibrated_data', {})
            self.interpolated_data = data.get('interpolated_data', {})
            
            # 转换键为整数
            self.calibration_data = {int(k): v for k, v in self.calibration_data.items()}
            self.interpolated_data = {int(k): v for k, v in self.interpolated_data.items()}
            
            print(self.text_res[self.lang]['load_success'].format(filename))
            return True
            
        except Exception as e:
            print(self.text_res[self.lang]['load_fail'].format(e))
            return False
    
    def print_calibration_summary(self):
        """
        打印标定结果摘要
        Print calibration results summary
        """
        print(self.text_res[self.lang]['summary'])
        
        complete_table = self.generate_complete_calibration_table()
        
        # 根据标定类型确定速度键名和单位
        if self.calibration_type == "angular":
            speed_key = 'angular_speed_deg_s'
            speed_unit = self.text_res[self.lang]['unit_angular']
        else:
            speed_key = 'speed_ms'
            speed_unit = self.text_res[self.lang]['unit_linear']
        
        print(self.text_res[self.lang]['header'].format("Lvl", speed_unit, "Src"))
        print("-" * 36)
        
        for level in range(1, 31):
            if level in complete_table:
                speed = complete_table[level][speed_key]
                source = complete_table[level]['source']
                source_cn = {
                    'calibrated': self.text_res[self.lang]['calib_method'], 
                    'interpolated': self.text_res[self.lang]['interp_method'], 
                    'estimated': 'Est'
                }[source]
                print(f"{level:<4} {speed:<12.3f} {source_cn:<12}")
        
        print(self.text_res[self.lang]['stats'])
        calibrated_count = len(self.calibration_data)
        interpolated_count = len(self.interpolated_data)
        
        print(self.text_res[self.lang]['stats_detail'].format(calibrated_count, interpolated_count))
    
    def update_robot_config(self, config_path: str = "config/robot_config.json") -> bool:
        """
        将标定结果自动写入robot_config.json文件
        Automatically write calibration results to robot_config.json file
        
        Args:
            config_path: Config file path Config file path
            
        Returns:
            bool: 是否成功更新 Whether update was successful
        """
        try:
            # 生成完整标定表
            complete_table = self.generate_complete_calibration_table()
            
            # 读取现有配置文件
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
            else:
                print(self.text_res[self.lang]['config_missing'].format(config_path))
                return False
            
            # 根据标定类型更新对应的配置节
            if self.calibration_type == "angular":
                config_key = "angular_speed_calibration_30_levels"
                speed_key = "angular_speed_deg_s"
                print(self.text_res[self.lang]['update_angular'])
            else:
                config_key = "linear_speed_calibration_30_levels"
                speed_key = "speed_ms"
                print(self.text_res[self.lang]['update_linear'])
            
            # 准备更新数据
            calibration_data = {}
            if self.calibration_type == "angular":
                calibration_data["comment"] = self.text_res[self.lang]['angular_comment']
            
            for level in range(1, 31):
                if level in complete_table:
                    calibration_data[str(level)] = complete_table[level][speed_key]
            
            # 更新配置文件
            config_data[config_key] = calibration_data
            
            # 保存配置文件
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)
            
            print(self.text_res[self.lang]['config_updated'].format(config_path))
            print(self.text_res[self.lang]['data_updated'].format(len(calibration_data)-1 if 'comment' in calibration_data else len(calibration_data)))
            return True
            
        except Exception as e:
            print(self.text_res[self.lang]['update_fail'].format(e))
            return False
    
    def load_and_update_config_from_file(self, calibration_file: str, config_path: str = "config/robot_config.json") -> bool:
        """
        从指定的标定文件载入数据并更新到robot_config.json
        Load calibration data from specified file and update robot_config.json
        
        Args:
            calibration_file: 标定文件路径 Calibration file path
            config_path: Config file path Config file path
            
        Returns:
            bool: 是否成功更新 Whether update was successful
        """
        try:
            # 检查标定文件是否存在
            if not os.path.exists(calibration_file):
                print(self.text_res[self.lang]['calib_file_missing'].format(calibration_file))
                return False
            
            # 载入标定文件
            with open(calibration_file, 'r', encoding='utf-8') as f:
                calibration_data = json.load(f)
            
            # 检查标定文件格式 - 支持两种格式
            if 'calibration_data' not in calibration_data and 'complete_table' not in calibration_data:
                print(self.text_res[self.lang]['calib_format_error'])
                return False
            
            # 检查标定类型
            calibration_type = calibration_data.get('metadata', {}).get('calibration_type', 'unknown')
            if calibration_type not in ['linear', 'angular']:
                print(self.text_res[self.lang]['unknown_type'].format(calibration_type))
                return False
            
            # 读取现有配置文件
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
            else:
                print(self.text_res[self.lang]['config_missing'].format(config_path))
                return False
            
            # 根据标定类型确定配置键名
            if calibration_type == "angular":
                config_key = "angular_speed_calibration_30_levels"
                speed_key = "angular_speed_deg_s"
                print(self.text_res[self.lang]['load_angular_file'].format(calibration_file))
            else:
                config_key = "linear_speed_calibration_30_levels"
                speed_key = "speed_ms"
                print(self.text_res[self.lang]['load_linear_file'].format(calibration_file))
            
            # 准备更新数据
            new_calibration_data = {}
            if calibration_type == "angular":
                new_calibration_data["comment"] = self.text_res[self.lang]['angular_comment']
            
            # 转换标定数据格式 - 支持两种数据格式
            if 'complete_table' in calibration_data:
                # 新格式：使用complete_table
                for level_str, level_data in calibration_data['complete_table'].items():
                    if speed_key in level_data:
                        new_calibration_data[level_str] = level_data[speed_key]
            elif 'calibration_data' in calibration_data:
                # 旧格式：使用calibration_data
                for level_str, level_data in calibration_data['calibration_data'].items():
                    if speed_key in level_data:
                        new_calibration_data[level_str] = level_data[speed_key]
            
            # 更新配置文件
            config_data[config_key] = new_calibration_data
            
            # 保存配置文件
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)
            
            print(self.text_res[self.lang]['config_updated'].format(config_path))
            calib_type_name = self.text_res[self.lang]['calib_angular'] if calibration_type == 'angular' else self.text_res[self.lang]['calib_linear']
            print(self.text_res[self.lang]['loaded_levels'].format(len(new_calibration_data)-1 if 'comment' in new_calibration_data else len(new_calibration_data), calib_type_name))
            return True
            
        except Exception as e:
            print(self.text_res[self.lang]['load_file_fail'].format(e))
            return False
    
    def run_full_calibration(self) -> str:
        """
        运行完整的交互式标定流程
        Run complete interactive calibration process
        
        Returns:
            str: 保存的文件路径 Saved file path
        """
        print(self.text_res[self.lang]['welcome_sys'])
        print("=" * 50)
        print(self.text_res[self.lang]['welcome_msg'])
        print(self.text_res[self.lang]['sys_desc1'])
        print(self.text_res[self.lang]['sys_desc2'])
        print(self.text_res[self.lang]['sys_desc3'])
        print(self.text_res[self.lang]['start_flow_msg'])
        
        try:
            # 1. 标定固定间隔档位
            print(self.text_res[self.lang]['phase1'])
            print(self.text_res[self.lang]['phase1_levels'].format(self.calibration_levels))
            calibration_results = self.calibrate_fixed_levels()
            
            if not calibration_results:
                print(self.text_res[self.lang]['phase1_fail'])
                return None
            
            # 自动进行插值计算
            # Automatically perform interpolation
            print("\n" + "="*50)
            print(self.text_res[self.lang]['phase1_done'])
            
            # 2. 插值计算其他档位
            # 2. Interpolate other levels
            print(self.text_res[self.lang]['phase2'])
            self.interpolate_missing_levels()
            
            # 3. 打印摘要
            self.print_calibration_summary()
            
            # 4. 保存结果
            print("\n" + self.text_res[self.lang]['save_success'].format(""))
            save_results = input(self.text_res[self.lang]['save_prompt'])
            filename = None
            if save_results.lower() == 'y':
                filename = self.save_calibration_results()
            
            print(self.text_res[self.lang]['flow_done'])
            print(self.text_res[self.lang]['patience_thanks'])
            return filename
            
        except KeyboardInterrupt:
            print(self.text_res[self.lang]['interrupt_msg'])
            save_partial = input(self.text_res[self.lang]['save_partial_prompt'])
            if save_partial.lower() == 'y':
                filename = self.save_calibration_results()
                if filename:
                    print(self.text_res[self.lang]['partial_saved'])
                return filename
            return None
        except Exception as e:
            print(self.text_res[self.lang]['calib_error'].format(e))
            import traceback
            traceback.print_exc()
            return None

def main():
    """
    主函数
    Main function
    """
    # 语言配置
    lang = os.environ.get('VOICE_LANGUAGE', 'en').lower()
    if lang != 'zh_cn':
        lang = 'en'
    
    # 获取文本资源
    text = TEXT_RES[lang]
    
    print(text['sys_title'])
    print("=" * 50)
    print(text['sys_funcs'])
    print(text['sys_func1'])
    print(text['sys_func2'])
    print(text['sys_func3'])
    print(text['sys_func4'])
    print(text['sys_func5'])
    
    print(text['sys_ensure'])
    print(text['sys_ensure1'])
    print(text['sys_ensure2'])
    print(text['sys_ensure3'])
    print(text['sys_ensure4'])
    
    # 选择功能模式
    print(text['select_func'])
    print(text['func_linear'])
    print(text['func_angular'])
    print(text['func_load_angular'])
    print(text['func_load_linear'])
    
    while True:
        mode_choice = input(text['select_mode_prompt']).strip()
        if mode_choice == '1':
            calibration_type = "linear"
            mode = "calibrate"
            print(text['mode_linear_selected'])
            break
        elif mode_choice == '2':
            calibration_type = "angular"
            mode = "calibrate"
            print(text['mode_angular_selected'])
            break
        elif mode_choice == '3':
            calibration_type = "angular"
            mode = "load_file"
            print(text['mode_load_angular_selected'])
            break
        elif mode_choice == '4':
            calibration_type = "linear"
            mode = "load_file"
            print(text['mode_load_linear_selected'])
            break
        else:
            print(text['invalid_mode'])
    
    try:
        if mode == "calibrate":
            # 标定模式
            print(text['start_flow_msg'])
            
            # 初始化标定器
            print(text['init_sys'])
            calibrator = SpeedCalibration30Levels(debug=True, calibration_type=calibration_type)
            # 使用init_complete格式化，这里简单处理
            calib_type_name = text['calib_linear'] if calibration_type == 'linear' else text['calib_angular']
            print(text['init_complete'].format(calib_type_name))
            
            # 运行完整标定
            result_file = calibrator.run_full_calibration()
            
            if result_file:
                print(text['congrats'])
                print(text['saved_to'].format(result_file))
                
                # 询问是否查看结果
                view_results = input(text['view_res_prompt'])
                if view_results.lower() == 'y':
                    print(text['show_res'])
                    print(text['use_current'])
                    
                    # 直接使用当前标定器实例显示结果
                    calibrator.print_calibration_summary()
                
                # 询问是否自动写入配置文件
                calib_type_name = text['calib_linear'] if calibrator.calibration_type == 'linear' else text['calib_angular']
                write_config = input(text['write_config_prompt'].format(calib_type_name))
                if write_config.lower() == 'y':
                    if calibrator.update_robot_config():
                        print(text['write_success'].format(calib_type_name))
                    else:
                        print(text['write_fail'])
            else:
                print(text['calib_incomplete'])
                print(text['retry_msg'])
                
        elif mode == "load_file":
            # 载入文件模式
            calib_type_name = text['calib_angular'] if calibration_type == 'angular' else text['calib_linear']
            print(text['load_mode_title'].format(calib_type_name))
            
            # 列出当前目录下的标定文件
            import glob
            pattern = f"*{calibration_type}*calibration*.json"
            calibration_files = glob.glob(pattern)
            
            if not calibration_files:
                print(text['no_files'].format(calib_type_name))
                print(text['file_hint'].format(calibration_type))
                return
            
            print(text['found_files'].format(calib_type_name))
            for i, file in enumerate(calibration_files, 1):
                print(f"{i}. {file}")
            
            # 让用户选择文件
            while True:
                try:
                    file_choice = input(text['select_file_prompt'].format(len(calibration_files))).strip()
                    file_index = int(file_choice) - 1
                    if 0 <= file_index < len(calibration_files):
                        selected_file = calibration_files[file_index]
                        print(text['file_selected'].format(selected_file))
                        break
                    else:
                        print(text['invalid_file_choice'].format(len(calibration_files)))
                except ValueError:
                    print(text['invalid_num'])
            
            # 创建标定器实例并载入文件
            calibrator = SpeedCalibration30Levels(debug=True, calibration_type=calibration_type)
            
            if calibrator.load_and_update_config_from_file(selected_file):
                print(text['load_success_msg'].format(calib_type_name))
            else:
                print(text['load_fail_msg'])
            
    except KeyboardInterrupt:
        print(text['user_interrupt'])
    except Exception as e:
        print(text['prog_error'].format(e))
        import traceback
        traceback.print_exc()
    
    print(text['thanks'])

if __name__ == "__main__":
    main()
