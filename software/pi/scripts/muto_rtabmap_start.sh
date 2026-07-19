# PI ONLY - dual board versie v2
C=humble_run
R="source /opt/ros/humble/setup.bash && export CYCLONEDDS_URI=file:///root/cyclone_dds.xml"
L="source /root/yahboomcar_ros2_ws/software/library_ws_humble/install/setup.bash"
N="source /root/yahboomcar_ros2_ws/yahboomcar_ws/install/setup.bash"

echo '=== STAP 0: Webserver stoppen + container herstarten ==='
pkill -f 'python3 -m http.server' 2>/dev/null || true
sleep 1
docker restart $C
sleep 8
echo 'Container herstart'

echo '=== STAP 1: LiDAR ==='
docker exec -d $C bash -c "$R && $L && ros2 launch ydlidar_ros2_driver ydlidar_launch.py > /tmp/ydlidar.log 2>&1"
sleep 8
SCAN=$(docker exec $C bash -c "$R && ros2 topic list 2>/dev/null | grep ^/scan$" 2>/dev/null || echo '')
if [ -z "$SCAN" ]; then echo 'FOUT: /scan niet beschikbaar'; exit 1; fi
echo 'LiDAR actief'

echo '=== STAP 2: Camera ==='
docker exec -d $C bash -c "$R && $L && ros2 launch astra_camera astro_pro_plus.launch.xml > /tmp/camera.log 2>&1"
sleep 12
CAM=$(docker exec $C bash -c "$R && ros2 topic list 2>/dev/null | grep camera/color/image_raw$" 2>/dev/null || echo '')
if [ -z "$CAM" ]; then echo 'FOUT: camera niet beschikbaar'; exit 1; fi
echo 'Camera actief op 30fps (standaard)'

echo '=== STAP 3: RGBD sync ==='
docker exec -d $C bash -c "$R && $N && exec ros2 run rtabmap_sync rgbd_sync   --ros-args   -p approx_sync:=true   -p approx_sync_max_interval:=0.5   -p topic_queue_size:=5   -p sync_queue_size:=5   -p qos:=1   --remap rgb/image:=/camera/color/image_raw   --remap rgb/camera_info:=/camera/color/camera_info   --remap depth/image:=/camera/depth/image_raw   > /tmp/rgbd_sync.log 2>&1"
sleep 5
echo 'RGBD sync actief'

echo '=== STAP 4: Scan timestamp fix ==='
docker cp /home/pi/scan_timestamped.py $C:/root/scan_timestamped.py 2>/dev/null || true
docker exec -d $C bash -c "$R && exec python3 /root/scan_timestamped.py > /tmp/scan_fix.log 2>&1"
sleep 2
echo 'Scan timestamp fix actief'

echo '=== STAP 5: rf2o ==='
docker exec -d $C bash -c "$R && $N && exec ros2 launch rf2o_laser_odometry rf2o_laser_odometry.launch.py > /tmp/rf2o.log 2>&1"
sleep 6
echo 'rf2o actief'

echo '=== STAP 6: IMU publisher ==='
docker cp /home/pi/imu_publisher.py $C:/root/imu_publisher.py 2>/dev/null || true
docker exec -d $C bash -c "$R && exec python3 /root/imu_publisher.py > /tmp/imu.log 2>&1"
sleep 3
echo 'IMU publisher actief'

echo '=== STAP 7: Rosbridge ==='
docker exec -d $C bash -c "$R && ros2 launch rosbridge_server rosbridge_websocket_launch.xml > /tmp/rosbridge.log 2>&1"
sleep 3
echo 'Rosbridge actief'

echo '=== STAP 8: Muto driver ==='
docker cp /home/pi/muto_driver_fixed.py $C:/root/muto_driver_fixed.py 2>/dev/null || true
docker exec -d $C bash -c "$R && exec python3 /root/muto_driver_fixed.py > /tmp/muto_driver.log 2>&1"
sleep 2
echo 'Driver actief'

echo '=== STAP 9: Webserver ==='
nohup python3 -m http.server 8080 --directory /home/pi > /tmp/webserver.log 2>&1 &
disown
sleep 2
HTTP=$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8080/muto_viz.html)
echo "Webserver actief (HTTP $HTTP)"

echo ''
echo '========================================='
echo 'PI stack operationeel'
echo 'GEEN RTAB-Map of TF op Pi'
echo 'Start Jetson: sudo bash /home/Danny/muto_jetson_start.sh'
echo 'Map: http://192.168.68.88:8080/muto_viz.html'
echo '========================================='
