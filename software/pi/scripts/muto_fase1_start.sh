#!/bin/bash
# Muto RS - Fase 1 opstartsequentie (LiDAR + EKF + RTAB-Map, geen camera)
# Gebaseerd op sessie A6/A7, geverifieerd werkend 28 juli 2026

C=humble_run
R="source /opt/ros/humble/setup.bash && export CYCLONEDDS_URI=file:///root/cyclone_dds.xml"
L="source /root/yahboomcar_ros2_ws/software/library_ws_humble/install/setup.bash"
N="source /root/yahboomcar_ros2_ws/yahboomcar_ws/install/setup.bash"

echo "=== app_muto.py killen (blokkeert seriële poort) ==="
pkill -f app_muto.py 2>/dev/null
sleep 1

echo "=== STAP 1: LiDAR ==="
docker exec -d $C bash -c "$R && $L && ros2 launch ydlidar_ros2_driver ydlidar_launch.py >/tmp/ydlidar.log 2>&1"
sleep 8
docker exec $C bash -c "$R && ros2 topic list 2>/dev/null | grep ^/scan$" && echo 'LiDAR actief' || echo 'FOUT LiDAR'

echo "=== STAP 2: Scan timestamp fix ==="
docker exec -d $C bash -c "$R && exec python3 /root/scan_timestamped.py > /tmp/scan_fix.log 2>&1"
sleep 2

echo "=== STAP 3: robot_state_publisher + joint_state_publisher (officieel URDF, vervangt handmatige static TF's) ==="
docker exec -d $C bash -c "$R && $N && exec ros2 launch /root/robot_state_launch.py > /tmp/robot_state.log 2>&1"
sleep 3
docker exec $C bash -c "$R && ros2 topic list 2>/dev/null | grep ^/tf_static$" && echo 'robot_state_publisher actief' || echo 'FOUT robot_state_publisher'

echo "=== STAP 4: rf2o ==="
docker exec -d $C bash -c "$R && $N && exec ros2 launch rf2o_laser_odometry rf2o_laser_odometry.launch.py > /tmp/rf2o.log 2>&1"
sleep 6
docker exec $C bash -c "$R && ros2 topic list 2>/dev/null | grep ^/odom$" && echo 'rf2o actief' || echo 'FOUT rf2o'

echo "=== STAP 5: IMU publisher (TF komt nu uit URDF/robot_state_publisher, STAP 3) ==="
docker exec -d $C bash -c "$R && exec python3 /root/imu_publisher.py > /tmp/imu.log 2>&1"
sleep 3

echo "=== STAP 6: EKF ==="
docker exec -d $C bash -c "$R && exec ros2 run robot_localization ekf_node --ros-args -r __node:=ekf_filter_node -r /odometry/filtered:=/odom_fused --params-file /root/yahboomcar_ros2_ws/ekf_params.yaml > /tmp/ekf.log 2>&1"
sleep 5
docker exec $C bash -c "$R && ros2 topic list 2>/dev/null | grep ^/odom_fused$" && echo 'EKF actief' || echo 'FOUT EKF'

echo "=== STAP 7: (base_footprint TF komt nu uit URDF/robot_state_publisher, STAP 3) ==="

echo "=== STAP 8: driver (\$DRIVER, default muto_driver_fixed) ==="
# DRIVER=phoenix_driver bash muto_fase1_start.sh   -> gebruikt phoenix_driver.py
#                                                      (tripod-gait i.p.v. STM32-firmware-gait,
#                                                       zie GAIT.md "Nav2-integratie")
# Default (geen DRIVER meegegeven) blijft ongewijzigd muto_driver_fixed.py --
# phoenix_driver.py is een bewuste, terugdraaibare keuze, geen vervanging.
DRIVER="${DRIVER:-muto_driver_fixed}"
if [[ "$DRIVER" != "muto_driver_fixed" && "$DRIVER" != "phoenix_driver" ]]; then
  echo "FOUT: onbekende DRIVER='$DRIVER' (verwacht muto_driver_fixed of phoenix_driver)"
  exit 1
fi
ALREADY_RUNNING=$(docker exec $C bash -c "ps -eo cmd | grep -E 'muto_driver_fixed.py|phoenix_driver.py' | grep -v grep")
if [ -n "$ALREADY_RUNNING" ]; then
  echo "driver draait al, niet opnieuw gestart: $ALREADY_RUNNING"
else
  docker exec -d $C bash -c "$R && exec python3 /root/${DRIVER}.py > /tmp/${DRIVER}.log 2>&1"
  sleep 3
fi
docker exec $C bash -c "ps -eo pid,cmd | grep -E 'muto_driver_fixed.py|phoenix_driver.py' | grep -v grep" && echo "driver actief ($DRIVER)" || echo 'FOUT driver'

echo "=== STAP 9: joy_node + yahboom_joy ==="
docker exec -d $C bash -c "$R && $N && exec ros2 launch yahboomcar_ctrl yahboomcar_joy_launch.py > /tmp/joy.log 2>&1"
sleep 4
docker exec $C bash -c "$R && ros2 topic list 2>/dev/null | grep -E '^/(joy|cmd_vel)$'"

echo "=== STAP 10: Foxglove Bridge ==="
docker exec $C bash -c "cat > /root/start_foxglove.sh << 'INNER_EOF'
#!/bin/bash
source /opt/ros/humble/setup.bash
exec ros2 launch foxglove_bridge foxglove_bridge_launch.xml \\
  port:=8765 \\
  topic_whitelist:=\"['/scan_fixed', '/tf', '/tf_static', '/odom_fused', '/rosout', '/map']\" \\
  num_threads:=2 \\
  sysinfo:=false \\
  send_buffer_limit:=2000000
INNER_EOF
chmod +x /root/start_foxglove.sh"
docker exec -d $C bash -c "exec /root/start_foxglove.sh > /tmp/foxglove_bridge.log 2>&1"
sleep 6
FOXGLOVE=$(docker exec $C bash -c "python3 -c \"import socket; s=socket.socket(); s.settimeout(2); print('OPEN' if s.connect_ex(('127.0.0.1',8765))==0 else 'DICHT')\"" 2>/dev/null || echo 'DICHT')
[ "$FOXGLOVE" = "OPEN" ] && echo 'Foxglove actief (ws://192.168.68.88:8765)' || echo 'WAARSCHUWING: Foxglove niet bereikbaar'

echo ""
echo "========================================="
echo "Fase 1 basis-stack opgestart."
echo "Volgende stap: RTAB-Map starten (los commando, zie projectnotities)"
echo "  of Nav2: hexapod_navigation.launch.py"
echo "========================================="
