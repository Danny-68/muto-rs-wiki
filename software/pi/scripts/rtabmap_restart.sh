#!/bin/bash
# Herstart ALLEEN rtabmap_slam zonder andere processen te raken
C=humble_run
R="source /opt/ros/humble/setup.bash"
N="source /root/yahboomcar_ros2_ws/yahboomcar_ws/install/setup.bash"

echo "--- rtabmap stoppen ---"
docker exec $C pkill -9 -f "/opt/ros/humble/lib/rtabmap_slam/rtabmap" 2>/dev/null || true
sleep 3

echo "--- rtabmap herstarten ---"
docker exec -d $C bash -c "$R && $N && ros2 run rtabmap_slam rtabmap --ros-args --params-file /root/rtabmap_params.yaml --remap scan:=/scan --remap odom:=/odom --remap rgbd_image:=/rgbd_image > /tmp/rtabmap.log 2>&1"
sleep 8

echo "--- map TF check ---"
TF=$(docker exec $C bash -c "$R && timeout 3 ros2 topic echo /tf --once 2>/dev/null" | grep "frame_id: map" || echo "")
if [ -n "$TF" ]; then
  echo "OK: map TF actief"
else
  echo "WAARSCHUWING: map TF niet gevonden"
fi

docker exec $C tail -2 /tmp/rtabmap.log
