# 🔄 Overdracht — lees dit eerst in een nieuwe sessie

**Laatst bijgewerkt:** 11 augustus 2026, laat op de avond
**Volledige details:** [docs/ROADMAP.md](docs/ROADMAP.md) sectie "🌙 Eindstatus sessie 11 augustus 2026", [problems/PROBLEMS.md](problems/PROBLEMS.md), [slam/SLAM_NAV2.md](slam/SLAM_NAV2.md)

---

## Waar we nu staan (in één alinea)

We hebben vanavond de rf2o-rotatie-overschatting definitief root-caused (gait-lineariseringsmismatch, geen sensorfout), Pad A (externe IMU voor yaw + rf2o alleen x/y) geeft **0,96-1,00× nauwkeurigheid** zodra je ≥24s wacht na een stop (`/pose_settling`-topic bouwt dit al in). Daarna kwam een AMCL-lokalisatieprobleem naar boven: de robot convergeerde confident maar **naar een compleet verkeerde pose**. Root cause gevonden door oudere sessie-transcripten te doorzoeken: een **180° laser-mounting-TF-fout** (Yahboom's officiële URDF heeft de correctie al ingebouwd, maar de YDLidar-driver gebruikte het verkeerde frame_id). Gefixt. Daarnaast bleek de externe IMU **vlak bij het metalen frame** onbetrouwbare metingen te geven (bevestigd via een kalibratietest, opgelost door de IMU te verplaatsen/isoleren). Na beide fixes: positie klopt, maar er resteert een **~95° oriëntatie-afwijking** die handmatig gecorrigeerd is — root cause daarvan nog niet gevonden. Daarna, bij een poging de robot naar een deuropening te draaien, liepen twee dingen mis (zie "Openstaande bugs" hieronder) waardoor de **huidige fysieke oriëntatie van de robot nu onbevestigd is**.

**Robot staat veilig stil.** Software-stack (lidar/rf2o/EKF/Nav2/phoenix_driver) draait nu **niet** — moet elke sessie opnieuw opgestart worden (container wordt regelmatig herstart, alle processen gaan dan verloren).

---

## Direct te doen, in deze volgorde

1. **Software-stack opnieuw opstarten.** Zie `software/pi/scripts/muto_fase1_start.sh` als basis, of volg de stappen die deze sessie steeds herhaald zijn: `app_muto.py` stoppen (blokkeert `/dev/myserial`) → lidar → `scan_timestamped.py` → `robot_state_launch.py` → rf2o → `imu_publisher.py` → UKF (`ekf_params.yaml`, Pad A-config staat er al goed in) → `phoenix_driver.py` → Nav2 (`hexapod_navigation.launch.py map:=/root/maps/lidar_only_map.yaml`).
2. **⚠️ Controleer eerst of de 180°-laser-TF-fix nog actief is.** Dit is een losse `sed`-aanpassing in een container-lokaal bestand (`ydlidar_ros2_driver/params/ydlidar.yaml`, `frame_id: laser` → `frame_id: laser_scan_fix`) — gaat waarschijnlijk verloren bij een container-herstart. Check: `docker exec humble_run grep frame_id /root/yahboomcar_ros2_ws/software/library_ws_humble/install/ydlidar_ros2_driver/share/ydlidar_ros2_driver/params/ydlidar.yaml`. Zo niet, opnieuw toepassen (zie ROADMAP.md voor de volledige uitleg).
3. **Verifieer of de externe IMU nog steeds op de verplaatste/geïsoleerde positie zit** (fysiek, niet software) — dit was een handmatige fysieke wijziging door de gebruiker, geen code-fix.
4. **Een verse, betrouwbare heroriëntatie-check doen** — `mark_amcl_pose.py` gebruiken om de huidige, werkelijke oriëntatie vast te stellen. Vertrouw NIET op de laatst bekende waarden uit deze sessie (die zijn tegenstrijdig, zie hieronder).
5. Pas daarna verder met: linksom-snelheid apart kalibreren, `incremental_rotate.py` repareren, en de eerder geplande Nav2-obstakel-vermijdingstest.

---

## Openstaande bugs (nog niet gefixt)

- **Linksom-rotatiesnelheid nooit gevalideerd met de verplaatste IMU** — alleen rechtsom is gekalibreerd (~0,049 rad/s, zie `software/pi/tools/rotation_calib_test.py`). Een blinde aanname dat links even snel is als rechts veroorzaakte een overshoot (bedoeld 139°, geschat ~200° geworden) — robot direct gestopt, geen schade.
- **`incremental_rotate.py`'s wachttijd-implementatie is kapot** — gebruikt een `spin_once(timeout_sec=1.0)`-lus i.p.v. `time.sleep()`, garandeert dus geen echte 27s wachttijd. Moet gerepareerd worden vóór hergebruik.
- **Resterende ~95° oriëntatie-afwijking na de 180°-TF-fix** — root cause onbekend, mogelijk gerelateerd aan een eerder genoteerd `reversion`-parameterverschil met Yahboom's officiële YDLidar-config. Nu alleen handmatig gecorrigeerd via `/initialpose`, niet structureel opgelost.
- **Twee tegenstrijdige eindmetingen van de laatste sessie:** IMU-cumulatief zei -73,3° rotatie, AMCL zei -102,1° (verschil ~29°) — geen van beide vertrouwd. De werkelijke huidige oriëntatie van de robot is dus onbekend totdat een verse, betrouwbare check gedaan is (zie stap 4 hierboven).

---

## Bewust uitgesteld (lagere prioriteit, met reden)

- **Zijwaartse drift tijdens recht-vooruit-lopen** (2-4× groter dan de 10-augustus-baseline) — bewust naar lagere prioriteit gezet, want Nav2's closed-loop obstakel-vermijding zou dit grotendeels moeten compenseren zodra lokalisatie klopt. **Let op:** een deel van de eerder gemeten "extra drift" is mogelijk zelf een IMU-magnetometer-meetartefact geweest (gemeten vóór de IMU-verplaatsing) — nog niet herzien met de verbeterde IMU.
- **Pad B (zachte gait-variant)** — werkte goed op een draaischijf maar gaf afzet-slip op de echte vloer. On hold, looppunten-inspectie nog nodig.
- **Astra Pro Plus + ICP-pointcloud-odometrie** (voorstel van de gebruiker, 11 aug 2026 laat) — technisch degelijk voorstel (DOF-splitsing vloer/verticale-geometrie, IMU als ICP-initial-guess, kwaliteit-gestuurde covariantie), maar **bewust als stap-2-optie** neergezet: (a) de "RF2O heeft ~2/3 yaw-fout"-aanname waar het voorstel op steunt is door onze eigen schone tests achterhaald (rf2o zelf is 0,97-1,02× nauwkeurig bij gladde beweging, en Pad A haalt nu al 0,96-1,00×), (b) camera-SLAM is in dit project al eerder bewust losgelaten vanwege Pi/Jetson-rekenlast, (c) vanavond al tekenen van resource-druk gezien (DDS-transport-fouten, een onverklaarde container-herstart). Advies: eerst de goedkope, bijna-afgeronde lidar/IMU-route afmaken; dit voorstel als fallback bewaren als oriëntatie dan nog steeds onbetrouwbaar blijkt.

---

## Belangrijke, blijvende lessen uit deze sessie

- **Nooit een lange, blinde rotatieduur commanderen** op basis van een niet-voor-die-richting/dat-moment-gevalideerde snelheid — altijd korte, veilige stappen met een echte tussenmeting. Dit gebeurde twee keer vanavond ondanks eerder geleerde lessen.
- **Wachttijden altijd met `time.sleep()`**, nooit een `spin_once`-lus met een per-iteratie-timeout — die garandeert geen echte verstreken tijd.
- **Minimaal ~24-27 seconden wachten na elke stop** voordat een yaw/pose-meting betrouwbaar is (fysieke naslinger, empirisch bepaald).
- **IMU-plaatsing t.o.v. metalen delen is een reële foutbron**, niet alleen een theoretisch punt — vlak bij metaal gaf aantoonbaar inconsistente, zelfs tekenwisselende metingen.
- Bij een hardnekkig, herkenbaar probleem: **doorzoek oudere sessie-transcripten** (`~/.claude/projects/-home-pi/*.jsonl`, `mcp__ccd_session_mgmt__search_session_transcripts` bleek de index niet goed te dekken, dus desnoods direct grepen in de `.jsonl`-bestanden) — dit project heeft een lange geschiedenis en problemen zijn vaker al eens opgelost.
