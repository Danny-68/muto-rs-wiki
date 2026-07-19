#!/bin/bash
# Start YDLIDAR 4ROS (TG30) driver in de humble_run Docker container
# Gecorrigeerde versie: gebruikt Humble (niet Kilted) en lidar_type=0 (TOF)

CONTAINER="humble_run"

if ! docker ps --format "{{.Names}}" | grep -q "^${CONTAINER}$"; then
    echo "Container '${CONTAINER}' draait niet. Probeer te starten..."
    docker start "${CONTAINER}" || { echo "Kon container niet starten."; exit 1; }
    sleep 2
fi

echo "Container: ${CONTAINER}"

# LET OP: /dev/ttyUSB-nummering kan verschuiven na reboot/USB-herschikking.
# Controleer dit altijd eerst op de host met:
#   udevadm info -a -n /dev/ttyUSBX | grep -E "idVendor|idProduct|product"
# Verwacht voor de LiDAR: idVendor=10c4, idProduct=ea60 (Silicon Labs CP2102)
LIDAR_PORT="/dev/ttyUSB2"

echo "Lidar starten op ${LIDAR_PORT} met 512000 baud (lidar_type=0, TOF/TG30)..."
docker exec -d "${CONTAINER}" bash -c "
export FASTDDS_BUILTIN_TRANSPORTS=UDPv4
source /opt/ros/humble/setup.bash
source /root/yahboomcar_ros2_ws/software/library_ws_humble/install/setup.bash
ros2 run ydlidar_ros2_driver ydlidar_ros2_driver_node --ros-args \
    -p port:=${LIDAR_PORT} \
    -p baudrate:=512000 \
    -p lidar_type:=0 \
    -p sample_rate:=20 \
    -p range_max:=30.0 \
    -p range_min:=0.05 \
    -p frame_id:=laser_frame \
    -p auto_reconnect:=true > /tmp/ydlidar_out.txt 2>&1
"

sleep 5
if docker exec "${CONTAINER}" bash -c "source /opt/ros/humble/setup.bash && ros2 topic list 2>/dev/null | grep -q scan"; then
    echo "Lidar actief — /scan topic beschikbaar"
else
    echo "Lidar nog niet actief, laatste output:"
    docker exec "${CONTAINER}" cat /tmp/ydlidar_out.txt 2>/dev/null | tail -10
fi
