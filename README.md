# 🦾 Yahboom Muto RS — Project Naslagwerk

> **Eigenaar:** Dan (Meinds) | **Robot:** Yahboom Muto RS (4ROS versie, Raspberry Pi 5)
> **Doel:** Volledig autonoom, AI-aangestuurde hexapod met SLAM, Nav2, en Dify NLP-controle

---

## 📋 Inhoudsopgave

| Document | Inhoud |
|---|---|
| [📅 TIMELINE.md](docs/TIMELINE.md) | Chronologisch overzicht van alle mijlpalen (juni–juli 2026) |
| [🔧 HARDWARE.md](hardware/HARDWARE.md) | Geometrie, poot volgorde, udev, TF waarden, Jetson specs |
| [📡 PROTOCOL.md](hardware/PROTOCOL.md) | STM32 protocol, alle commando’s, CSPower, API formaten |
| [💾 SOFTWARE_STACK.md](software/SOFTWARE_STACK.md) | Stack A/B, containers, scripts, llama.cpp, Dify |
| [🗺️ SLAM_NAV2.md](slam/SLAM_NAV2.md) | RTAB-Map, rf2o, Nav2, opstartsequentie, valkuilen |
| [🦿 GAIT.md](gait/GAIT.md) | Phoenix gait, centipede, rubber band, voetcontact |
| [🤖 DIFY.md](dify/DIFY.md) | Workflow architectuur, API formaat, troubleshooting |
| [🐛 PROBLEMS.md](problems/PROBLEMS.md) | 40+ bekende problemen met definitieve fixes |

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
```

---

## 🏗️ Systeemarchitectuur

```
\u250c\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2510
\u2502  WINDOWS PC (192.168.68.77) \u00b7 RTX 5080 16GB    \u2502
\u2502  Dify :80 \u00b7 llama.cpp :8081 \u00b7 Open WebUI      \u2502
\u2514\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u252c\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2518
                   \u2502 HTTP/LAN
\u250c\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u25bc\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2510
\u2502  RASPBERRY PI 5 (192.168.68.88)                \u2502
\u2502  humble_run: ROS2 \u00b7 rf2o \u00b7 camera \u00b7 IMU \u00b7 bridge  \u2502
\u2502  muto_yahboom: FastAPI :8080 \u00b7 LLM agent        \u2502
\u2514\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u252c\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2518
                   \u2502 USB-serial 115200
\u250c\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u25bc\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2510
\u2502  STM32 BASEBOARD \u00b7 18\u00d7 CSPower 35KG servos      \u2502
\u2514\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2518

\u250c\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2510
\u2502  JETSON ORIN NANO (192.168.68.86)               \u2502
\u2502  jetson_run: RTAB-Map GPU \u00b7 Nav2 \u00b7 TF pub        \u2502
\u2514\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2518
```

---

## 🚀 Snelstart

```bash
# RTAB-Map + Nav2 (autonoom)
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

---

## 📍 IP-adressen & poorten

| Apparaat | IP | Poort | Dienst |
|---|---|---|---|
| Raspberry Pi 5 | 192.168.68.88 | 8080 | Stack B FastAPI / webserver |
| Raspberry Pi 5 | 192.168.68.88 | 9090 | rosbridge WebSocket |
| Windows PC | 192.168.68.77 | 80 | Dify Studio |
| Windows PC | 192.168.68.77 | 8081 | llama.cpp API |
| Jetson Orin Nano | 192.168.68.86 | — | ROS2 DDS (geen vaste poort) |
