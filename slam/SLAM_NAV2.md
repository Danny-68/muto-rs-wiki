# 🗺️ SLAM & Nav2 Referentie — Yahboom Muto RS

---

## 🟢 HUIDIGE AANPAK (sinds 30 juli 2026): lidar-only AMCL, geen Jetson

> Het RTAB-Map/Jetson-gedeelte verderop in dit document is **on hold** sinds medio juli 2026 wegens Pi/Jetson/WiFi-belasting (zie [PROBLEMS.md](../problems/PROBLEMS.md#rtab-map--slam)). Dit is de actieve, geverifieerde aanpak.

### Opstarten
```bash
# 🐧 PI TERMINAL — start lidar, robot_state_publisher (officieel URDF), rf2o, EKF, driver
sudo bash /home/pi/muto_fase1_start.sh

# Daarna Nav2 met de bestaande kaart:
ros2 launch hexapod_nav hexapod_navigation.launch.py \
  map:=/root/maps/lidar_only_map.yaml \
  params_file:=/root/hexapod_nav_params_custom.yaml
```
**Vóór start:** `pkill -f app_muto.py` (bezet anders `/dev/myserial`, zie README-regel 7).

### Kernonderdelen
| Onderdeel | Wat | Waarom |
|---|---|---|
| **Officieel URDF** (`robot_state_publisher` + `joint_state_publisher`, Yahboom's `Muto.urdf`) | Vervangt handmatige `static_transform_publisher`-commando's | Bevat de al-bekende 180°-laser-correctie; voorkomt de TF-fouten die met handmatige transforms zijn gemaakt |
| `ydlidar.yaml`: `reversion: true` | Hoort bij het officiële URDF (zie PROBLEMS.md-nuance) | Yahboom's eigen 4ROS-launch gebruikt exact deze combinatie |
| **`RegulatedPurePursuitController`** i.p.v. DWB | `FollowPath`-plugin in `hexapod_nav_params_custom.yaml`, params overgenomen van Yahboom's `nav2_kilted.yaml` | Vermijdt DWB's rotate-then-translate-oscillatie; rotatie pas geforceerd bij >45° koersfout |
| Rechthoekig footprint `[[0.14,0.11],[0.14,-0.11],[-0.14,-0.11],[-0.14,0.11]]` + `inflation_radius: 0.35` | i.p.v. cirkelvormig `robot_radius` | Past beter bij de langwerpige hexapod-vorm; 0.35 voorkomt Nav2's "inflation smaller than inscribed radius"-ERROR |
| `muto_driver_fixed.py` v5/v6 | Combineert **altijd** x/y/z in één `move()`-aanroep | Voorkomt dat rotatie de voorwaartse snelheid wegkaapt (zie PROBLEMS.md) |

### AMCL-lokalisatieprocedure (zonder Foxglove-kennis nodig)
1. `ros2 service call /reinitialize_global_localization std_srvs/srv/Empty '{}'`
2. Gedoseerde rotatie-bursts sturen (`angular.z=0.25`, ~2s, met stop erna) — kleiner dan `update_min_a: 0.2 rad` (~11.5°) geeft géén nieuwe AMCL-schatting, dus bursts ruim daarboven houden.
3. Positie convergeert meestal vlot; **yaw convergeert soms niet vanzelf** (lokale kaartsymmetrie of rf2o-onbetrouwbaarheid).
4. Bij vastlopende yaw: gemarkeerde kaartafbeelding genereren (rode stip+pijl op AMCL-schatting) en de gebruiker een koerscorrectie laten inschatten → als nieuwe, striktere `/initialpose`-prior toepassen.
5. **Verificatie:** live `/scan_fixed` op 0°/90°/180°/270° vergelijken met een raycast tegen de `.pgm`-kaart vanaf de huidige AMCL-pose — grote afwijkingen op meerdere richtingen = echte lokalisatiefout.

### Precisiebeweging (geen Nav2, directe STM32-aansturing)
Voor kleine, nauwkeurige stappen (bijv. door een deuropening) is `robot_bridge.py` (Flask, port 5000) betrouwbaarder dan Nav2/`cmd_vel`-bursts:
- `POST /robot/forward {"distance_m": 0.3, "correct_drift": true}` — gekalibreerde afstand + automatische yaw-drift-correctie (sinds 9 aug 2026).
- `POST /robot/rotate_to_angle {"angle_deg": ...}` — closed-loop rotatie op de STM32-onboard-yaw, nauwkeuriger dan `rf2o`/EKF tijdens snelle rotatie.
- **Nooit** tijdsduur combineren met een aangenomen snelheid (`level × 0.01 m/s` klopt niet, zie PROBLEMS.md) — gebruik altijd de gekalibreerde commando's.
- **Nooit** tegelijk met `muto_driver_fixed.py`/`app_muto.py` — delen `/dev/myserial`.

### Bekende, nog niet opgeloste beperking
De STM32-gaitcyclus verwerkt commando's in discrete stappen van ~0.45s, niet continu zoals Nav2's DWB/Pure-Pursuit-controllers (5Hz) aannemen. Verklaart mogelijk waarom zelfs een correcte controller een bewegend lookahead-punt niet nauwkeurig kan volgen. Zie [PROBLEMS.md](../problems/PROBLEMS.md#-nav2--driver-lidar-only-amcl-aanpak-sinds-30-juli-2026).

---

## ⏸️ GEPAUZEERD: RTAB-Map + Jetson (camera-based, dual-board)

> On hold sinds medio juli 2026 — Pi/Jetson/WiFi-belasting te hoog gebleken (zie PROBLEMS.md). Onderstaande inhoud blijft staan voor het geval een lichtere/lokale variant zonder Jetson ooit haalbaar blijkt; **niet de huidige aanpak.**

### Opstartscript (enkelvoudig commando)

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
