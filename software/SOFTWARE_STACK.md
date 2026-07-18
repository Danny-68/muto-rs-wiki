# 💾 Software Stack Referentie — Yahboom Muto RS

---

## Overzicht: Twee stacks

De robot heeft twee modi die **niet tegelijk** kunnen draaien op port 8080:

| | Stack A (eigen) | Stack B (Yahboom) |
|---|---|---|
| **Gebruik** | Eigen sensoren, SLAM, Nav2 | Dify / LLM controle |
| **Port 8080** | HTTP fileserver (muto_viz.html) | FastAPI (muto_yahboom container) |
| **Serial** | muto_driver_fixed.py via /cmd_vel | app_muto.py direct |
| **Camera** | ROS2 topics via humble_run | have_a_look() via ROS2 |
| **Starten** | `sudo bash /home/pi/muto_rtabmap_start.sh` | `sudo bash /home/pi/switch_to_yahboom.sh` |

---

## Stack A: Eigen Stack

### Componenten

| Component | Locatie | Beschrijving |
|---|---|---|
| `robot_bridge.py` | Pi host, Flask :5000 | HTTP→STM32 serial bridge |
| `sensor_relay.py` | humble_run container | ROS2→HTTP bridge |
| `muto_driver_fixed.py` | humble_run container | /cmd_vel→STM32 driver |
| `scan_timestamped.py` | humble_run container | /scan timestamp fix |
| `imu_publisher.py` | Pi host | ICM20948→/imu publisher |

### Endpoints robot_bridge.py (port 5000)

```
GET  /health                    Systeem status
GET  /robot/imu                 Yaw, pitch, roll via STM32
POST /robot/forward             Vooruit (speed, duration_s)
POST /robot/backward            Achteruit
POST /robot/stop                Stop
POST /robot/rotate              Graden roteren
POST /robot/rotate_to_angle     IMU gesloten-lus rotatie
GET  /lidar/obstacle            Hindernis detectie
GET  /camera/depth/obstacle     Diepte hindernis
GET  /camera/describe           Visuele beschrijving
```

### Starten
```bash
sudo bash /home/pi/switch_to_own_stack.sh
```

---

## Stack B: Yahboom Muto LLM Stack

### Broncode locaties

```
/root/muto-llm-2.0/packages/           ← ECHTE broncode (single-level)
/root/muto-llm-2.0/muto-llm-2.0/      ← dode kopie, NIET gebruiken
```

**Editable install finder:**
```
/usr/local/lib/python3.10/dist-packages/__editable___muto_hexapod_lib_1_0_0_finder.py
```

### Kritieke bestanden

| Bestand | Pad |
|---|---|
| command_executor.py | `/root/muto-llm-2.0/packages/muto_ros2_controller/muto_ros2_controller/command_executor.py` |
| audio_player.py | `/root/muto-llm-2.0/packages/voice_module/voice_module/core/audio_player.py` |
| voice_config.yaml | `/root/muto-llm-2.0/packages/voice_module/voice_module/config/voice_config.yaml` |
| prompt backups | `/root/muto-llm-2.0/muto-llm-2.0/prompt_backup_en/env/` |

### API formaat

**Endpoint:** `POST http://192.168.68.88:8080/execute_commands`

```json
{
  "status": "success",
  "plan": [
    {"id": "1", "command": "forward(speed=15, duration=2)"},
    {"id": "2", "command": "stop()"}
  ]
}
```

### Beschikbare robot functies (via command_executor.py)

```python
forward(speed, duration)        # Vooruit
backward(speed, duration)       # Achteruit  
shift_left(speed, duration)     # Links schuiven
shift_right(speed, duration)    # Rechts schuiven
rotate(speed, duration)         # Roteren
spin_in_place(speed, duration)  # Draaien op plek
stop()                          # Stoppen
adjust_height(level)            # Hoogte: 1=laag, 2=midden, 3=hoog
big_stride(speed, duration)     # Grote pas
have_a_look(user_query)         # Camera + AI analyse
get_lidar_data()                # LiDAR data
get_lidar_360_data()            # 360° LiDAR
get_lidar_range_at_angle(angle) # Afstand op hoek
robot_speak(text, volume)       # TTS spraak
say_hello()                     # Begroeting animatie
wave_no()                       # Nee schudden
curl_up()                       # Oprollen
stretch()                       # Strekken
warm_up_squat(action)           # Squat animatie
```

### Starten
```bash
sudo bash /home/pi/switch_to_yahboom.sh
```

---

## Docker Containers

### humble_run

```bash
# Image
muto-humble:3.5

# Start
docker start humble_run

# Schone start (aanbevolen voor RTAB-Map)
docker restart humble_run

# ROS2 environment in container
docker exec -it humble_run bash
source /opt/ros/humble/setup.bash
source /home/pi/yahboomcar_ros2_ws/software/library_ws_humble/install/setup.bash
```

**Devices die de container nodig heeft:**
- `/dev/myserial` (STM32)
- `/dev/mylidar` (YDLidar)
- `/dev/i2c-4` (IMU)
- Orbbec camera via USB

### muto_yahboom

```bash
# Image
muto-humble:3.5 (zelfde als humble_run)

# Gestart door switch_to_yahboom.sh
# FastAPI op port 8080
# Deelt ROS_DOMAIN_ID=0 met humble_run via --net=host
```

### jetson_run (Jetson)

```bash
# Image
muto-humble-jetson:1.0

# Start
sudo docker start jetson_run

# Bevat: ROS2 Humble, Nav2, RTAB-Map, rf2o, GPU support
# Runtime: --runtime=nvidia --net=host
```

---

## MutoLib API

```python
from MutoLib import Servo, Leg, point3d

# Initialisatie
import serial
ser = serial.Serial('/dev/myserial', 115200)
servo = Servo(ser)
leg = Leg(leg_index, servo)  # leg_index 0-5

# Beweging
pos = point3d(x, y, z)  # mm, +x=rechts +y=voor +z=omhoog
leg.move_tip(pos)        # ENIGE correcte servo interface
```

**MutoLib locaties:**
- Container: `/root/yahboomcar_ros2_ws/software/MutoLib/`
- Pi host: `/home/pi/muto/MutoLib/`

**⚠️ Regel:** STM32 gait commands (0x12-0x17) resetten alle servo posities → niet combineerbaar met move_tip()

---

## Opstartscripts Overzicht

| Script | Locatie | Functie |
|---|---|---|
| `muto_rtabmap_start.sh` | `/home/pi/` | Volledige RTAB-Map + Nav2 stack (9 stappen) |
| `switch_to_yahboom.sh` | `/home/pi/` | Switch naar Stack B |
| `switch_to_own_stack.sh` | `/home/pi/` | Switch naar Stack A |
| `rtabmap_restart.sh` | `/home/pi/` | Veilig alleen rtabmap_slam herstarten |
| `muto_jetson_start.sh` | `/home/Danny/` (Jetson) | Jetson stack (5 stappen) |
| `start_llama.bat` | `D:\llama.cpp\` | llama.cpp server starten (Windows) |

---

## llama.cpp (Windows PC)

```
Locatie:    D:\llama.cpp\
Build:      b10064
CUDA:       13.3
Model:      Qwen2.5-14B-Instruct-Q4_K_M.gguf (D:\llama.cpp\models\)
Port:       8081
Endpoint:   http://192.168.68.77:8081/v1
VRAM:       ~11.4 GB van 16 GB
Snelheid:   ~97 tokens/sec
```

**Startcommando:**
```
D:\llama.cpp\llama-server.exe
  --model "D:\llama.cpp\models\Qwen2.5-14B-Instruct-Q4_K_M.gguf"
  --host 0.0.0.0 --port 8081
  --n-gpu-layers 99 --ctx-size 8192
  --batch-size 512 --ubatch-size 512
  --threads 8 --parallel 2
  --flash-attn on
  --alias "qwen2.5-14b-instruct"
```

Context per slot = 8192 / 2 = **4096 tokens per slot**.

---

## Dify Configuratie

```
Installatie:  D:\dify\docker\
Studio:       http://localhost/apps   (NIET http://192.168.68.77)
API endpoint: http://192.168.68.77:8081/v1
```

**Kritieke .env instellingen:**
```env
SSRF_PROXY_ALLOW_PRIVATE_IPS=192.168.68.88
```

**Na schema update in Dify:** altijd "Configure" knop klikken in Tool List.
