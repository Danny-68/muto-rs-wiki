#!/bin/bash
# JETSON ONLY - dual board versie v2
C=jetson_run
R="source /opt/ros/humble/setup.bash && export CYCLONEDDS_URI=file:///root/cyclone_dds.xml"
RF2O="source /root/rf2o_ws/install/setup.bash"

echo "=== STAP 0: Container starten ==="
docker start $C
sleep 5
STATUS=$(docker inspect -f '{{.State.Running}}' $C 2>/dev/null)
if [ "$STATUS" != "true" ]; then echo "FOUT: jetson_run start mislukt"; exit 1; fi
echo "jetson_run actief"

echo "=== STAP 1: TF laser ==="
docker exec -d $C bash -c "$R && exec /opt/ros/humble/lib/tf2_ros/static_transform_publisher --x -0.04 --y 0.0 --z 0.24 --yaw 0 --pitch 0 --roll 0 --frame-id base_link --child-frame-id laser"
sleep 2
echo "Laser TF actief (yaw=0)"

echo "=== STAP 2: TF camera ==="
docker exec -d $C bash -c "$R && exec /opt/ros/humble/lib/tf2_ros/static_transform_publisher --x 0.06 --y 0.0 --z 0.225 --yaw 0.0 --pitch 0.1047 --roll 0.0 --frame-id base_link --child-frame-id camera_link"
sleep 2
echo "Camera TF actief"

echo "=== STAP 3: TF imu_link ==="
docker exec -d $C bash -c "$R && exec /opt/ros/humble/lib/tf2_ros/static_transform_publisher --x 0.0 --y 0.0 --z 0.0 --yaw 0 --pitch 0 --roll 0 --frame-id base_link --child-frame-id imu_link"
sleep 2
echo "imu_link TF actief"

echo "=== STAP 4: Pi TF stoppen ==="
ssh pi@192.168.68.88 "docker exec humble_run pkill -9 -f static_transform 2>/dev/null || true" 2>/dev/null || true
echo "Pi TF gestopt"

echo "=== STAP 5: RTAB-Map GPU ==="
docker exec -d $C bash -c "$R && ros2 run rtabmap_slam rtabmap --ros-args --params-file /root/rtabmap_params.yaml --remap scan:=/scan_fixed --remap odom:=/odom --remap rgbd_image:=/rgbd_image > /tmp/rtabmap.log 2>&1"
sleep 10
MAP=$(docker exec $C bash -c "$R && ros2 topic list 2>/dev/null | grep ^/map$" 2>/dev/null || echo "")
if [ -z "$MAP" ]; then
    echo "WAARSCHUWING: /map nog niet zichtbaar"
    echo "Check: docker exec jetson_run tail -20 /tmp/rtabmap.log"
else
    echo "RTAB-Map actief (/map beschikbaar)"
fi

echo ""
echo "========================================="
echo "JETSON stack operationeel"
echo "TF: laser (yaw=0), camera_link, imu_link"
echo "RTAB-Map: GPU actief"
echo "Map: http://192.168.68.88:8080/muto_viz.html"
echo "========================================="
