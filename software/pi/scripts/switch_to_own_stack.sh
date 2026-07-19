#!/bin/bash
# switch_to_own_stack.sh — Stop Yahboom Stack B, herstel eigen Stack A
# inclusief automatische opstart van LiDAR, camera en sensor_relay
# Gebruik: sudo bash /home/pi/switch_to_own_stack.sh

ROBOT_BRIDGE="${1:-/home/pi/robot_bridge.py}"
LOG_DIR="/home/pi/logs"
LIDAR_TIMEOUT=15
CAMERA_TIMEOUT=20
RELAY_TIMEOUT=15

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

ok()   { echo -e "${GREEN}[OK]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
fail() { echo -e "${RED}[FAIL]${NC} $1"; }
info() { echo -e "${BLUE}[INFO]${NC} $1"; }

mkdir -p "$LOG_DIR"

echo "========================================"
echo " Stack A opstarten (volledig)"
echo "========================================"

# ── Stap 1: Yahboom Stack B stoppen ──────────────────────────────────
echo ""
echo "Stap 1: Yahboom Stack B stoppen..."
if docker ps --format '{{.Names}}' | grep -q "^muto_yahboom$"; then
    docker stop muto_yahboom
    sleep 3
    ok "muto_yahboom gestopt"
else
    warn "muto_yahboom was al niet actief"
fi

# ── Stap 2: app_muto.py stoppen ──────────────────────────────────────
echo ""
echo "Stap 2: app_muto.py stoppen..."
if pgrep -f "app_muto.py" > /dev/null; then
    pkill -f "app_muto.py" || true
    sleep 2
    ok "app_muto.py gestopt"
else
    warn "app_muto.py was al niet actief"
fi

# ── Stap 3: Bestaande sensor-processen opruimen ───────────────────────
echo ""
echo "Stap 3: Bestaande sensor-processen opruimen..."
docker exec humble_run pkill -f "sensor_relay.py" 2>/dev/null || true
docker exec humble_run pkill -f "ydlidar" 2>/dev/null || true
docker exec humble_run pkill -f "astra_camera" 2>/dev/null || true
sleep 2
ok "Sensor-processen opgeruimd"

# ── Stap 4: /dev/myserial vrij ───────────────────────────────────────
echo ""
echo "Stap 4: Verificeer /dev/myserial vrij..."
sleep 1
if lsof /dev/myserial 2>/dev/null | grep -q "python"; then
    fail "/dev/myserial nog bezet"
    exit 1
fi
ok "/dev/myserial is vrij"

# ── Stap 5: humble_run starten ───────────────────────────────────────
echo ""
echo "Stap 5: humble_run container starten..."
if docker ps --format '{{.Names}}' | grep -q "^humble_run$"; then
    warn "humble_run draait al"
else
    docker start humble_run
    sleep 3
    if docker ps --format '{{.Names}}' | grep -q "^humble_run$"; then
        ok "humble_run gestart"
    else
        fail "humble_run kon niet starten"
        exit 1
    fi
fi

# ── Stap 6: robot_bridge.py starten ─────────────────────────────────
echo ""
echo "Stap 6: robot_bridge.py starten..."
pkill -f "robot_bridge.py" 2>/dev/null || true
sleep 1
if [ ! -f "$ROBOT_BRIDGE" ]; then
    fail "robot_bridge.py niet gevonden op: $ROBOT_BRIDGE"
    exit 1
fi
nohup python3 "$ROBOT_BRIDGE" > "$LOG_DIR/robot_bridge.log" 2>&1 &
sleep 2
if pgrep -f "robot_bridge.py" > /dev/null; then
    ok "robot_bridge.py gestart"
else
    fail "robot_bridge.py kon niet starten — check: cat $LOG_DIR/robot_bridge.log"
    exit 1
fi

# ── Stap 7: LiDAR driver starten ────────────────────────────────────
echo ""
echo "Stap 7: LiDAR driver starten..."
docker exec -d humble_run bash -c \
    "source /opt/ros/humble/setup.bash && \
     source /root/yahboomcar_ros2_ws/software/library_ws_humble/install/setup.bash && \
     ros2 launch ydlidar_ros2_driver ydlidar_launch.py > /tmp/lidar.log 2>&1"

info "Wachten op LiDAR node (max ${LIDAR_TIMEOUT}s)..."
LIDAR_OK=false
for i in $(seq 1 $LIDAR_TIMEOUT); do
    if docker exec humble_run bash -c \
        "source /opt/ros/humble/setup.bash && ros2 node list 2>/dev/null" \
        | grep -q "ydlidar_ros2_driver_node"; then
        LIDAR_OK=true
        break
    fi
    sleep 1
done

if [ "$LIDAR_OK" = false ]; then
    warn "LiDAR node niet zichtbaar na ${LIDAR_TIMEOUT}s"
    docker exec humble_run cat /tmp/lidar.log > "$LOG_DIR/lidar.log" 2>/dev/null
else
    ok "LiDAR node actief"
fi

# ── Stap 8: Camera driver starten ───────────────────────────────────
echo ""
echo "Stap 8: Camera driver starten..."
docker exec -d humble_run bash -c \
    "source /opt/ros/humble/setup.bash && \
     source /root/yahboomcar_ros2_ws/software/library_ws_humble/install/setup.bash && \
     ros2 launch astra_camera astro_pro_plus.launch.xml > /tmp/camera.log 2>&1"

info "Wachten op camera topics (max ${CAMERA_TIMEOUT}s)..."
CAMERA_OK=false
for i in $(seq 1 $CAMERA_TIMEOUT); do
    COUNT=$(docker exec humble_run bash -c \
        "source /opt/ros/humble/setup.bash && \
         ros2 topic info /camera/color/image_raw 2>/dev/null" \
        | grep "Publisher count" | grep -o '[0-9]*' || echo "0")
    if [ "${COUNT:-0}" -ge 1 ] 2>/dev/null; then
        CAMERA_OK=true
        break
    fi
    sleep 1
done

if [ "$CAMERA_OK" = false ]; then
    warn "Camera niet actief na ${CAMERA_TIMEOUT}s"
    docker exec humble_run cat /tmp/camera.log > "$LOG_DIR/camera.log" 2>/dev/null
else
    ok "Camera actief"
fi

# ── Stap 9: sensor_relay.py starten ─────────────────────────────────
echo ""
echo "Stap 9: sensor_relay.py starten..."
docker exec -d humble_run bash -c \
    "source /opt/ros/humble/setup.bash && \
     source /root/yahboomcar_ros2_ws/software/library_ws_humble/install/setup.bash && \
     python3 /root/sensor_relay.py > /tmp/sensor_relay.log 2>&1"

info "Wachten op sensor_relay HTTP (max ${RELAY_TIMEOUT}s)..."
RELAY_OK=false
for i in $(seq 1 $RELAY_TIMEOUT); do
    if curl -s --max-time 1 http://localhost:5001/scan/nearest > /dev/null 2>&1; then
        RELAY_OK=true
        break
    fi
    sleep 1
done

if [ "$RELAY_OK" = false ]; then
    warn "sensor_relay niet bereikbaar na ${RELAY_TIMEOUT}s"
    docker exec humble_run cat /tmp/sensor_relay.log > "$LOG_DIR/sensor_relay.log" 2>/dev/null
else
    ok "sensor_relay actief op poort 5001"
fi

# ── Stap 10: Eindverificatie ─────────────────────────────────────────
echo ""
echo "Stap 10: Eindverificatie..."
sleep 8

BRIDGE_DATA=$(curl -s --max-time 2 http://localhost:5000/health)
LIDAR_DATA=$(curl -s --max-time 2 http://localhost:5001/scan/nearest)
DEPTH_DATA=$(curl -s --max-time 2 http://localhost:5001/depth/center)
CAMERA_BYTES=$(curl -s --max-time 3 http://localhost:5001/camera/color/jpeg | wc -c)

echo ""
echo "========================================"
echo " Stack A status"
echo "========================================"

if echo "$BRIDGE_DATA" | grep -q '"ok":true'; then
    ok "robot_bridge.py (poort 5000): bereikbaar"
else
    warn "robot_bridge.py: NIET bereikbaar"
fi

if echo "$LIDAR_DATA" | grep -q '"ok":true'; then
    DIST=$(echo "$LIDAR_DATA" | python3 -c \
        "import sys,json; d=json.load(sys.stdin); print(f\"{d['distance_m']}m @ {d['angle_deg']}deg\")" \
        2>/dev/null || echo "data ontvangen")
    ok "LiDAR: $DIST"
else
    warn "LiDAR: nog geen scan-data"
fi

if echo "$DEPTH_DATA" | grep -q '"ok":true'; then
    DEPTH=$(echo "$DEPTH_DATA" | python3 -c \
        "import sys,json; d=json.load(sys.stdin); print(f\"z={d['z_m']}m\")" \
        2>/dev/null || echo "data ontvangen")
    ok "Dieptecamera: $DEPTH"
else
    warn "Dieptecamera: nog geen data"
fi

if [ "${CAMERA_BYTES:-0}" -gt 1000 ] 2>/dev/null; then
    ok "Kleurcamera: ${CAMERA_BYTES} bytes JPEG"
else
    warn "Kleurcamera: geen JPEG-data"
fi

echo "========================================"
echo " Stack A opstarten voltooid"
echo "========================================"
echo ""
echo "Logs op host : ls $LOG_DIR/"
echo "Logs in container:"
echo "  LiDAR        : docker exec humble_run cat /tmp/lidar.log"
echo "  Camera       : docker exec humble_run cat /tmp/camera.log"
echo "  sensor_relay : docker exec humble_run cat /tmp/sensor_relay.log"
echo ""
