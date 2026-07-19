#!/bin/bash
# switch_to_yahboom.sh — Stop Stack A, start Yahboom Stack B
# Gebruik: sudo bash /home/pi/switch_to_yahboom.sh

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

ok()   { echo -e "${GREEN}[OK]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
fail() { echo -e "${RED}[FAIL]${NC} $1"; exit 1; }

echo "========================================"
echo " Wisselen naar Yahboom Stack B"
echo "========================================"

# ── Stap 1: Stoppen van app_muto.py ──────────────────────────────────────────
echo ""
echo "Stap 1: app_muto.py stoppen..."
if pgrep -f "app_muto.py" > /dev/null; then
    pkill -f "app_muto.py" || true
    sleep 2
    if pgrep -f "app_muto.py" > /dev/null; then
        pkill -9 -f "app_muto.py" || true
        sleep 1
    fi
    ok "app_muto.py gestopt"
else
    warn "app_muto.py was al niet actief"
fi

# ── Stap 2: Verificeer /dev/myserial vrij ────────────────────────────────────
echo ""
echo "Stap 2: Verificeer /dev/myserial vrij..."
sleep 1
if lsof /dev/myserial 2>/dev/null | grep -q "python"; then
    fail "/dev/myserial nog steeds bezet — stop handmatig wat de poort gebruikt"
fi
ok "/dev/myserial is vrij"

# ── Stap 3: robot_bridge.py stoppen indien actief ────────────────────────────
echo ""
echo "Stap 3: robot_bridge.py stoppen..."
if pgrep -f "robot_bridge.py" > /dev/null; then
    pkill -f "robot_bridge.py" || true
    sleep 2
    ok "robot_bridge.py gestopt"
else
    warn "robot_bridge.py was al niet actief"
fi

# ── Stap 4: Eventuele oude Stack B container opruimen ────────────────────────
echo ""
echo "Stap 4: Eventuele oude Stack B container opruimen..."
OLD=$(docker ps -q --filter name=muto_yahboom 2>/dev/null)
if [ -n "$OLD" ]; then
    docker stop muto_yahboom || true
    sleep 2
    ok "Oude muto_yahboom container gestopt"
else
    warn "Geen oude muto_yahboom container gevonden"
fi

# ── Stap 5: humble_run starten ───────────────────────────────────────────────
echo ""
echo "Stap 5: humble_run starten..."
if docker ps --format '{{.Names}}' | grep -q "^humble_run$"; then
    warn "humble_run draait al"
else
    docker start humble_run
    sleep 3
    ok "humble_run gestart"
fi

# ── Stap 6: LiDAR starten in humble_run ─────────────────────────────────────
echo ""
echo "Stap 6: LiDAR starten in humble_run..."
docker exec -d humble_run bash -c \
    "source /opt/ros/humble/setup.bash && \
     source /root/yahboomcar_ros2_ws/software/library_ws_humble/install/setup.bash && \
     ros2 launch ydlidar_ros2_driver ydlidar_launch.py > /tmp/lidar_launch.log 2>&1"

# Wacht tot /scan topic actief is
LIDAR_OK=false
for i in $(seq 1 6); do
    sleep 5
    SCAN=$(docker exec humble_run bash -c \
        "source /opt/ros/humble/setup.bash && ros2 topic list 2>/dev/null | grep scan" 2>/dev/null || true)
    if [ -n "$SCAN" ]; then
        LIDAR_OK=true
        ok "LiDAR topic actief: $SCAN"
        break
    fi
    echo "  Wachten op LiDAR... ($((i*5))s)"
done

if [ "$LIDAR_OK" = false ]; then
    warn "LiDAR topic niet gevonden na 30s — Stack B start zonder LiDAR"
fi

# ── Stap 7: Verificeer Dify bereikbaar ───────────────────────────────────────
echo ""
echo "Stap 7: Controleer of Dify bereikbaar is op 192.168.68.77..."
if ! ping -c 2 -W 2 192.168.68.77 > /dev/null 2>&1; then
    fail "192.168.68.77 niet bereikbaar — is Docker Desktop en Dify gestart op de Windows PC?"
fi
ok "Dify host bereikbaar"

# ── Stap 8: Stack B starten ───────────────────────────────────────────────────
echo ""
echo "Stap 8: Stack B starten (Yahboom muto_controller)..."
echo "Log volgt hieronder — Ctrl+C om te stoppen"
echo "========================================"

docker run -it --rm \
    --privileged \
    --net=host \
    --name muto_yahboom \
    -v /root/muto-llm-2.0:/root/muto-llm-2.0 \
    -v /dev:/dev \
    -v /home/pi/speech_music:/home/pi/speech_music \
    -v /home/pi/yahboomcar_ros2_ws:/root/yahboomcar_ros2_ws \
    -e DIFY_HOST=192.168.68.77 \
    -e DIFY_API_KEY=app-f4CjDXcJX4VvnIqR34Z0LGM2 \
    -e FORCE_VOICE_PROVIDER=alibaba \
    -e MUTO_ENABLE_VOICE=false \
    -e ROBOT_TYPE=Muto \
    -e RPLIDAR_TYPE=4ROS \
    -e ALSA_CARD=3 \
    -e AUDIODEV=hw:3,0 \
    muto-humble:3.5 \
    bash -c "source /root/yahboomcar_ros2_ws/software/library_ws_humble/install/setup.bash && bash /root/muto-llm-2.0/rebuild_and_launch.sh"
