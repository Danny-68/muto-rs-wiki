# 📅 Project Tijdlijn — Yahboom Muto RS

Chronologisch overzicht van alle mijlpalen, beslissingen en hardware-events.

---

## Juni 2026

### 23 juni — Projectstart & WSL setup
- **WSL2** opgezet met Ubuntu 24.04, ROS2 Jazzy, RViz2 (hardware-accelerated via WSLg)
- **Yahboom Muto RS** repository gekloond, URDF met 18 joints geladen in RViz2
- Pi 5 bevestigd als Raspberry Pi 5 Model B Rev 1.1 (Ubuntu 24.04, ROS2 Jazzy)
- SSH toegang opgezet naar Pi
- **Probleem:** WSL2 ↔ Pi ROS2 network discovery mislukt (WSL2 NAT-probleem)
- **RViz2 URDF:** Eerste visuele robot model, 18 DOF (6 poten × coxa/femur/tibia)
- Eerste tripod gait publisher aangemaakt in RViz2 als proof-of-concept

### 26 juni — Hardware documentatie & communicatieprotocol
- **Alle hardware PDFs geanalyseerd:**
  - Muto expansion board introduction
  - Baseboard communicatieprotocol
  - 35KG bus servo specificaties
  - ICM-20948 IMU datasheet
  - CSPower bus servo protocol
- **Kritieke bevinding:** Twee-laags communicatiearchitectuur:
  - Pi → STM32 (baseboard protocol)
  - STM32 → CSPower servos op USART2 (rechts) + USART3 (links)
  - Pi communiceert NIET direct met servos
- **IMU gecorrigeerd:** MPU9250 → ICM-20948 (9-axis met onboard sensor fusion)
- **Kritiek probleem ontdekt:** Baseboard protocol heeft geen command voor servo stroom (register 0x2E)
- **Brief naar Yahboom geschreven** met technisch verzoek voor firmware extensie:
  - Command 0x51: servo stroom uitlezen via STM32
  - Velocity Twist Command op adres 0x18 (Vx, Vy, Wz) voor arc locomotie
- YDLidar TG30 aansluitingsonderzoek gestart (adapter board → USB HUB → Pi)

### 26 juni — LiDAR troubleshooting & SD kaart
- Drie USB serial devices gevonden: ttyUSB0, ttyUSB1, ttyUSB2
- **LiDAR identificatie via udevadm:** CP210x = lidar, CH340 = STM32
- SD kaart uitbreidingsstrategie: kloon 64GB + verwijder ongebruikte containers
- **MutoLib ontdekt op Pi:** `/root/yahboomcar_ros2_ws/software/MutoLib/`
- Import pad bevestigd: `from MutoLib import Servo, Leg, point3d`

### 27-28 juni — Gait ontwikkeling (fase 1)
- **Phoenix-stijl tripod gait** ontworpen (geïnspireerd op Zenta/Xan/KurtE)
- **Kritieke MutoLib bevindingen:**
  - `Servo(ser)` vereist `serial.Serial` object, niet port/baudrate strings
  - `Leg(leg_index, servo_object)` constructor
  - `move_tip()` vereist `point3d` object
  - Coördinatenstelsel: +x=rechts, +y=voor, +z=omhoog
  - Poot volgorde: 0=RF, 1=RM, 2=RR, 3=LR, 4=LM, 5=LF
  - ⚠️ Fysieke poot indices 4 en 5 zijn OMGEKEERD van verwachte naam
- **Continu fase model** (φ ∈ [0,1)) op 50Hz i.p.v. discrete stappen
- **Sinusoïdale easing** toegevoegd: `0.5 - 0.5 * cos(π * t)` voor organische beweging
- **IMU yaw correctie** geïmplementeerd via baseboard command 0x60
- **Centipede wave gait** aangemaakt (achter-naar-voor golfbeweging)

### 28-29 juni — Ollama setup & gait verfijning
- **Ollama** geconfigureerd op Windows PC (RTX 5080, 16GB VRAM)
- Models: `qwen2.5:14b` en `qwen2.5-coder:14b` (elk ~9GB, Q4_K_M)
- **Open WebUI** geïnstalleerd via `uv tool install open-webui --python 3.12`
- VS Code Continue extension geconfigureerd met `apiBase: http://192.168.68.77:11434`
- **Brief definitief verstuurd naar Yahboom** met gecombineerd verzoek:
  - 0x51: servo stroom uitlezen
  - 0x18: Velocity Twist Command

### 29 juni — Phoenix gait geavanceerde features
- **Vier biologische bewegingsverbeteringen** geïmplementeerd:
  1. Body dip (neerwaartse beweging tijdens swing)
  2. Snelheidsafhankelijke voethoogte
  3. Versnelling/vertraging (ramp + exponential decay)
  4. Body sway (zwaai naar stance zijde)
- **Servo hardware interpolatie** toegevoegd: STM32 register 0x2C, 18ms executietijd
- **`--exec-time` CLI argument** voor phoenix_gait.py

### 30 juni — Dify installatie
- **Dify** geïnstalleerd op Windows 11 via Docker Desktop
- Initiële installatiemap: `C:\WINDOWS\system32\dify` ← **FOUT PAD** (later verplaatst)
- **Flask API** (`robot_bridge.py`) aangemaakt op Pi als bridge
- **Kritieke bug gevonden en gefixed:** STM32 packet length byte verkeerd berekend (off by 3)
  - Correct protocol: `0x55 0x00 0x09 0x01 ADDR DATA CHECKSUM 0x00 0xAA`
  - Checksum: `(0xFF - (length + WR + ADDR + DATA)) & 0xFF`
- **Snelheidskalibratie** uitgevoerd (vlakke ondergrond)
- **Orbbec Astra Pro Plus** geconfigureerd (udev fix voor uvcvideo conflict)
- **Audio module** (YB-MAE02-V1.0) werkend via Speech_Lib

---

## Juli 2026

### 1 juli — Sensor integratie & metingen
- **Hexapod geometrie fysiek gemeten (schuifmaat):**
  - Coxa: 27.5mm + 50.59mm (gemeten: 52mm)
  - Femur: 72.60mm (gemeten: 73mm)
  - Tibia: 134.5mm (gemeten: 140mm)
  - ⚠️ `muto_rs_gait.txt` bevat onbetrouwbare maten — NOOIT gebruiken
- **YDLidar TG30 bevestigd werkend:** `lidar_type=0` (TYPE_TOF)
- **Correct workspace:** `/home/pi/yahboomcar_ros2_ws/software/library_ws_humble/install/`
- **Snelheidstabel vastgesteld (gemeten):**

  | Step | Snelheid (m/s) |
  |------|---------------|
  | 10   | 0.027         |
  | 15   | 0.061         |
  | 18   | 0.069         |
  | 20   | 0.096         |
  | 25   | 0.125         |

- **Voice commando IDs ontdekt:**
  - 0 = wake-word "Hallo Yahboom"
  - 2 = stop, 4 = vooruit, 5 = achteruit
  - 6 = links draaien, 7 = rechts draaien
- **udev mappings permanent vastgelegd:**
  - `/dev/myserial` → ttyUSB0 (STM32 CH340)
  - `/dev/mylidar` → ttyUSB1 (YDLidar CP210x)

### 3 juli — Stack switching & Yahboom stack verkenning
- **Dify verplaatst** van `C:\WINDOWS\system32\dify` naar `D:\dify\docker`
  - Oorzaak verhuizing: Windows systeem32 permissieproblemen
  - ⚠️ **NOOIT** `robocopy /COPYALL` gebruiken → kopieert restrictieve permissies
- **Camera ROS2 sensor relay** (`sensor_relay.py`) aangemaakt in `humble_run`
- **IMU yaw correctie:** bytes d5/d6 (index 9,10 na 0x55), delen door 100
- **Stack A** volledig gedocumenteerd: robot_bridge.py (Flask, port 5000) + sensor_relay.py
- **ReAct agent** getest maar onbetrouwbaar door qwen2.5:14b JSON quoting fouten

### 4-5 juli — Stack B activatie & Dify workflow
- **Stack B** (Yahboom muto-llm-2.0) succesvol geactiveerd
- Udev mappings herbevestigd en gecorrigeerd:
  - `/dev/myserial` → ttyUSB0 (CH340) ← eerder ttyUSB1, nu permanent gefixed
- **Werkende Dify workflow architectuur:**
  ```
  Start → Decision LLM → CODE_PARSEN → IF/ELSE → 
  Iteration → Execution LLM → HTTP POST :8080/execute_commands → 
  result_parser → End
  ```
- **ELSE branch** output node hernoemd naar `reason_output` (fix: duplicate variable fout)
- `have_a_look()` (camera) en LiDAR functies werkend via `command_executor.py`
- **SSRF fix:** `SSRF_PROXY_ALLOW_PRIVATE_IPS=192.168.68.88` in Dify `.env`

### 5-6 juli — Audio probleem root cause & fix
- **Root cause audio probleem gevonden:**
  - Camera + interne C-Media audio zitten op DEZELFDE interne accu-gevoede USB hub
  - Voedingsspanning: 8.4V nominaal → 6-7V tijdens ontlading (te weinig voor USB)
- **Oplossing:** Soundblaster Play! 3 (USB ID `041e:324d`) op aparte Pi USB poort
  - Omzeilt de Yahboom expansion hub volledig
- **audio_player.py** herschreven met:
  - Automatische ALSA kaart detectie (`aplay -l` parsing)
  - Tekst-only fallback als geen speaker aanwezig
  - `voice_config.yaml` alsa_device = `null` (NOOIT hardcoden: kaart-nummers verschuiven)
  - **ALTIJD** `plughw:` prefix gebruiken, NOOIT `hw:` → "Channels count non available"

### 6-7 juli — Camera udev fix gedocumenteerd
- **Orbbec Astra Pro Plus udev fix:**
  - `/etc/udev/rules.d/56-orbbec-usb.rules`
  - Unbindt `uvcvideo` (pid 050f) en `snd-usb-audio` (pid 060f)
- **Correcte launch file:** `astro_pro_plus.launch.xml` (Yahboom typo: "astro" niet "astra")
- **Altijd:** `pkill app_muto.py` voor camera driver start
- Camera mag NIET draaien tijdens SLAM-only sessies (→ 100% CPU via sensor_relay)

### 12 juli — Stack A verbetering & SLAM mijlpaal
- **muto_driver_fixed.py** v3 aangemaakt (direct STM32 serial: 0x12/0x13)
- **SLAM toolkit regels vastgelegd (KRITIEK):**
  - NOOIT `map_slam_toolbox_launch.py` → start tweede ydlidar
  - SLAM opstartsequentie verplicht:
    1. pkill alle processen
    2. Start LiDAR → wacht op `/scan`
    3. Start rf2o
    4. Start slam_toolbox
    5. Start driver
    6. NOOIT camera tijdens SLAM-only
- **`reversion: false`** in ydlidar.yaml (true → 180° roterende scan)
- **`lidar_type: 0`** (TYPE_TOF, niet TYPE_TRIANGLE=1)
- `/dev/rplidar` tijdelijke symlink: `sudo ln -sf /dev/mylidar /dev/rplidar` (na elke reboot)

### 12 juli — Jetson Orin Nano aanschaf beslissing
- **Jetson Orin Nano Super Developer Kit** gekocht (2e hands, €300)
  - Model: P3766, part: 945-13766-0000-000
  - 8GB LPDDR5, 1024 CUDA cores, 67 TOPS in MAXN mode
- **Architectuurbeslissing:** Dual-board
  - Pi 5: STM32 serial, LiDAR, camera, rf2o odometry (latency-kritisch)
  - Jetson: RTAB-Map GPU, Nav2, YOLO, LLM (compute-zwaar)
  - Communicatie: shared `ROS_DOMAIN_ID=0` via DDS over WiFi
- **Niet mogelijk:** Muto S2 image op Jetson Orin → fundamenteel incompatibel (Tegra X1 vs Orin T234)
- **Installatieplan:** JetPack 6.1 rev 1 via NVIDIA SDK Manager → NVMe SSD

### 13 juli — RTAB-Map mijlpaal
- **RTAB-Map volledig werkend** (LiDAR + Orbbec depth camera + loop closure)
- **TF waarden definitief vastgesteld:**
  - LiDAR: x=-0.04, y=0, z=0.24, yaw=0
  - Camera: x=0.06, y=0, z=0.225, pitch=0.1047rad (6° omhoog)
- **Opstart via:** `sudo bash /home/pi/muto_rtabmap_start.sh`
- **Web visualisatie:** `http://192.168.68.88:8080/muto_viz.html`
  - Live kaart, LiDAR scan, robot positie, 6-richting besturing

### 14 juli — Nav2 werkend
- **Nav2 succesvol gestart** via `navigation_launch.py` (NIET `bringup_launch.py` → dat start AMCL)
- **scan_timestamped.py** aangemaakt: lost timestamp drop probleem op
  - Republiceert `/scan` als `/scan_fixed` met huidige timestamp
  - Drops: 2845 → 4 na fix
- **cmd_vel relay:** `ros2 run topic_tools relay /cmd_vel_nav /cmd_vel`
- **Nav2 keten bevestigd:** Nav2 → /cmd_vel → muto_driver → STM32
- `app_muto.py` bezet serial port — altijd stoppen voor Nav2

### 14 juli — Jetson Docker image gebouwd
- **Docker image:** `muto-humble-jetson:1.0` (ROS2 Humble + Nav2 + RTAB-Map + rf2o + GPU)
- **Container:** `jetson_run` (`--runtime=nvidia --net=host`)
- **DDS discovery bevestigd:** Pi en Jetson zien elkaars topics op `ROS_DOMAIN_ID=0`
- **RTAB-Map draait op Jetson GPU**
- CycloneDDS unicast config: `/home/pi/cyclone_dds.xml` en `/home/Danny/cyclone_dds.xml`

### 17 juli — IMU installatie (ICM20948)
- **Pimoroni ICM20948 extern IMU aangesloten op Pi 5 I2C bus 4**
  - Adres: 0x68
  - GPIO: SDA=pin 8 (GPIO14), SCL=pin 10 (GPIO15)
  - Config: `/boot/firmware/config.txt`: `dtoverlay=i2c-gpio,bus=4,i2c_gpio_sda=14,i2c_gpio_scl=15`
  - WHO_AM_I=0xEA bevestigd vanuit `humble_run` container
- **LCD display op I2C bus 1** adres 0x3C (pin 3 + pin 5) — aparte bus om conflict te vermijden
- **ROS2 IMU publisher** aangemaakt (`/home/pi/imu_publisher.py`, 20Hz)
- **EKF** (`robot_localization`) configureert `/odom_fused` uit rf2o + IMU

### 17-18 juli — Voetcontact detectie
- **Yahboom nooit gereageerd** op firmware verzoek (0x51 servo stroom)
- **Aanpak A** geïmplementeerd: servo positie fout detectie
  - Tibia servo IDs: 3, 6, 9, 12, 15, 18 (RF→LF)
  - Servo angle read: addr 0x60, antwoord byte index 6
  - **Grondcontact drempel:** 12° fout
  - Op grond: 20-38° fout (servo geblokkeerd)
  - In zwaaifase: 2-5° fout (alleen mechanische speling)
- **`foot_contact.py`** klaar op Pi voor integratie in muto_driver_fixed.py

### 18 juli — llama.cpp installatie & Dify koppeling
- **llama.cpp** geïnstalleerd op Windows PC (`D:\llama.cpp`, build b10064, CUDA 13.3)
- **Model:** Qwen2.5-14B-Instruct-Q4_K_M.gguf
- **Opstartcommando:** `D:\llama.cpp\start_llama.bat`
  - Port 8081, 99 GPU layers, 8192 context, 2 parallel slots
  - VRAM: ~11.4 GB van 16 GB, ~97 tokens/sec
- **Dify gekoppeld** via OpenAI-API-compatible plugin op `http://192.168.68.77:8081/v1`
- Stack B (muto_yahboom) werkend met FastAPI :8080
- **API formaat ontdekt:** `{"status": "success", "plan": [{"id": "1", "command": "forward(speed=15, duration=2)"}]}`
- **Beschikbare robot functies:** `forward()`, `backward()`, `shift_left()`, `shift_right()`, `rotate()`, `stop()`, `adjust_height()`, `have_a_look()`, en meer

---

## 🔮 Open punten (op moment van schrijven)

| Prioriteit | Taak |
|---|---|
| 🔴 Hoog | Nav2 autonoom navigeren volledig debuggen |
| 🔴 Hoog | `app_muto.py` permanent uitschakelen bij boot |
| 🟡 Midden | `foot_contact.py` integreren in muto_driver_fixed.py als ROS2 node |
| 🟡 Midden | EKF op Jetson draaien (Pi CPU verlichten) |
| 🟡 Midden | Dify vision workflow (`have_a_look`) correct configureren |
| 🟢 Laag | IMU EKF fusie verder verfijnen |
| 🟢 Laag | Seeed reComputer J3010 overwegen voor compacte Jetson integratie |
