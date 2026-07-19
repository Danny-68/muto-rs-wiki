#!/bin/bash

# WiFi连接脚本 / WiFi Connection Script
# 断开当前WiFi并连接到指定网络 / Disconnect current WiFi and connect to specified network

# 配置变量 / Configuration Variables
WIFI_NAME="ORBI90"          # 目标WiFi网络名称 / Target WiFi network name
WIFI_PASSWORD="orangefinch585"              # WiFi密码 / WiFi password
INTERFACE="wlan0"             # 网络接口名称，根据系统调整 / Network interface name, adjust according to your system

# 双语输出函数 / Bilingual output function
print_message() {
    local cn="$1"    # 中文消息 / Chinese message
    local en="$2"    # 英文消息 / English message
    echo "$cn"
    echo "$en"
    echo "----------------------------------------"
}

print_message "开始WiFi连接脚本..." "Starting WiFi connection script..."

# 检查是否有sudo权限 / Check for sudo privileges
if [ "$EUID" -ne 0 ]; then
    print_message "需要sudo权限来执行网络操作" "Root privileges required for network operations"
    print_message "请使用: sudo $0" "Please use: sudo $0"
    exit 1
fi

# 断开当前WiFi连接 / Disconnect current WiFi connection
print_message "正在断开WiFi连接..." "Disconnecting WiFi connection..."
nmcli dev disconnect $INTERFACE

# 检查断开操作结果 / Check disconnection result
if [ $? -eq 0 ]; then
    print_message "WiFi已成功断开" "WiFi disconnected successfully"
else
    print_message "断开WiFi时出现错误，继续尝试连接..." "Error disconnecting WiFi, continuing with connection attempt..."
fi

# 等待网络状态稳定 / Wait for network state to stabilize
sleep 1

# 扫描可用网络 / Scan for available networks
print_message "正在扫描可用网络..." "Scanning for available networks..."
nmcli dev wifi rescan

# 等待扫描完成 / Wait for scan completion
sleep 2

# 检查目标网络是否可用 / Check if target network is available
print_message "检查网络 '$WIFI_NAME' 是否可用..." "Checking if network '$WIFI_NAME' is available..."

# 搜索目标网络 / Search for target network
if nmcli dev wifi list | grep -q "$WIFI_NAME"; then
    print_message "找到网络 '$WIFI_NAME'" "Network '$WIFI_NAME' found"
else
    print_message "警告: 未找到网络 '$WIFI_NAME'，但仍尝试连接..." "Warning: Network '$WIFI_NAME' not found, but still attempting connection..."
fi

# 连接到指定WiFi / Connect to specified WiFi
print_message "正在连接到 '$WIFI_NAME'..." "Connecting to '$WIFI_NAME'..."

# 执行连接命令 / Execute connection command
if [ -z "$WIFI_PASSWORD" ]; then
    # 连接到开放网络 / Connect to open network
    nmcli dev wifi connect "$WIFI_NAME"
else
    # 连接到加密网络 / Connect to encrypted network
    nmcli dev wifi connect "$WIFI_NAME" password "$WIFI_PASSWORD"
fi

# 检查连接结果 / Check connection result
if [ $? -eq 0 ]; then
    print_message "成功连接到 '$WIFI_NAME'" "Successfully connected to '$WIFI_NAME'"
    
    # 显示连接状态 / Display connection status
    echo "当前连接状态 / Current connection status:"
    nmcli connection show --active | grep wifi
    echo ""
    
    # 显示IP地址信息 / Display IP address information
    echo "IP地址信息 / IP address information:"
    ip addr show $INTERFACE | grep inet
    echo ""
    
    # 测试网络连通性 / Test network connectivity
    print_message "测试网络连通性..." "Testing network connectivity..."
    if ping -c 3 8.8.8.8 >/dev/null 2>&1; then
        print_message "网络连接正常" "Network connection is working"
    else
        print_message "警告: 网络可能无法访问互联网" "Warning: Network may not have internet access"
    fi
    
else
    # 连接失败处理 / Connection failure handling
    print_message "连接失败!" "Connection failed!"
    echo "可能的原因 / Possible reasons:"
    echo "1. 网络不在范围内 / Network out of range"
    echo "2. 密码错误 / Incorrect password"
    echo "3. 网络配置问题 / Network configuration issues"
    echo "4. 接口名称错误 / Incorrect interface name"
    echo ""
    
    # 显示可用网络列表 / Show available networks list
    echo "可用网络列表 / Available networks:"
    nmcli dev wifi list
    
    exit 1
fi

print_message "WiFi连接脚本完成" "WiFi connection script completed"

# 脚本使用说明 / Script usage instructions
cat << EOF

使用说明 / Usage Instructions:
=====================================
1. 修改脚本中的WIFI_NAME变量为目标网络名称
   Modify the WIFI_NAME variable to your target network name

2. 如果网络有密码，设置WIFI_PASSWORD变量
   If the network has a password, set the WIFI_PASSWORD variable

3. 根据系统调整INTERFACE变量（通常是wlan0或wlp3s0等）
   Adjust the INTERFACE variable according to your system (usually wlan0 or wlp3s0, etc.)

4. 使用sudo权限运行脚本
   Run the script with sudo privileges

示例 / Example:
sudo $0

EOF

