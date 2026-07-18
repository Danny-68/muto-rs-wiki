# 🦾 Yahboom Muto RS — Project Naslagwerk

> **Eigenaar:** Dan (Meinds) | **Robot:** Yahboom Muto RS (4ROS versie, Raspberry Pi 5)  
> **Doel:** Volledig autonoom, AI-aangestuurde hexapod met SLAM, Nav2, en Dify NLP-controle

---

## 📋 Inhoudsopgave

| Document | Inhoud |
|---|---|
| [📅 TIMELINE.md](docs/TIMELINE.md) | Chronologisch overzicht van alle mijlpalen |
| [🔧 HARDWARE.md](hardware/HARDWARE.md) | Volledige hardwarebeschrijving en aansluitingen |
| [💾 SOFTWARE_STACK.md](software/SOFTWARE_STACK.md) | Stack A, Stack B, containers, scripts |
| [🗺️ SLAM_NAV2.md](slam/SLAM_NAV2.md) | RTAB-Map, rf2o, Nav2 setup en regels |
| [🦿 GAIT.md](gait/GAIT.md) | Gait-ontwikkeling, MutoLib, phoenix gait |
| [🤖 DIFY.md](dify/DIFY.md) | Dify workflow, llama.cpp, LLM-keten |
| [🐛 PROBLEMS.md](problems/PROBLEMS.md) | Alle bekende problemen + definitieve fixes |
| [📡 PROTOCOL.md](hardware/PROTOCOL.md) | STM32 baseboard protocol, servo protocol |

---

## 🏗️ Architectuuroverzicht

```
┌─────────────────────────────────────────────────────────┐
│                    WINDOWS PC (192.168.68.77)           │
│   RTX 5080 · 16GB VRAM                                  │
│   ┌──────────┐  ┌──────────────┐  ┌──────────────────┐ │
│   │  Dify    │  │  llama.cpp   │  │   Open WebUI     │ │
│   │ :80      │  │  :8081       │  │   :8080 (lokaal) │ │
│   │(localhost)│  │Qwen2.5-14B  │  │                  │ │
│   └──────────┘  └──────────────┘  └──────────────────┘ │
└───────────────────────┬─────────────────────────────────┘
                        │ HTTP (LAN 192.168.68.x)
┌───────────────────────▼─────────────────────────────────┐
│              RASPBERRY PI 5 (192.168.68.88)             │
│   ┌─────────────────────────────────────────────────┐   │
│   │  Docker: humble_run (muto-humble:3.5)           │   │
│   │  ROS2 Humble · RTAB-Map · rf2o · rosbridge      │   │
│   │  Camera driver · scan_timestamped · IMU pub      │   │
│   └─────────────────────────────────────────────────┘   │
│   ┌─────────────────────────────────────────────────┐   │
│   │  Docker: muto_yahboom (muto-humble:3.5)         │   │
│   │  FastAPI :8080 · muto_controller · Dify-agent   │   │
│   └─────────────────────────────────────────────────┘   │
│                                                          │
│   /dev/myserial (ttyUSB0) → STM32 baseboard            │
│   /dev/mylidar  (ttyUSB1) → YDLidar TG30               │
│   Orbbec Astra Pro Plus   → USB direct                  │
│   ICM20948 IMU            → I2C bus 4 (GPIO 14/15)      │
└───────────────────────┬─────────────────────────────────┘
                        │ USB-serial 115200 baud
┌───────────────────────▼─────────────────────────────────┐
│              STM32 BASEBOARD (YB-MAE02-V1.0)            │
│   USART2 → Rechter poten (RF, RM, RR)                   │
│   USART3 → Linker poten (LF, LM, LR)                    │
│   18× CSPower 35KG bus servos                           │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│        JETSON ORIN NANO SUPER (192.168.68.86)           │
│   8GB LPDDR5 · 1024 CUDA cores · 67 TOPS               │
│   Extern (niet op chassis) · 19V voeding                │
│   Docker: jetson_run · RTAB-Map GPU · Nav2              │
└─────────────────────────────────────────────────────────┘
```

---

## 🚀 Snelstart — volledig systeem opstarten

### RTAB-Map + Nav2 stack (autonoom)
```bash
# 🐧 PI TERMINAL
sudo bash /home/pi/muto_rtabmap_start.sh
```

### Dify / LLM controle stack
```bash
# 🐧 PI TERMINAL
sudo bash /home/pi/switch_to_yahboom.sh
```

### Terug naar eigen stack
```bash
# 🐧 PI TERMINAL
sudo bash /home/pi/switch_to_own_stack.sh
```

### llama.cpp starten (Windows)
```
D:\llama.cpp\start_llama.bat
```
Dify Studio: `http://localhost/apps`

---

## ⚠️ Absolute regels (NOOIT overtreden)

1. **NOOIT** `map_slam_toolbox_launch.py` gebruiken → start tweede ydlidar
2. **NOOIT** `/rtabmap/pause` aanroepen → map→odom TF stopt
3. **NOOIT** `color_fps` of `depth_fps` argumenten bij camera launch → UVC crash
4. **NOOIT** twee RTAB-Map instanties tegelijk (Pi + Jetson) → database locked
5. **ALTIJD** `docker restart humble_run` als stap 0 voor RTAB-Map sessies
6. **ALTIJD** `pkill -f app_muto.py` voor Nav2 start → serial port conflict

---

## 📍 IP-adressen

| Apparaat | IP | Rol |
|---|---|---|
| Raspberry Pi 5 | 192.168.68.88 | Robot compute, sensors |
| Windows PC | 192.168.68.77 | Dify, llama.cpp, Open WebUI |
| Jetson Orin Nano | 192.168.68.86 | GPU compute (extern) |

---

## 📁 Belangrijke paden

| Pad | Inhoud |
|---|---|
| `/home/pi/muto_rtabmap_start.sh` | RTAB-Map opstartscript (9 stappen) |
| `/home/pi/switch_to_yahboom.sh` | Switch naar Stack B |
| `/home/pi/switch_to_own_stack.sh` | Switch naar Stack A |
| `/home/pi/imu_publisher.py` | ICM20948 ROS2 publisher (20Hz) |
| `/home/pi/foot_contact.py` | Voetcontact detectie module |
| `/root/rtabmap_params.yaml` | RTAB-Map parameters (in container) |
| `/root/hexapod_nav_params_custom.yaml` | Nav2 parameters |
| `/root/muto-llm-2.0/packages/` | Yahboom LLM stack broncode |
| `D:\llama.cpp\` | llama.cpp installatie (Windows) |
| `D:\dify\docker\` | Dify Docker installatie (Windows) |
