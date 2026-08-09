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

### (medio juli, exacte datum niet vastgelegd) — RTAB-Map/Jetson roadmap on hold
- Uitgebreid gemeten (`ros2 topic hz`/`bw` op `/rgbd_image`, herhaalde `uptime`, `vcgencmd get_throttled`/`measure_temp`) tijdens gecombineerd Pi+Jetson RTAB-Map-gebruik — signalen van te hoge belasting.
- `/rgbd_image` teruggebracht naar 3Hz via `topic_tools throttle` als tegenmaatregel — onvoldoende verbetering.
- **Beslissing:** `switch_to_yahboom.sh` gebruikt om over te schakelen naar een lidar-only aanpak zonder Jetson/camera-afhankelijkheid. RTAB-Map/Jetson-pad blijft *on hold*, niet verwijderd — zie [PROBLEMS.md](../problems/PROBLEMS.md#rtab-map--slam) voor de heropname-voorwaarde.

---

## Juli–Augustus 2026 — Nav2 live-debugsessies (lidar-only, geen Jetson)

> Vanaf hier is de aanpak: officieel URDF + AMCL + lidar-only (Pi-alleen), i.p.v. RTAB-Map/Jetson. Zie [SLAM_NAV2.md](../slam/SLAM_NAV2.md) voor de volledige, actuele procedure.

### 30 juli — Drie echte bugs gevonden en opgelost
- **Laser-TF 180° verkeerd om:** verklaart het herhaaldelijk waargenomen patroon dat de robot de kleinste i.p.v. grootste vrije ruimte opzoekt. Fix: 180°-yaw op de static transform.
- **`inflation_radius` (0.2) kleiner dan inscribed radius (0.255):** Nav2 gaf dit expliciet als ERROR. Fix: `inflation_radius: 0.35`.
- **Driver negeerde `cmd_vel`-snelheid:** elke beweging ging met hardcoded level 15. Fix: nieuwe driver op de officiële `MutoLibCore.Muto`-klasse, schaalt naar levels.
- **Nieuwe observatie:** discrete gait-cyclus (~0.45s per commando) i.p.v. continue snelheid — fundamenteel ander bewegingsmodel dan Nav2's DWB-controller aanneemt.

### 30 juli — Audit tegen Yahboom's officiële stack
- Yahboom gebruikt een volledig **URDF-model** (wij: handmatige static transforms) — bevat letterlijk de 180°-laser-correctie die we net empirisch hadden gevonden.
- **YDLidar `reversion`-mismatch:** Yahboom zet `reversion: True` voor het 4ROS-pad, wij hadden `false`.
- **EKF mist IMU-oriëntatiefusie:** Yahboom fuseert absolute yaw + yaw-rate, wij alleen yaw-rate (onze IMU publiceert geen orientation).
- Controller gewisseld: DWB → `RegulatedPurePursuitController` + rechthoekig footprint — meetbare verbetering, robot maakte voor het eerst echte voortgang richting doel.
- **Bevinding:** `odom_fused` wijkt tot een kwart slag af na snelle rotatie (sporadisch `rf2o`-trackingverlies, geen consistente schaalfout). Lagere rotatiesnelheid (level 20 i.p.v. 30) verbeterde dit van -49.6° naar -11.3° afwijking.
- **Herontdekt:** het rotatie-drift-probleem was al opgelost in `robot_bridge.py` (STM32-onboard-yaw + vaste overshoot-marge) — een ander, onafhankelijk systeem dan de rf2o/EKF-aanpak van vandaag.

### 31 juli — Koude start: officieel URDF ingevoerd
- `robot_state_publisher` + `joint_state_publisher` met Yahboom's officiële `Muto.urdf` vervangt de handmatige static transforms.
- Tegelijk `reversion: false → true` in `ydlidar.yaml` (hoort bij de URDF-overstap, zie PROBLEMS.md-nuance).
- **Losse bevinding:** 90°-brede blinde sector in de lidar-scan bleek een fysiek losse stekker, geen software-bug.

### 31 juli — Nav2 + AMCL-procedure + grote driverbug gefixt
- AMCL-lokalisatieprocedure zonder Foxglove-kennis uitgewerkt: `/reinitialize_global_localization` + gedoseerde rotatie-bursts + kaart-screenshot-correctie + laser-raycast-verificatie.
- **Grote bug gevonden en gefixt:** driver stuurde x/y/z nooit gecombineerd — elke kleine rotatie in een Nav2-commando gooide de voorwaartse snelheid volledig weg. Nu altijd `move(x,y,z)` gecombineerd, zoals Yahboom's officiële driver.

### 31 juli — Door de deuropening: gait-ontdekking + bijna-aanvaring
- **Fine-scan-techniek** ontwikkeld: deuropeningen precies lokaliseren via laser-scan-sprongen (herbruikbaar voor elke doorgang).
- **Kern-ontdekking:** `move()`'s aangenomen snelheid (level×0.01 m/s) was nooit gevalideerd en klopt niet (niveau 15 = 0.059 m/s, niet 0.15 m/s). Een bestaande, geverifieerde kalibratietabel (`robot_config.json`) en `robot_bridge.py`'s gekalibreerde `distance_m`/`rotate_to_angle`-commando's bleken al te bestaan.
- **Bijna-aanvaring:** eerste documentatie van yaw-drift tijdens *recht vooruit* lopen (eerder alleen bekend tijdens draaien) — robot dreigde tegen een deurpost te draaien, gebruiker greep bijna in. Hersteld met `rotate_to_angle`, daarna kleine geverifieerde stappen — robot bereikte de gang.
- Robot fysiek veilig, doel van de sessie gehaald.

### 7 augustus — Forward-drift gekwantificeerd, rotate_to_angle-bug gefixt
- **Forward-yaw-drift gekwantificeerd** (n=5): gemiddeld **-5.2°/0.3m**, consistent (std.dev ~0.86°) — systematische oorzaak.
- **`rotate_to_angle`-overshoot-model fundamenteel fout:** coast bleek ~11-16° vrijwel onafhankelijk van de doelhoek, niet evenredig zoals de oude formule aannam. Fix: vaste marge (14°) i.p.v. schaling. Gevalideerd n=15: gemiddelde afwijking van 10-17° naar **-0.8°**.
- **Batch-correctie tijdens lopen:** elke 2-3 stappen (~0.3m) laten drift accumuleren, dan één `rotate_to_angle`-correctie — werkte, robot **tweede keer succesvol door de deur**.
- **Gevonden, nog niet gefixt:** docstring-bug in `rotate_to_angle()` (links/rechts stond verkeerd om beschreven — code zelf was altijd al correct).

### 9 augustus — Codeaudit: bugs ontkracht/gefixt, robot_bridge.py uitgebreid
- **`MutoLibCore.move()`'s hardcoded `level=15`** (leek een grote onopgeloste bug) bleek **geen bug in het draaiende systeem** — de daadwerkelijk geïmporteerde module (`dist-packages`, niet de host-clone) heeft de originele, wél-werkende `move()`. Wel een reële package-installatie-verwarring blootgelegd (3 kopieën uit elkaar gelopen, zie PROBLEMS.md).
- **IMU-magnetometerfusie:** rootcause bevestigd (ongevalideerde as-remap-aanname + geen hard/soft-iron-kalibratie + mogelijke servo-interferentie) — fix nog niet geïmplementeerd.
- **RTAB-Map/`slam_toolbox`-alternatieven geëvalueerd:** `hexapod_slam_localization.launch.py` lost het "automatisch heroriënteren"-probleem niet op (zelfde vaste-start-pose-beperking als AMCL). `rtabmap_localization_launch.py` zou dat wél kunnen, maar er bestaat nergens een `rtabmap.db` — vereist eerst een volledige nieuwe mapping-sessie.
- **Forward-drift-correctie geautomatiseerd:** `_forward_with_drift_correction()` toegevoegd aan `robot_bridge.py`, opt-in via `POST /robot/forward {"correct_drift": true, "distance_m": ...}`.
- **`robot-bridge.service`** (systemd) aangemaakt — bewust *disabled* i.p.v. auto-start, want `app_muto.py` start al automatisch op via `~/.config/autostart/app.desktop` en deelt dezelfde seriële poort.
- **Docstring-fix** `rotate_to_angle()` (links/rechts).
- **OLED-scherm bevestigd werkend** (was onduidelijk gedocumenteerd sinds de sessie van 26 juni) — hardware + driver + autostart intact, gebruiker bevestigde leesbare data op het scherm.
- **Live rotatietests uitgevoerd** (robot aan, gebruiker als toezicht): coast-model bij hoeken <14° gekwantificeerd (blijkt een vaste ~5-6° minimum-puls, niet evenredig), links/rechts-asymmetrie op 25° bevestigd (rechts 3× zo onvoorspelbaar als links, geen vaste bias), en de openstaande vraag uit 13h beantwoord: `ROTATE_STEP=15` geeft 3-4× meer overshoot zonder tijdwinst t.o.v. `ROTATE_STEP=10` — step=10 blijft de juiste keuze. Zie [PROBLEMS.md](../problems/PROBLEMS.md#-rotatie--precisiebeweging-robot_bridgepy) voor de volledige cijfers.
- **Forward-drift-correctie live getest, twee bugs gevonden en gefixt:** eerste versie had een tekenfout (`rotate_to_angle(-drift)` i.p.v. `rotate_to_angle(drift)`) die de afwijking verergerde in plaats van herstelde (0.6m: -14.2° werd -62.2°) — direct live ontdekt en gefixt. Na de tekenfix bleef per-batch correctie nog steeds matig omdat een enkele batch-drift (~5-6°) in de onbetrouwbare sub-14°-zone valt; drempel opgehoogd naar 15° (2-3 batches accumuleren, zoals sectie 18.5). **Eindresultaat: 0.9m ongecorrigeerd -17.4°, gecorrigeerd -0.7°.**

---

## 🔮 Open punten (bijgewerkt 9 augustus 2026)

| Prioriteit | Taak |
|---|---|
| 🔴 Hoog | `app_muto.py` permanent uitschakelen bij boot (start nu nog automatisch via `~/.config/autostart/app.desktop`, botst met `robot_bridge.py`/ROS-driver) |
| 🔴 Hoog | IMU-magnetometer hard/soft-iron-kalibratie + as-remap valideren (rootcause bekend, fix nog niet geïmplementeerd) |
| 🟡 Midden | 3 uiteenlopende kopieën van `MutoLibCore.py` (host-clone, wiki-mirror, live dist-packages) opschonen |
| 🟢 Laag | Sub-14°-rotaties bruikbaar maken (nu een vaste ~5-6° minimum-puls, niet evenredig) — bijv. een minimale looptijd forceren vóór de stopconditie geëvalueerd wordt |
| 🟢 Laag | Rootcause van de grotere onvoorspelbaarheid bij rechtsom draaien (std.dev 4.6° vs 1.4° links) — STM32-firmware is niet lokaal beschikbaar, dus hardwarematig verder uitzoeken heeft een harde grens |
| 🟢 Laag | `hexapod_slam_localization.launch.py`/`rtabmap_localization_launch.py` verder bekijken als er ooit een RTAB-Map-database wordt opgebouwd |
| 🟢 Laag | RTAB-Map/Jetson-pad alleen heroverwegen bij een lichtere/lokale variant zonder Jetson (zie PROBLEMS.md) |
| 🟢 Laag | `foot_contact.py` integreren in muto_driver_fixed.py als ROS2 node |
| 🟢 Laag | Dify vision workflow (`have_a_look`) correct configureren |
| 🟢 Laag | Discrete gait-cyclus (~0.45s/commando) — uitzoeken of een snellere aanroepmethode bestaat binnen `muto_hexapod_lib` |
