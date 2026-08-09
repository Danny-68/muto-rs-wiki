# 🦾 Yahboom Muto RS — Project Naslagwerk

> **Eigenaar:** Dan (Meinds) | **Robot:** Yahboom Muto RS (4ROS versie, Raspberry Pi 5)
> **Doel:** Volledig autonoom, AI-aangestuurde hexapod met SLAM, Nav2, en Dify NLP-controle

---

## 📋 Inhoudsopgave

| Document | Inhoud |
|---|---|
| [📅 TIMELINE.md](docs/TIMELINE.md) | Chronologisch overzicht van alle mijlpalen (juni–augustus 2026) |
| [🗺️ ROADMAP.md](docs/ROADMAP.md) | Overkoepelend overzicht: autonome navigatie + Dify + Jetson-AI, wat werkt, wat nog moet |
| [🔧 HARDWARE.md](hardware/HARDWARE.md) | Geometrie, poot volgorde, udev, TF waarden, Jetson specs |
| [📡 PROTOCOL.md](hardware/PROTOCOL.md) | STM32 protocol, alle commando’s, CSPower, API formaten |
| [💾 SOFTWARE_STACK.md](software/SOFTWARE_STACK.md) | Stack A/B, containers, scripts, llama.cpp, Dify |
| [🗺️ SLAM_NAV2.md](slam/SLAM_NAV2.md) | RTAB-Map, rf2o, Nav2, opstartsequentie, valkuilen |
| [🦿 GAIT.md](gait/GAIT.md) | Phoenix gait, centipede, rubber band, voetcontact |
| [🤖 DIFY.md](dify/DIFY.md) | Workflow architectuur, API formaat, troubleshooting |
| [🐛 PROBLEMS.md](problems/PROBLEMS.md) | 50+ bekende problemen met definitieve fixes |
| [⏪ ROLLBACK.md](ROLLBACK.md) | Terugrollen naar een eerdere staat (git-tags, per-bestand herstel) |

### Setup (from scratch)

| Document | Inhoud |
|---|---|
| [🐧 PI_SETUP.md](setup/PI_SETUP.md) | Raspberry Pi 5 van nul opbouwen (Debian Bookworm) |
| [🤖 JETSON_SETUP.md](setup/JETSON_SETUP.md) | Jetson Orin Nano, JetPack 6.1, Docker + NVIDIA runtime |
| [🪟 WINDOWS_SETUP.md](setup/WINDOWS_SETUP.md) | Dify, llama.cpp, Ollama op Windows 11 |
| [🐳 DOCKER_SETUP.md](setup/DOCKER_SETUP.md) | Alle Docker run commando’s, mounts, images |
| [🔌 UDEV_RULES.md](setup/UDEV_RULES.md) | Exacte udev regels voor USB + camera |

### Software broncode

```
software/
  pi/
    gait/        phoenix_gait.py, centipede_gait.py, foot_contact.py
    ros2/        muto_driver_fixed.py, sensor_relay.py, scan_timestamped.py, ...
    sensors/     imu_publisher.py, imu_test.py, servo_angle_*.py, ...
    tools/       robot_bridge.py, rotate_calib.py, yahboom_oled.py, ...
    voice/       voice_raw.py, voice_raw2.py, voice_test.py
    scripts/     muto_rtabmap_start.sh, switch_*.sh, rtabmap_restart.sh, ...
    config/      cyclone_dds.xml, ekf_config.yaml, rtabmap_params.yaml, ...
  container/     muto_rtabmap_launch.py, rgbd_throttle.py, scan_relay.py
    config/      hexapod_nav_params.yaml, muto_map.yaml, rtabmap_params.yaml
  jetson/
    scripts/     muto_jetson_start.sh
    config/      cyclone_dds.xml, ekf_config.yaml
    container/   rtabmap_params.yaml
  setup/
    udev/        99-usb-serial.rules, 56-orbbec-usb.rules
    systemd/     robot-bridge.service
```

---

## ⚠️ Status-update (9 augustus 2026)

Sinds medio juli is het **RTAB-Map + Jetson**-pad hieronder **on hold** gezet wegens Pi/Jetson/WiFi-belasting (zie [PROBLEMS.md](problems/PROBLEMS.md#rtab-map--slam)). De actieve navigatie-aanpak is nu **lidar-only AMCL + Nav2 op de Pi alleen** (officieel URDF, `RegulatedPurePursuitController`) — zie [SLAM_NAV2.md](slam/SLAM_NAV2.md) voor de volledige, actuele procedure en [TIMELINE.md](docs/TIMELINE.md) voor hoe we daar kwamen. De architectuur en snelstart hieronder tonen daarom **twee** paden: het huidige (lidar-only) en het gepauzeerde (RTAB-Map/Jetson).

---

## 🏗️ Systeemarchitectuur

> **Let op:** dit diagram rendert vanaf nu met echte Unicode-tekens — de vorige versie bevatte kapotte `\u250c`-tekst-escapes (rendert als losse tekst i.p.v. kaders op GitHub).

```
┌────────────────────────────────────────────────┐
│  WINDOWS PC (192.168.68.77) · RTX 5080 16GB    │
│  Dify :80 · llama.cpp :8081 · Open WebUI      │
└──────────────────┬───────────────────────────┘
                   │ HTTP/LAN
┌──────────────────▼───────────────────────────┐
│  RASPBERRY PI 5 (192.168.68.88)                │
│  humble_run: ROS2 · rf2o · camera · IMU · bridge  │
│  muto_yahboom: FastAPI :8080 · LLM agent        │
└──────────────────┬───────────────────────────┘
                   │ USB-serial 115200
┌──────────────────▼───────────────────────────┐
│  STM32 BASEBOARD · 18× CSPower 35KG servos      │
└────────────────────────────────────────────────┘

┌────────────────────────────────────────────────┐
│  JETSON ORIN NANO (192.168.68.86)               │
│  jetson_run: RTAB-Map GPU · Nav2 · TF pub        │
│  ⏸️ ON HOLD sinds medio juli (Pi/Jetson/WiFi-load) │
└────────────────────────────────────────────────┘
```

---

## 🚀 Snelstart

```bash
# Lidar-only AMCL + Nav2 (huidige, actieve aanpak — geen Jetson nodig)
sudo bash /home/pi/muto_fase1_start.sh
# Zie SLAM_NAV2.md voor AMCL-lokalisatieprocedure + Nav2-opstart daarna

# Precisiebeweging / eenvoudige HTTP-besturing (Flask, port 5000)
python3 /home/pi/robot_bridge.py
# of: sudo systemctl start robot-bridge   (eerst app_muto.py stoppen, zie regel 7 hieronder)

# RTAB-Map + Nav2 (autonoom, ⏸️ ON HOLD — zie status-update hierboven)
sudo bash /home/pi/muto_rtabmap_start.sh

# Dify / LLM controle
sudo bash /home/pi/switch_to_yahboom.sh

# llama.cpp (Windows)
D:\llama.cpp\start_llama.bat
```

---

## ⚠️ Absolute regels (NOOIT overtreden)

1. **NOOIT** `map_slam_toolbox_launch.py` → start tweede ydlidar
2. **NOOIT** `/rtabmap/pause` → map→odom TF stopt
3. **NOOIT** `color_fps`/`depth_fps` bij camera launch → UVC crash
4. **NOOIT** twee RTAB-Map instanties tegelijk → database locked
5. **ALTIJD** `docker restart humble_run` als stap 0 voor RTAB-Map
6. **ALTIJD** `pkill -f app_muto.py` voor Nav2 start
7. **NOOIT** `app_muto.py`, `muto_driver_fixed.py` en `robot_bridge.py` gelijktijdig — delen exclusief `/dev/myserial`. `app_muto.py`'s autostart (`~/.config/autostart/app.desktop`) blijft **bewust actief** — na een koude start moet direct met de gamepad bestuurd kunnen worden. Alle stack-startscripts (`switch_to_own_stack.sh`, `switch_to_yahboom.sh`, `muto_fase1_start.sh`, `muto_rtabmap_start.sh`) stoppen `app_muto.py` al zelf als eerste stap; `robot_bridge.py` doet dit sinds 9 aug 2026 ook zelf bij het opstarten (`_stop_app_muto()`), dus je hoeft dit nooit meer handmatig te doen.
8. **ALTIJD** bij een noodstop **ook** een directe rauwe seriële STOP-byte sturen, niet alleen het ROS-proces killen — de STM32 latcht het laatste commando en blijft dat uitvoeren (zie [PROBLEMS.md](problems/PROBLEMS.md)).
9. **NOOIT** `reversion` in `ydlidar.yaml` los aanpassen zonder te checken welke laser-TF-aanpak actief is (handmatige TF ↔ `false`, officieel URDF ↔ `true`) — zie PROBLEMS.md.

---

## 📍 IP-adressen & poorten

| Apparaat | IP | Poort | Dienst |
|---|---|---|---|
| Raspberry Pi 5 | 192.168.68.88 | 8080 | Stack B FastAPI / webserver |
| Raspberry Pi 5 | 192.168.68.88 | 9090 | rosbridge WebSocket |
| Windows PC | 192.168.68.77 | 80 | Dify Studio |
| Windows PC | 192.168.68.77 | 8081 | llama.cpp API |
| Jetson Orin Nano | 192.168.68.86 | — | ROS2 DDS (geen vaste poort) |
