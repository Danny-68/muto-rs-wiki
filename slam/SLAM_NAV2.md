# 🗺️ SLAM & Nav2 Referentie — Yahboom Muto RS

---

## Opstartscript (enkelvoudig commando)

```bash
# 🐧 PI TERMINAL
sudo bash /home/pi/muto_rtabmap_start.sh
```

**Stap 0 (altijd eerst):**
```bash
docker restart humble_run   # Schone lei
```

---

## Verplichte SLAM Opstartsequentie

> ⚠️ Volgorde is kritiek. Sla nooit stappen over.

```
1. pkill alle bestaande processen
2. Start LiDAR → wacht op /scan
3. Start rf2o
4. Start slam_toolbox (of RTAB-Map)
5. Start driver
6. NOOIT camera starten tijdens SLAM-only sessies
```

---

## RTAB-Map Setup

### Parameters (`/root/rtabmap_params.yaml` in container)

```yaml
# Kritieke instellingen
frame_id: "base_link"
Reg/Force3DoF: "true"
qos_scan: 2
qos_image: 2
# String-typed parameters verplicht
```

### RTAB-Map starten op Jetson (GPU)

```bash
# 🐧 JETSON TERMINAL
docker exec -d jetson_run bash -c '
  source /opt/ros/humble/setup.bash && \
  ros2 run rtabmap_slam rtabmap \
    --ros-args \
    --params-file /root/rtabmap_params.yaml \
    --remap scan:=/scan_fixed \
    --remap odom:=/odom \
    --remap rgbd_image:=/rgbd_image \
    > /tmp/rtabmap.log 2>&1'
```

### TF Publishers starten op Jetson

```bash
# Laser TF (yaw=0 is DEFINITIEF)
docker exec -d jetson_run bash -c '
  source /opt/ros/humble/setup.bash && \
  ros2 run tf2_ros static_transform_publisher \
    -0.04 0 0.24 0 0 0 base_link laser_frame'

# Camera TF (pitch=0.1047rad = 6°)
docker exec -d jetson_run bash -c '
  source /opt/ros/humble/setup.bash && \
  ros2 run tf2_ros static_transform_publisher \
    0.06 0 0.225 0 0.1047 0 base_link camera_link'

# IMU TF (geen offset)
docker exec -d jetson_run bash -c '
  source /opt/ros/humble/setup.bash && \
  ros2 run tf2_ros static_transform_publisher \
    0 0 0 0 0 0 base_link imu_link'
```

### Veilig RTAB-Map herstarten (zonder TF publishers te raken)

```bash
# 🐧 PI TERMINAL
sudo bash /home/pi/rtabmap_restart.sh
```

---

## scan_timestamped.py — Timestamp Fix

**Probleem:** Nav2 drops scan timestamps (2845 drops gemeten)
**Oplossing:** Republiceert `/scan` als `/scan_fixed` met huidige timestamp

```bash
# Starten (is onderdeel van muto_rtabmap_start.sh, stap 9)
docker exec -d humble_run bash -c '
  source /opt/ros/humble/setup.bash && \
  exec python3 /root/scan_timestamped.py > /tmp/scan_ts.log 2>&1'
```

Na fix: drops van 2845 → 4.

---

## Nav2 Setup

### Starten

```bash
# 🐧 PI TERMINAL (in humble_run)
ros2 launch nav2_bringup navigation_launch.py \
  params_file:=/root/hexapod_nav_params_custom.yaml
```

> ⚠️ NOOIT `bringup_launch.py` gebruiken → start AMCL (conflicteert met RTAB-Map)

### cmd_vel relay (verplicht)

```bash
ros2 run topic_tools relay /cmd_vel_nav /cmd_vel
```

### Voor Nav2 starten: altijd serial vrijgeven

```bash
pkill -f app_muto.py    # Bezet anders /dev/myserial
```

### Nav2 keten

```
Nav2 → /cmd_vel_nav → relay → /cmd_vel → muto_driver → STM32 → robot
```

---

## rf2o Laser Odometrie

### Starten op Pi

```bash
# In humble_run container
source /opt/ros/humble/setup.bash
source /home/pi/yahboomcar_ros2_ws/software/library_ws_humble/install/setup.bash
ros2 launch rf2o_laser_odometry rf2o_laser_odometry.launch.py
```

- Pi rf2o publiceert naar `/odom` (via launch file)
- RTAB-Map remap: `--remap odom:=/odom`

---

## Camera Setup voor RTAB-Map

```bash
# In humble_run container — ALTIJD zonder fps argumenten
ros2 launch astra_camera astro_pro_plus.launch.xml
```

### rgbd_sync

```bash
ros2 run rtabmap_sync rgbd_sync \
  approx_sync:=true \
  qos:=1 \
  topic_image_rgb:=/camera/color/image_raw \
  topic_image_depth:=/camera/depth/image_raw \
  topic_camera_info_rgb:=/camera/color/camera_info
```

> ⚠️ `qos:=1` (BEST_EFFORT) is verplicht — camera publiceert BEST_EFFORT

---

## Web Visualisatie

URL: `http://192.168.68.88:8080/muto_viz.html`

Toont:
- Live RTAB-Map kaart
- LiDAR scan
- Robot positie (odom)
- 6-richting besturing via rosbridge (:9090)
- Publiceert Twist via `/cmd_vel`

Rosbridge instellingen:
- `throttle_rate: 500` (CPU besparend)
- Topics: `/map`, `/scan`, `/odom` (geen camera topics via rosbridge)

---

## Yahboom Launch File Regels

| Launch file | Status | Reden |
|---|---|---|
| `map_slam_toolbox_launch.py` | ❌ NOOIT | Bevat laser_bringup_launch.py → 2e ydlidar |
| `laser_bringup_launch.py` | ❌ NOOIT | Start 2e ydlidar instantie |
| `rtabmap_sync_launch.py` | ✅ Veilig | Enige veilige Yahboom launch file |
| `navigation_launch.py` | ✅ Veilig | Correcte Nav2 launch |
| `bringup_launch.py` | ❌ NOOIT | Start AMCL → conflict met RTAB-Map |

---

## Bekende Yahboom TF Conflicten

### `static_tf_pub_laser` node
- Publiceert conflicterende `base_link→laser_frame` transform
- **Fix:** Stoppen voor RTAB-Map sessie
```bash
docker exec humble_run pkill -9 -f static_tf_pub_laser
```

---

## Dual-Board Architectuur (Pi + Jetson)

| Taak | Pi 5 | Jetson Orin |
|---|---|---|
| STM32 serial | ✅ | ❌ |
| LiDAR driver | ✅ | ❌ |
| Camera driver | ✅ | ❌ |
| rf2o odometrie | ✅ | ❌ |
| IMU publisher | ✅ | ❌ |
| rosbridge | ✅ | ❌ |
| RTAB-Map | ❌ | ✅ (GPU) |
| Nav2 | Op Pi of Jetson | Voorkeur Jetson |
| TF publishers | ❌ | ✅ |

**DDS Discovery:**
- `ROS_DOMAIN_ID=0` op beide boards
- CycloneDDS unicast XML configs vereist (WiFi multicast onbetrouwbaar)
