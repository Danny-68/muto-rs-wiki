#!/bin/bash
# =============================================================
# muto_slam_start.sh v5 — Volledige SLAM + Nav2 opstart
# Gebruik: sudo bash /home/pi/muto_slam_start.sh [--nav2]
# =============================================================
# KRITIEKE REGELS:
# 1. NOOIT map_slam_toolbox_launch.py gebruiken — start 2e ydlidar!
# 2. reversion: false in ydlidar.yaml
# 3. Camera NIET starten tijdens SLAM
# 4. sensor_relay NIET starten tijdens SLAM
# 5. Statische TF base_link->laser VERPLICHT voor slam_toolbox
# 6. Nav2 vereist opgeslagen kaart + initialpose via RViz2
# =============================================================

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
ok()   { echo -e "${GREEN}[OK]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
fail() { echo -e "${RED}[FAIL]${NC} $1"; exit 1; }
info() { echo -e "${BLUE}[INFO]${NC} $1"; }

NAV2=false
[ "$1" = "--nav2" ] && NAV2=true

echo "============================================================"
echo " Muto RS -- SLAM Opstart v5  ($(date))"
[ "$NAV2" = true ] && echo " Modus: SLAM + Nav2" || echo " Modus: SLAM mapping"
echo "============================================================"

# -- Stap 1: Alle processen stoppen ------------------------------
echo ""; echo "Stap 1: Alle processen stoppen..."
docker exec humble_run pkill -9 -f "ydlidar" 2>/dev/null || true
docker exec humble_run pkill -9 -f "slam_toolbox" 2>/dev/null || true
docker exec humble_run pkill -9 -f "rf2o" 2>/dev/null || true
docker exec humble_run pkill -9 -f "astra_camera" 2>/dev/null || true
docker exec humble_run pkill -9 -f "sensor_relay" 2>/dev/null || true
docker exec humble_run pkill -9 -f "muto_driver" 2>/dev/null || true
docker exec humble_run pkill -9 -f "rosbridge" 2>/dev/null || true
docker exec humble_run pkill -9 -f "static_transform" 2>/dev/null || true
docker exec humble_run pkill -9 -f "odom_publisher" 2>/dev/null || true
docker exec humble_run pkill -9 -f "nav2\|amcl\|bt_navigator\|lifecycle" 2>/dev/null || true
pkill -f "robot_bridge.py" 2>/dev/null || true
pkill -f "http.server" 2>/dev/null || true
sleep 4
ok "Alle processen gestopt"

# -- Stap 2: humble_run container --------------------------------
echo ""; echo "Stap 2: humble_run container..."
if ! docker ps --format '{{.Names}}' | grep -q "^humble_run$"; then
    docker start humble_run; sleep 4
fi
ok "humble_run draait"

# -- Stap 3: rplidar symlink -------------------------------------
echo ""; echo "Stap 3: rplidar symlink..."
sudo ln -sf /dev/mylidar /dev/rplidar 2>/dev/null || true
ok "/dev/rplidar -> $(readlink /dev/rplidar)"

# -- Stap 4: LiDAR configuratie check ----------------------------
echo ""; echo "Stap 4: LiDAR configuratie check..."
YAML="/root/yahboomcar_ros2_ws/software/library_ws_humble/install/ydlidar_ros2_driver/share/ydlidar_ros2_driver/params/ydlidar.yaml"
if docker exec humble_run grep "reversion" $YAML | grep -q "true"; then
    warn "reversion: true — corrigeren naar false"
    docker exec humble_run sed -i 's/reversion: true/reversion: false/' $YAML
fi
ok "reversion: false bevestigd"

# -- Stap 5: YDLidar starten ------------------------------------
echo ""; echo "Stap 5: YDLidar starten..."
docker exec -d humble_run bash -c \
    "source /opt/ros/humble/setup.bash && \
     source /root/yahboomcar_ros2_ws/software/library_ws_humble/install/setup.bash && \
     ros2 launch ydlidar_ros2_driver ydlidar_launch.py > /tmp/ydlidar.log 2>&1"

echo "  Wachten op /scan..."
LIDAR_OK=false
for i in $(seq 1 20); do
    sleep 2
    if docker exec humble_run bash -c \
        "source /opt/ros/humble/setup.bash && \
         ros2 topic list 2>/dev/null | grep -q '^/scan$'"; then
        LIDAR_OK=true; ok "LiDAR actief: /scan"; break
    fi
    echo "  ...wachten ($((i*2))s)"
done
[ "$LIDAR_OK" = false ] && fail "LiDAR niet gevonden na 40s"

# -- Stap 6: Statische TF base_link → laser ----------------------
echo ""; echo "Stap 6: Statische TF publisher..."
docker exec -d humble_run bash -c \
    "source /opt/ros/humble/setup.bash && \
     exec /opt/ros/humble/lib/tf2_ros/static_transform_publisher \
     --x -0.032 --y 0 --z 0.184 \
     --yaw 0 --pitch 0 --roll 0 \
     --frame-id base_link --child-frame-id laser"
sleep 2
ok "TF base_link → laser gestart"

# -- Stap 7: rf2o odometrie --------------------------------------
echo ""; echo "Stap 7: rf2o odometrie..."
docker exec -d humble_run bash -c \
    "source /opt/ros/humble/setup.bash && \
     source /root/yahboomcar_ros2_ws/yahboomcar_ws/install/setup.bash && \
     ros2 launch rf2o_laser_odometry rf2o_laser_odometry.launch.py \
     > /tmp/rf2o.log 2>&1"
sleep 4
ok "rf2o gestart"

# -- Stap 8: slam_toolbox ----------------------------------------
echo ""; echo "Stap 8: slam_toolbox starten..."
docker exec -d humble_run bash -c \
    "source /opt/ros/humble/setup.bash && \
     ros2 run slam_toolbox sync_slam_toolbox_node \
     --ros-args \
     -p use_sim_time:=false \
     -p odom_frame:=odom \
     -p map_frame:=map \
     -p base_frame:=base_link \
     -p scan_topic:=/scan \
     -p mode:=mapping \
     > /tmp/slam.log 2>&1"

echo "  Wachten op /map..."
SLAM_OK=false
for i in $(seq 1 15); do
    sleep 2
    if docker exec humble_run bash -c \
        "source /opt/ros/humble/setup.bash && \
         ros2 topic list 2>/dev/null | grep -q '^/map$'"; then
        SLAM_OK=true; ok "SLAM actief: /map"; break
    fi
    echo "  ...wachten ($((i*2))s)"
done
[ "$SLAM_OK" = false ] && warn "SLAM /map niet actief — check /tmp/slam.log"

# -- Stap 9: Rosbridge ------------------------------------------
echo ""; echo "Stap 9: Rosbridge (poort 9090)..."
docker exec -d humble_run bash -c \
    "source /opt/ros/humble/setup.bash && \
     ros2 launch rosbridge_server rosbridge_websocket_launch.xml \
     > /tmp/rosbridge.log 2>&1"
sleep 3
ok "Rosbridge gestart"

# -- Stap 10: Muto driver ----------------------------------------
echo ""; echo "Stap 10: Muto driver..."
docker exec -d humble_run bash -c \
    "source /opt/ros/humble/setup.bash && \
     python3 /root/muto_driver_fixed.py > /tmp/muto_driver.log 2>&1"
sleep 2
ok "Muto driver gestart"

# -- Stap 11: Nav2 (optioneel) -----------------------------------
if [ "$NAV2" = true ]; then
    echo ""; echo "Stap 11: Nav2 starten..."
    if [ ! -f "/home/pi/muto_map.yaml" ]; then
        # Kaart staat op host — kopieer naar container
        docker cp /home/pi/muto_map.pgm humble_run:/root/muto_map.pgm 2>/dev/null || true
        docker cp /home/pi/muto_map.yaml humble_run:/root/muto_map.yaml 2>/dev/null || true
    fi
    docker exec -d humble_run bash -c \
        "source /opt/ros/humble/setup.bash && \
         source /root/yahboomcar_ros2_ws/yahboomcar_ws/install/setup.bash && \
         ros2 launch hexapod_nav hexapod_navigation.launch.py \
         map:=/root/muto_map.yaml \
         > /tmp/nav2.log 2>&1"
    sleep 8
    ok "Nav2 gestart"
    info "Stel startpositie in via RViz2 (2D Pose Estimate)"
fi

# -- Stap 12: Webserver -----------------------------------------
echo ""; echo "Stap 12: Webserver (poort 8080)..."
python3 -m http.server 8080 --directory /home/pi > /tmp/webserver.log 2>&1 &
sleep 1
ok "Webserver gestart"

# -- Verificatie ------------------------------------------------
echo ""; echo "Verificatie..."
LIDAR_COUNT=$(docker exec humble_run ps aux | grep "ydlidar_ros2_driver_node" | grep -v grep | wc -l)
[ "$LIDAR_COUNT" -gt 1 ] && warn "MEERDERE ydlidar processen ($LIDAR_COUNT)!" || ok "YDLidar: 1 proces"

echo ""
echo "============================================================"
echo -e " ${GREEN}Klaar!${NC}"
echo ""
echo "  Visualisatie : http://192.168.68.88:8080/muto_viz.html"
echo ""
echo "  Kaart opslaan:"
echo "    docker exec humble_run bash -c 'source /opt/ros/humble/setup.bash && source /root/yahboomcar_ros2_ws/yahboomcar_ws/install/setup.bash && ros2 run nav2_map_server map_saver_cli -f /root/muto_map'"
echo "    sudo docker cp humble_run:/root/muto_map.pgm /home/pi/muto_map.pgm"
echo "    sudo docker cp humble_run:/root/muto_map.yaml /home/pi/muto_map.yaml"
echo ""
if [ "$NAV2" = true ]; then
echo "  Nav2 actief:"
echo "    1. Start RViz2: export DISPLAY=192.168.68.77:0.0 && docker exec -it humble_run bash -c 'source /opt/ros/humble/setup.bash && source /root/yahboomcar_ros2_ws/yahboomcar_ws/install/setup.bash && export DISPLAY=192.168.68.77:0.0 && rviz2'"
echo "    2. Klik 2D Pose Estimate op startpositie robot"
echo "    3. Klik 2D Nav Goal voor doelpunt"
echo ""
else
echo "  Nav2 starten: sudo bash /home/pi/muto_slam_start.sh --nav2"
echo ""
fi
echo "  Logs:"
echo "    LiDAR : docker exec humble_run cat /tmp/ydlidar.log | tail -5"
echo "    rf2o  : docker exec humble_run cat /tmp/rf2o.log | tail -5"
echo "    SLAM  : docker exec humble_run cat /tmp/slam.log | tail -5"
echo "    Driver: docker exec humble_run cat /tmp/muto_driver.log | tail -5"
[ "$NAV2" = true ] && echo "    Nav2  : docker exec humble_run cat /tmp/nav2.log | tail -5"
echo ""
echo "  WAARSCHUWING: Fysieke aan/uit bij nood!"
echo "============================================================"
