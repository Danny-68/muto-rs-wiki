# 🐛 Probleem & Fix Register — Yahboom Muto RS

Geordend per categorie. Raadpleeg bij elk probleem eerst dit document.

---

## 🗺️ RTAB-Map / SLAM

### "database is locked"
- **Oorzaak:** Twee RTAB-Map instanties actief (Pi + Jetson tegelijk)
- **Fix:** Stop Pi instantie: `docker exec humble_run pkill -9 -f rtabmap`

### "map→odom TF stopt" / robot verdwijnt van kaart
- **Oorzaak:** `/rtabmap/pause` aangeroepen
- **Fix:** **NOOIT `/rtabmap/pause` gebruiken.** Herstart rtabmap_slam via `rtabmap_restart.sh`
- **Correcte manier:** `sudo bash /home/pi/rtabmap_restart.sh`

### Kaart roteert / chaos
- **Oorzaak:** Meerdere ydlidar instanties actief
- **Fix:**
  ```bash
  pkill -9 -f ydlidar
  # Wacht 3 seconden, dan opnieuw starten
  ```

### Kaart heeft dubbele camera cones
- **Oorzaak:** Oude database + verkeerde TF, of Pi publiceert ook TF terwijl Jetson dat doet
- **Fix:**
  ```bash
  # Wis database
  rm /root/.ros/rtabmap.db*
  # Stop Pi TF publishers als Jetson ze publiceert
  docker exec humble_run pkill -9 -f static_transform
  ```

### "RTAB-Map: Did not receive data"
- **Oorzaak:** QoS mismatch of rgbd_image heeft Publisher count 0
- **Fix:** Check of rgbd_sync draait met `qos:=1` (BEST_EFFORT, niet 2=RELIABLE)

### scan staat 90° gedraaid
- **Oorzaak:** Verkeerde laser TF yaw waarde
- **Fix:** Definitieve yaw waarde = **0** (niet 1.5708 of -1.5708)

---

## 📡 TF Publishers

### Meerdere static_transform publishers
- **Oorzaak:** Container herstarten via pkill stopt niet alle processen correct
- **Fix:** Container herstarten (NIET alleen pkill): `docker restart humble_run`

### Twee camera cones zichtbaar in kaart
- **Oorzaak:** Pi publiceert ook TF terwijl Jetson dat al doet
- **Fix:** `docker exec humble_run pkill -9 -f static_transform`

---

## 📷 Camera (Orbbec Astra Pro Plus)

### Camera crasht met "set uvc ctrl error Invalid mode"
- **Oorzaak:** fps argumenten meegegeven bij launch
- **Fix:** **NOOIT** `color_fps` of `depth_fps` argumenten gebruiken
- **Correct:** `ros2 launch astra_camera astro_pro_plus.launch.xml`

### rgbd_sync ontvangt geen data
- **Oorzaak:** rgbd_sync draait met `qos:=2` (RELIABLE) maar camera publiceert BEST_EFFORT
- **Fix:** `qos:=1` gebruiken bij rgbd_sync

### rgbd_sync meerdere instanties
- **Oorzaak:** pkill doodt niet alle instanties
- **Fix:** Enige betrouwbare fix: `docker restart humble_run`

### Camera geeft "Resource busy"
- **Oorzaak:** `app_muto.py` draait nog
- **Fix:** `pkill -f app_muto.py` voor camera driver start

### Verkeerde launch bestandsnaam
- **Yahboom typo:** Bestand heet `astro_pro_plus.launch.xml` (met 'o', niet "astra")

---

## 🌐 DDS / Netwerk

### DDS verbinding valt weg na container restart
- **Oorzaak:** Multicast over WiFi onbetrouwbaar
- **Fix:** CycloneDDS unicast config staat in:
  - `/home/pi/cyclone_dds.xml` (Pi)
  - `/home/Danny/cyclone_dds.xml` (Jetson)
  - `CYCLONEDDS_URI` al in opstartscripts

### Topics zichtbaar maar geen data
- **Oorzaak:** DDS rediscovery nodig na restart
- **Fix:** Wacht 30 seconden of herstart container

---

## 🛞 rf2o Odometrie

### rf2o "Waiting for laser_scans" op Jetson
- **Oorzaak:** Scan komt van Pi via WiFi, hapert
- **Fix:** rf2o altijd op **Pi** draaien

### rf2o publiceert topic naam
- **Pi (via launch file):** publiceert naar `/odom`
  - RTAB-Map remap: `--remap odom:=/odom`
- **Jetson (als ooit los gestart):** publiceert naar `/odom_rf2o`
  - RTAB-Map remap: `--remap odom:=/odom_rf2o`

---

## 🌐 Webserver

### Webserver stopt na SSH disconnect
- **Oorzaak:** Niet gestart met nohup+disown
- **Fix:**
  ```bash
  nohup python3 -m http.server 8080 --directory /home/pi > /tmp/webserver.log 2>&1 & disown
  ```

### Poort 8080 bezet maar geen response
- **Oorzaak:** Proces draait in container, niet op host
- **Fix:** `docker exec humble_run ss -tlnp | grep 8080`

---

## 🤖 Robot beweegt niet / stopt niet

### Robot blijft lopen na loslaten besturingsknop
- **Oorzaak:** `timeout_check` in muto_driver_fixed.py staat op 2.0s
- **Fix:** Timeout verkorten naar 0.5s
  ```bash
  sed -i 's/timeout_check.*2\.0/timeout_check = 0.5/' /path/to/muto_driver_fixed.py
  ```

### Robot beweegt niet bij Nav2 commando's
- **Oorzaak 1:** `app_muto.py` bezet serial port
- **Fix:** `pkill -f app_muto.py`
- **Oorzaak 2:** cmd_vel relay niet gestart
- **Fix:** `ros2 run topic_tools relay /cmd_vel_nav /cmd_vel`

---

## 🧠 IMU

### `/imu` Publisher count 0
- **Oorzaak:** `imu_publisher.py` niet gestart
- **Fix:**
  ```bash
  docker exec -d humble_run bash -c 'source /opt/ros/humble/setup.bash && exec python3 /root/imu_publisher.py > /tmp/imu.log 2>&1'
  ```

### ICM20948 WHO_AM_I fout
- **Oorzaak:** Verkeerde I2C bus (bus 1 i.p.v. bus 4)
- **Fix:** `i2cdetect -y 4` (bus 4, niet bus 1)

---

## 💻 Pi CPU Overbelasting

### Rosbridge op >80% CPU
- **Oorzaak:** Abonneert op te veel topics via WebSocket
- **Fix:** `throttle_rate:500` in muto_viz.html, IMU op 20Hz, geen camera topics via rosbridge

### IMU publisher op >60% CPU
- **Oorzaak:** Draait op 100Hz (timer 0.01s)
- **Fix:**
  ```bash
  sed -i 's/create_timer(0.01/create_timer(0.05/' /home/pi/imu_publisher.py
  # Herstart imu_publisher.py
  ```

### Pi load > 3.0
- **Oorzaak:** camera_info_republisher draait dubbel of meerdere zware nodes
- **Fix:** Republisher verwijderen, rgbd_sync direct op camera topics abonneren
- **Acceptabele Pi load:** ~2.5-3.0 met rf2o (~87% CPU) + camera (~53%) + rosbridge (~93% maar throttled)

---

## 🔊 Audio

### Geen geluid / "Channels count non available"
- **Oorzaak 1:** ALSA kaart hardcoded met `hw:X,0` (kaart nummers verschuiven bij reboot)
- **Fix:** Gebruik `null` in `voice_config.yaml`, altijd auto-detectie
- **Oorzaak 2:** `hw:` prefix i.p.v. `plughw:`
- **Fix:** Altijd `plughw:` gebruiken voor automatische formaatconversie

### Camera + audio werken niet tegelijk
- **Oorzaak:** Beide op interne Yahboom USB hub (battery-voltage powerbudget conflict)
- **Fix:** Soundblaster Play! 3 op aparte Pi USB poort (NIET de Yahboom hub)

---

## 🤖 Dify / Netwerk

### Dify 502 Bad Gateway na restart
- **Oorzaak:** nginx start sneller dan API
- **Fix:**
  ```powershell
  # In D:\dify\docker
  docker compose restart nginx
  # Wacht ~10 seconden, refresh http://localhost/apps
  ```

### Dify bereikt Pi niet (SSRF geblokkeerd)
- **Fix:** `SSRF_PROXY_ALLOW_PRIVATE_IPS=192.168.68.88` in `D:\dify\docker\.env`

### llama.cpp twee instanties op zelfde poort
- **Fix:**
  ```powershell
  taskkill /PID [pid] /F  # Voor beide PIDs
  ```

### Dify Studio niet bereikbaar
- **Correct adres:** `http://localhost/apps` (niet `http://192.168.68.77` → local firewall blokkeert)

---

## 🔐 SSH

### SSH wachtwoord gevraagd van Jetson naar Pi
- **Oorzaak:** SSH key niet geconfigureerd voor root op Jetson
- **Fix:**
  ```bash
  sudo ssh-keygen -t ed25519 -f /root/.ssh/id_ed25519 -N ""
  sudo ssh-copy-id pi@192.168.68.88
  ```

---

## 🐳 Docker / Containers

### humble_run start niet of crasht
- **Fix (altijd als stap 0):** `docker restart humble_run`

### "robocopy /COPYALL" permissions fout
- **Oorzaak:** Kopieert restrictieve Windows system32 permissies
- **Symptoom:** Downstream container failures (postgres, redis, nginx)
- **Fix:** `icacls` op de bestemming map om permissies te resetten
- **Regel:** NOOIT `robocopy /COPYALL` gebruiken voor Docker volumes

### muto_yahboom container start niet op port 8080
- **Oorzaak:** Webserver (`http.server 8080`) of andere service bezet de poort
- **Check:** `ss -tlnp | grep 8080`
- **Fix:** `sudo pkill -f "http.server"` en opnieuw starten

---

## 🔭 LiDAR (YDLidar TG30)

### Scan roteert / kaart chaos
- **Oorzaak:** `reversion: true` in ydlidar.yaml OF meerdere instances
- **Fix reversion:** Zet `reversion: false`
- **Fix instances:** `pkill -9 -f ydlidar` dan herstarten

### Lidar type fout
- **Correct:** `lidar_type: 0` (TYPE_TOF)
- **Fout:** `lidar_type: 1` (TYPE_TRIANGLE → verkeerde berekeningen)

### Geen `/scan` topic
- **Fix:**
  ```bash
  source /home/pi/yahboomcar_ros2_ws/software/library_ws_humble/install/setup.bash
  ros2 launch ydlidar_ros2_driver ydlidar_launch.py
  ```
  (Niet de Kilted workspace gebruiken)
