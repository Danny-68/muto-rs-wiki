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

### RTAB-Map + Jetson roadmap: on hold wegens Pi/Jetson/WiFi-belasting
- **Symptoom:** hoge Pi-load (`uptime`), undervoltage/thermisch-throttle-signalen (`vcgencmd get_throttled`) tijdens `/rgbd_image`-streaming naar de Jetson.
- **Geprobeerd:** `/rgbd_image` throttlen naar 3Hz via `topic_tools throttle` — verminderde de belasting niet genoeg om het de moeite waard te maken.
- **Beslissing:** overgestapt op `switch_to_yahboom.sh` → lidar-only Nav2/AMCL-aanpak op de Pi alleen, geen camera/Jetson meer nodig (zie [SLAM_NAV2.md](../slam/SLAM_NAV2.md) voor de huidige aanpak).
- **Heropname-voorwaarde:** alleen heroverwegen als er een lichtere/lokale RTAB-Map-variant mogelijk blijkt **zonder** de Jetson-split (bijv. volledig lokaal op de Pi, of met een sterk verlaagde framerate/resolutie) — anders herhaal je dezelfde belastingsmeting voor niets.

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
- **Oorzaak:** meerdere ydlidar-instances tegelijk actief
- **Fix instances:** `pkill -9 -f ydlidar` dan herstarten
- **Oorzaak (reversion):** zie onderstaande **⚠️ UPDATE 31 juli** — `reversion` alléén is geen vaste waarde, hangt af van welke laser-TF-aanpak je gebruikt.

> **⚠️ UPDATE 31 juli 2026 — reversion hangt samen met de TF-aanpak, niet los aanpasbaar:**
> Deze entry zei eerder onvoorwaardelijk "zet `reversion: false`". Dat klopte alleen zolang er een **handmatige** `static_transform_publisher` met een 180°-yaw-correctie (`--qz 1 --qw 0`) werd gebruikt voor `base_link→laser`.
> Sinds de overstap naar het **officiële URDF + `robot_state_publisher`** (i.p.v. handmatige static transforms, zie TIMELINE 31 juli) hoort daar **`reversion: true`** bij — Yahboom's eigen `laser_bringup_launch.py` gebruikt voor het 4ROS/YDLidar-pad exact deze combinatie (`reversion: True, inverted: True`), en dat is live geverifieerd correct (scan op 0°/90°/180°/270° klopte met de fysieke situatie).
> **Regel:** `reversion: false` + handmatige 180°-TF **OF** `reversion: true` + officieel URDF. **Nooit** de twee door elkaar combineren (dan corrigeer je 180° dubbel, of helemaal niet). Zie [SLAM_NAV2.md](../slam/SLAM_NAV2.md) voor de huidige (URDF-gebaseerde) aanpak.

### 90°-brede blinde sector, geen enkele meting in dat bereik
- **Oorzaak:** fysiek losse lidar-stekker — **geen software-/TF-/reversion-bug**, ook al toont het driver-log geen disconnect en lijken de timestamps vers.
- **Herkenning:** een grote (tientallen graden), aaneengesloten lege sector die een bekend nabij object volledig mist.
- **Fix:** stekker fysiek controleren/vastzetten, dan robot **en** container volledig herstarten (niet alleen de ROS-processen).
- **Les:** bij zo'n symptoom eerst de kabel checken, pas daarna in software zoeken.

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

---

## 🧭 Nav2 / Driver (lidar-only AMCL-aanpak, sinds 30 juli 2026)

### Robot zoekt de KLEINSTE i.p.v. grootste vrije ruimte
- **Oorzaak:** eigen `static_tf_pub_laser_ours` (`base_link→laser`) gebruikte identiteits-rotatie, maar de LiDAR zit fysiek 180° gedraaid — elk obstakel werd 180° verkeerd in de costmap geplaatst. Verklaart ook waarom AMCL nooit goed convergeerde.
- **Fix:** static transform met `--qz 1 --qw 0` (180° yaw) i.p.v. `--qz 0 --qw 1` (identiteit) — of beter: overstappen op het officiële URDF (zie hieronder).

### Nav2 logt "inflation radius smaller than inscribed radius" (ERROR)
- **Oorzaak:** `inflation_radius: 0.2` in `hexapod_nav_params_custom.yaml`, kleiner dan de inscribed radius (0.255) van het footprint.
- **Fix:** `inflation_radius: 0.35` in zowel `global_costmap` als `local_costmap`.

### Bocht met kleine rotatie gooit de voorwaartse snelheid volledig weg
- **Oorzaak (grote bug):** `muto_driver_fixed.py` stuurde x/y/z nooit gecombineerd — prioriteitslogica (`if z: move(0,0,z) elif x: move(x,0,0) ...`) betekende dat élke rotatie de voorwaartse snelheid kapte tot een pure draai. Ondermijnt precies waar `RegulatedPurePursuitController` op leunt (vloeiend vooruit+bijsturen combineren).
- **Fix:** driver herschreven om **altijd** `move(lvl_x, lvl_y, lvl_z)` met alle drie de componenten tegelijk aan te roepen, exact zoals Yahboom's officiële `yahboomcar_bringup`-driver.

### `/cmd_vel`-snelheid wordt genegeerd (elke beweging even hard)
- **Oorzaak:** oudere driverversie verstuurde elk commando met hardcoded `data=15`, ongeacht de daadwerkelijke `cmd_vel`-grootte.
- **Fix:** driver gebruikt nu de officiële `Muto`-klasse (`muto_hexapod_lib.core.MutoLibCore`) en schaalt `cmd_vel` naar levels (×100, geklemd [-30,30]).

### Opeenvolgende `/cmd_vel`-commando's worden pas na ~0.45s verwerkt (niet 0.1s)
- **Oorzaak:** de STM32-gait-cyclus is een discrete, niet-triviale-tijd kostende stap (`hexapod.move()` → `process_movement(13)`), geen continu regelbare snelheid zoals Nav2's DWB-controller aanneemt (5Hz control loop).
- **Status:** nog niet definitief opgelost — verklaart mogelijk (een deel van) waarom zelfs een correcte controller een bewegend lookahead-punt niet nauwkeurig kan volgen. Zie `RegulatedPurePursuitController` in [SLAM_NAV2.md](../slam/SLAM_NAV2.md) voor de huidige mitigatie.

### `odom_fused` wijkt tot een kwart slag af na snelle rotatie
- **Oorzaak:** sporadisch trackingverlies van `rf2o`'s laser-scan-matching tijdens snel draaien (verschil varieerde 15°→95° tussen bijna-identieke tests — geen consistente schaalfout, dus incidenteel).
- **Fix:** rotatiesnelheid verlagen (level 20 i.p.v. 30) verbeterde de afwijking van -49.6° naar -11.3° — gebruik level ≤20 voor rotatie in Nav2 (`rotate_to_heading_angular_vel`).

---

## 🎯 Rotatie & precisiebeweging (`robot_bridge.py`)

### `rotate_to_angle` overschiet fors bij kleine hoeken
- **Oorzaak:** oude formule `stop_margin = min(ROTATE_STOP_MARGIN, target * 0.5)` nam aan dat de coast (doordraaien na stopcommando) evenredig schaalt met de doelhoek. Metingen toonden het tegendeel: coast is **~11-16° vrijwel onafhankelijk van de doelhoek**. Bij kleine doelen gaf de oude formule een veel te kleine marge → tot 3× overschot.
- **Fix:** vaste `ROTATE_STOP_MARGIN = 14.0` (geen schaling meer). Gevalideerd n=15 over 8-35°: gemiddelde afwijking van 10-17° naar **-0.8°** (std.dev ~3.1°).

### `rotate_to_angle`-docstring beschreef links/rechts verkeerd om
- **Oorzaak:** documentatiefout — de code zelf (`turn_addr = 0x17 if angle_deg > 0 else 0x16`) deed altijd al **positief=rechts, negatief=links**; de docstring zei het omgekeerde.
- **Fix:** docstring gecorrigeerd (9 augustus 2026), geen gedragswijziging in de code.

### Robot drift fors naar één kant tijdens recht vooruit lopen (kan tegen obstakels aanlopen)
- **Metingen (n=5, 0.3m per stap):** gemiddeld **-5.2°/0.3m**, vrij consistent (std.dev ~0.86°) — systematische oorzaak (gait-/servo-asymmetrie), geen incidenteel trackingverlies. Ook aanwezig (in mindere mate, ~20°/3-4m) bij gamepad-besturing — een mens corrigeert dit onbewust continu, een los `forward()`-commando niet.
- **Mitigatie (handmatig, sinds 7 augustus):** in batches van 0.3m lopen, na elke batch met `rotate_to_angle` terugcorrigeren naar de referentie-yaw.
- **Fix (geautomatiseerd, 9 augustus 2026):** `POST /robot/forward` met `{"correct_drift": true, "distance_m": ...}` doet dit nu automatisch — zie `_forward_with_drift_correction()` in `software/pi/ros2/robot_bridge.py`. Standaardgedrag van `/robot/forward` blijft ongewijzigd (fire-and-forget) tenzij dit veld expliciet wordt meegegeven.
- **⚠️ Live gevonden tekenbug (eerste versie, 9 aug 2026):** de correctie riep `rotate_to_angle(-drift)` aan, uitgaand van de aanname dat een positieve hoek ("rechts") de gemeten yaw zou VERHOGEN. Live testen toonde het omgekeerde: "rechts" VERLAAGT de gemeten yaw. Resultaat: elke correctie verergerde de afwijking in plaats van 'm te herstellen (0.6m ongecorrigeerd -14.2°, met de kapotte correctie -62.2°). **Fix:** `rotate_to_angle(drift)` (zonder minteken).
- **⚠️ Tweede probleem, ook live gevonden:** na de tekenfix bleef de correctie nog steeds matig (0.6m: -12.2° ongecorrigeerd → +7.1° gecorrigeerd, wel beter maar niet overtuigend) — een enkele 0.3m-batch-drift (~5-6°) valt namelijk middenin de onbetrouwbare sub-14°-zone van `rotate_to_angle` (zie hieronder), dus corrigeren na élke batch maakte het resultaat onvoorspelbaarder i.p.v. beter. **Fix:** drempel opgehoogd naar `FORWARD_DRIFT_CORRECT_THRESHOLD = 15.0` graden (pas corrigeren als de opgebouwde afwijking ruim boven de marge zit, 2-3 batches — exact de handmatige aanpak uit sectie 18.5).
- **Eerste validatie (mogelijk onbetrouwbaar):** 0.9m ongecorrigeerd -17.4°, met de gefixte correctie (drempel 15°) -0.7° netto. **⚠️ Kanttekening (later dezelfde dag):** deze meting bevatte één batch met een verdachte, geïsoleerde +20.3°-sprong (heel anders dan de rest van de metingen die dag) — mogelijk veroorzaakt door externe tussenkomst tijdens de test, niet door de robot zelf. Zie hieronder voor schonere vervolgmetingen.
- **Schonere hertest (n=4, 0.9m, geen tussenkomst binnen een run):** natuurlijke drift bleek consistent **-8° tot -16°** — geen enkele uitschieter zoals boven. **Belangrijk:** bij deze schone metingen kwam de opgebouwde afwijking bijna nooit boven de 15°-drempel uit (meestal 13-16°, net eronder of erop), dus de correctie is in de meeste van deze runs helemaal NIET afgegaan. Dit betekent dat de eerdere "-0.7° netto"-validatie hierboven waarschijnlijk net op die ene verdachte uitschieter dreef, en (nog) geen betrouwbare bevestiging is dat de correctie in normale bedrijfsomstandigheden goed werkt.
- **Testmethodologie-les:** losse herhalingen na elkaar zonder tussentijdse heading-reset laten de robot in een steeds bredere boog wegdraaien (over 4 reps liep de yaw cumulatief ~36° op) — dit vereist veel meer (zijwaartse) ruimte dan verwacht. Oplossing: tussen elke herhaling terug naar de oorspronkelijke referentie-heading corrigeren, én telkens terugkeren naar het startpunt (anders loopt de robot geleidelijk una gehele testruimte uit).
- **Nog openstaand:** een "gunstige" testafstand bepalen waar de natuurlijke drift betrouwbaar (met marge) boven de 15°-drempel uitkomt — op basis van de gemeten ~-15°/meter zou dat rond de **1.5m** moeten liggen (nog niet getest).
- **Zijdelingse ontdekking: achteruit lopen drift veel minder én in tegengestelde richting.** Schone test (n=2, 0.9m puur achteruit): **+4.7° en +2.8°** (gem. +3.75°) — tegenover -12° tot -16° voorwaarts over dezelfde afstand. Niet zomaar "kleiner", ook nog eens **omgekeerd teken** — wijst erop dat de achterwaartse gait-cyclus in de STM32-firmware geen simpele tijdsomkering van de voorwaartse is, maar een andere balans tussen de poten heeft. Rootcause (welke poot/servo) niet te achterhalen zonder firmwarebroncode. Praktisch bruikbaar: voor precieze manoeuvres is achteruit rijden inherent stabieler dan vooruit.

### `rotate_to_angle` bij hoeken <14° draait altijd ~5-6°, ongeacht de gevraagde hoek
- **Gemeten (9 aug 2026, n=8, hoeken 4-13° beide richtingen):** turned_deg lag steeds tussen 4.4° en 5.9°, volledig onafhankelijk van of er 4° of 13° gevraagd werd.
- **Oorzaak:** onder de marge (14°) is `target - stop_margin` al negatief vóór de robot ook maar begint te bewegen, dus de polling-lus breekt bij de allereerste check — er is geen aanlooptijd, en het resultaat is een vaste, ongecontroleerde minimum-puls van ~5-6°.
- **Praktisch gevolg:** verwacht overshoot bij doelen <6°, en fors tekortschieten bij doelen 6-14°. De `below_resolution`-melding in `robot_bridge.py` is bijgewerkt om dit expliciet te benoemen.
- **Nog niet gefixt:** een aparte aanpak voor dit bereik (bijv. een minimale looptijd forceren vóór de stopconditie geëvalueerd wordt) is niet geïmplementeerd — alleen gedocumenteerd.

### `ROTATE_STEP=15` i.p.v. 10: veel grotere overshoot, geen tijdwinst
- **Vraag (sectie 13h):** is `ROTATE_STEP=10` onnodig traag?
- **Test (9 aug 2026, n=8 op 25°, beide richtingen):** step=15 gaf gemiddeld 3-4× grotere overshoot (rechts +21.2° vs +4.8°, links +14.8° vs -4.1°) — `ROTATE_STOP_MARGIN=14.0` is gekalibreerd vóór step=10 en schaalt niet mee naar grotere stappen.
- **Tijd:** vrijwel gelijk (7.5s vs 7.7s per rotatie) — de stapgrootte is niet de beperkende factor voor snelheid.
- **Conclusie:** `ROTATE_STEP=10` blijft de juiste keuze; step=15 zou een eigen herkalibratie van de marge nodig hebben voor exact hetzelfde resultaat qua tijd — geen reden om te wijzigen.

### Links/rechts-asymmetrie op 25°: rechts niet per se bevooroordeeld, wel veel onvoorspelbaarder
- **Gemeten (9 aug 2026, n=6 per richting, op 25°):** rechts gem. +2.1° afwijking maar met std.dev **4.6°** (spreiding -3.4° tot +7.5°); links gem. -3.85° met std.dev **1.4°** (veel consistenter, -1.4° tot -5.6°).
- **Interpretatie:** dit wijkt af van een eerdere, kleinere meting met gemengde hoeken die een lichte bias de andere kant op suggereerde — het patroon lijkt dus geen vaste, corrigeerbare links/rechts-bias, maar eerder **inherente mechanische speling die bij rechtsom draaien groter/onvoorspelbaarder is**.
- **Rootcause-status:** dieper uitgezocht in de STM32-communicatie (sectie 18.3 van de debug-briefing) leverde geen mechanische verklaring op — de firmware-broncode zelf is niet lokaal beschikbaar, dus de exacte oorzaak (bijv. een specifieke poot/servo) blijft onbevestigd.

### Tijd-gebaseerde `/cmd_vel`-bursts geven onvoorspelbare afstand
- **Oorzaak:** aangenomen snelheid (`level × 0.01 m/s`) is nooit gevalideerd en klopt niet — niveau 15 is in werkelijkheid maar 0.059 m/s, ruim 2,5× langzamer dan aangenomen.
- **Fix:** gebruik altijd de gekalibreerde `robot_bridge.py`-commando's (`distance_m`, `angle_deg`) of de onderliggende `forward()`/`turnleft()`/etc. — nooit een tijdsduur combineren met een aangenomen snelheid.

---

## 📦 Package-installatie verwarring

### Code lezen op de Pi-host geeft een ander beeld dan wat er daadwerkelijk draait
- **Voorbeeld:** `/home/pi/muto-llm-2.0/.../MutoLibCore.py` bevat een gepatchte `move()` met hardcoded `level=15` (uit een eerdere, deels mislukte patch-poging via `patch_mutolib.py`/`patch_mutolib2.py`, gericht op een niet-bestaand containerpad `/root/muto-llm-2.0/...`). De daadwerkelijk geïmporteerde module in `humble_run` staat op `/usr/local/lib/python3.10/dist-packages/muto_hexapod_lib/` (een fysieke kopie die de kapotte editable-install-verwijzing naar `/root/muto-llm/...` overschaduwt) en bevat de **originele, wél-werkende** `move()`.
- **Les:** bij twijfel over welke code daadwerkelijk actief is, **altijd verifiëren in het draaiende proces zelf** (bijv. `docker exec humble_run python3 -c "import inspect; from muto_hexapod_lib.core.MutoLibCore import Muto; print(inspect.getsource(Muto.move))"`) — nooit aannemen dat een bestand op de Pi-host of in deze wiki de live versie is.
- **Nog niet opgeruimd:** er bestaan nu minstens 3 kopieën van `MutoLibCore.py` (host-clone, wiki-mirror, live dist-packages) die uit elkaar zijn gelopen. Opschonen is een openstaand punt (zie TIMELINE "Open punten").


## 🦾 Gait / phoenix_gait.py

### Robot beweegt niet vooruit tijdens tripod-gait (poten bewegen wel)
- **Oorzaak:** `_foot_delta()` roteerde de translatierichting (`tx`, `tz`) met de mount-hoek van elke individuele poot (`MOUNT_RAD[leg]`) i.p.v. een gezamenlijke wereldrichting te gebruiken. Elke poot duwde daardoor radiaal t.o.v. zijn eigen montagehoek; de netto krachten heffen elkaar op en het lichaam verplaatst niet, ook al bewegen de poten zichtbaar (lift, heen-en-weer).
- - **Fix:** translatie loskoppelen van de mount-hoek, vaste wereldrichting voor alle poten (+x=rechts, +y=voorwaarts):
  -   ```python
        def _foot_delta(self, leg, gait, tx, tz, rot):
            nx, ny, _ = NEUTRAL_POS[leg]
            dx = gait.step_length * tz
            dy = gait.step_length * tx
            rot_scale = gait.step_length * 0.6
            rx = -ny * rot * rot_scale / max(math.hypot(nx, ny), 1)
            ry =  nx * rot * rot_scale / max(math.hypot(nx, ny), 1)
            return (dx + rx, dy + ry)
        ```
        Rotatie-component (`rx, ry`) was al correct en hoeft niet aangepast — die gebruikt bewust de pootpositie voor tangentiële beweging.
      - **Bevestigd op hardware:** 10 augustus 2026, tripod-gait + sway. Zie GAIT.md voor volledige context en testresultaten per gaittype.
   
      - ### `/home/pi/phoenix_gait.py` teruggevallen op oudere versie (regressie)
      - - **Symptoom:** ontbrekende functionaliteit die eerder al werkend was: continu fasemodel (50Hz), sinusoidale easing op horizontale beweging, centipede-gait, biologische verbeteringen (body dip, snelheidsafhankelijke lift, accel/decel), servo hardware-interpolatie (exec-time register 0x2C).
        - - **Oorzaak:** niet met zekerheid vastgesteld — vermoedelijk verloren tijdens een eerdere consolidatiepoging (tripod + centipede samenvoegen in één bestand).
          - - **Fix:** reconstructie op basis van projectgeschiedenis (10 augustus 2026). **Let op:** centipede leg-offsets (`[4/6, 2/6, 0/6, 1/6, 5/6, 3/6]`) zijn na deze reconstructie nog niet opnieuw op hardware bevestigd.
            - - **Les:** bij twijfel over de actuele staat van een script, eerst het bestand volledig inlezen en vergelijken met eerdere sessies voordat je een losse bug fixt — een geïsoleerde patch op een geregresseerd bestand lost het symptoom niet op.
              - 
