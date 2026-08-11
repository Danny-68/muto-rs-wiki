# 🗺️ Roadmap — Autonome navigatie, Dify-besturing & Jetson-AI

Overkoepelend statusoverzicht van de grote visie: een volledig autonome, natuurlijke-taal-aangestuurde hexapod met SLAM/Nav2-navigatie, Dify/LLM-besturing, en de Jetson als GPU-co-processor. Opgesteld 9 augustus 2026 door het hele project (lokale code + `muto-llm-2.0`-broncode, niet alleen de documentatie) door te lezen.

---

## De visie

```
Gebruiker (spraak/tekst)
        │
        ▼
   Dify-workflow (LLM-orkestratie)
        │
        ▼
   Robot voert uit: eenvoudige bewegingen, sensor-queries, ÉN
   (in principe) autonome navigatie naar benoemde plekken
        │
        ▼
   Jetson versnelt zware taken (SLAM/vision) zodat de Pi
   vrij blijft voor latency-kritische besturing
```

---

## Taakverdeling: gepland vs. werkelijk

| Machine | Geplande rol | Werkelijke status |
|---|---|---|
| **Raspberry Pi 5** (192.168.68.88) | Sensoren, actuatie, latency-kritische taken | ✅ Grotendeels werkend, actief onderhouden (10+ bugs gevonden/gefixt sinds 30 juli) |
| **Jetson Orin Nano** (192.168.68.86) | RTAB-Map GPU, Nav2, **YOLO, LLM** (compute-zwaar) — besluit 12 juli | ⏸️ Alleen RTAB-Map/Nav2-rol ooit gehaald (13-14 juli), sindsdien **on hold** wegens Pi/Jetson/WiFi-belasting. YOLO en LLM-op-Jetson: **nooit geïmplementeerd** — al het LLM-werk ging naar de Windows-PC |
| **Windows PC** (192.168.68.77) | Dify + LLM-inference | ✅ Werkend: Dify + llama.cpp (Qwen2.5-14B, RTX 5080, ~97 tok/s) |

**Conclusie: Jetson is een slapende asset.** Aangeschaft en opgezet voor drie rollen; nul daarvan actief op dit moment.

---

## Status per laag

### 1. Sensing & actuatie (Pi) — ✅ werkend
LiDAR (YDLidar TG30), IMU (ICM20948), Orbbec Astra-camera, STM32-serieel-driver. Zie [PROBLEMS.md](../problems/PROBLEMS.md) voor de uitgebreide bug-geschiedenis.

### 2. Autonome navigatie: lidar-only AMCL + Nav2 (Pi) — 🟡 werkend maar fragiel
Robot is succesvol door deuropeningen genavigeerd (31 juli, 7 augustus). Bekende, deels opgeloste beperkingen:
- Forward-drift-correctie geïmplementeerd maar nog niet overtuigend gevalideerd (zie PROBLEMS.md — validatie op 0.9m bleek mogelijk op een uitschieter te steunen, nog te herhalen op een "gunstige" afstand ~1.5m)
- Discrete gait-cyclus (~0.45s/commando) beperkt hoe nauwkeurig Nav2's controller kan bijsturen
- IMU-magnetometerfusie kapot (ongevalideerde as-remap, geen hard/soft-iron-kalibratie)
- Links/rechts-rotatie-asymmetrie en achteruit/vooruit-drift-asymmetrie onverklaard (firmware-broncode niet beschikbaar)

### 3. Dify/LLM-besturing (Stack B) — ✅ werkend voor eenvoudige commando's
Tweetraps-LLM-workflow (Decision LLM → parse → Execution LLM → HTTP POST naar Pi `:8080/execute_commands`). Werkt voor: `forward()`, `backward()`, `rotate()`, `have_a_look()`, LiDAR-queries, spraak. Zie [DIFY.md](../dify/DIFY.md).

### 4. 🔑 Kernvondst: de brug tussen Dify en Nav2 bestaat al in code, maar staat operationeel los

In `muto_hexapod_lib/Largemodel/navigation_manager.py` (onderdeel van `muto-llm-2.0`, dus van Stack B) zit een **volledig uitgewerkte** `NavigationManager`-klasse:

| Functie | Wat hij doet |
|---|---|
| `navigate_to_pose(x, y, yaw)` | Stuurt een echt Nav2 `NavigateToPose`-actiedoel via een eigen ROS2-node/ActionClient |
| `navigate_to_saved_position(naam)` | Zoekt een opgeslagen waypoint op (via `position_manager.py`, quaternion→yaw-conversie) en navigeert ernaartoe |
| `set_initial_pose(x, y, yaw)` | Publiceert naar `/initialpose` (AMCL) |

Deze zijn al in `MutoLargemodelInterface.py` doorverbonden (`self.navigation_manager = NavigationManager(self)`), en `command_executor.py`'s **generieke naam-gebaseerde command-dispatch** (parseert `functienaam(args)`-strings uit een LLM-plan en roept ze via reflectie aan) zou ze dus zonder verdere aanpassing al kunnen aanroepen. Een Dify-plan met `navigate_to_saved_position(position_name='keuken')` wordt vandaag al **geparsed en doorverbonden**.

**Maar:** `NavigationManager` is alleen een *client* — hij verwacht dat Nav2 (met een `navigate_to_pose`-actionserver en AMCL die naar `/initialpose` luistert) *al draait*. `switch_to_yahboom.sh` (het opstartscript voor Stack B, waar Dify tegenaan praat) start alleen:
1. `app_muto.py` stoppen
2. `robot_bridge.py` stoppen
3. Oude `muto_yahboom`-container opruimen
4. `humble_run` starten
5. **Alleen de LiDAR** (`ydlidar_ros2_driver`)
6. Dify-bereikbaarheid checken
7. Stack B-container starten

Geen `robot_state_publisher`, geen AMCL, geen Nav2. Dus: **als je vandaag via Dify "navigeer naar de keuken" zou zeggen, zou `navigate_to_pose()` gewoon timeouten** — er is geen actionserver om mee te praten.

**Samengevat: de software-integratie bestaat, de operationele koppeling (beide stacks tegelijk laten draaien) niet.**

---

## Roadmap: concrete vervolgstappen

| # | Stap | Waarom | Inschatting |
|---|---|---|---|
| 1 | **`switch_to_yahboom.sh` uitbreiden** zodat het naast de lidar ook `robot_state_publisher` (officieel URDF), AMCL en Nav2 (de huidige, gefixte lidar-only stack uit `muto_fase1_start.sh`) meestart | Dit is de kern-ontbrekende schakel tussen Dify en autonome navigatie | Middel — twee losse, bewust gescheiden opstartprocedures moeten samengevoegd worden zonder de bestaande seriële-poort-exclusiviteit (`/dev/myserial`) te breken |
| 2 | `navigate_to_pose()` / `navigate_to_saved_position()` **live testen** | Nooit gedaan — onbekend of de actionserver-naam/interfaces nog matchen met de huidige `hexapod_nav`-package (die is sinds juli meermaals gewijzigd) | Klein-middel, ná stap 1 |
| 3 | `position_manager.py` uitzoeken: hoe/waar worden waypoints opgeslagen, is er al een manier om ze vanuit Dify/spraak te definiëren ("onthoud deze plek als keuken")? | Nodig om `navigate_to_saved_position()` bruikbaar te maken in de praktijk | Klein, onderzoek eerst |
| 4 | Resterende Nav2-betrouwbaarheidspunten afronden: forward-drift-validatie op gunstige afstand, IMU-fusie, rotatie-asymmetrie | Beïnvloedt hoe betrouwbaar autonome navigatie sowieso is, los van de Dify-koppeling | Doorlopend, deels al bezig |
| 5 | **Besluit over Jetson:** (a) lichtere/lokale RTAB-Map-variant zonder Jetson-split vinden, (b) alsnog de oorspronkelijke YOLO/vision-rol implementeren om de Pi te ontlasten, of (c) bewust afschrijven en architectuur vereenvoudigen tot Pi+PC | Jetson kost stroom/ruimte zonder nu iets bij te dragen | Strategische keuze, geen technisch obstakel |
| 6 | `have_a_look()`-visie-workflow afronden | Al genoteerd als open punt sinds de juni-inventarisatie, nooit voltooid | Klein-middel |
| 7 | ✅ **grotendeels afgerond (11 aug 2026): `phoenix_driver.py` als Nav2-bewegingsbackend** — `muto_fase1_start.sh` uitgebreid met `DRIVER=phoenix_driver`-keuze, lifecycle-checks bevestigd gezond, een schokkerige-beweging-bug gevonden+gefixt (stop-debounce), en de eerste live `NavigateToPose`-test gaf **SUCCEEDED** met vloeiende beweging. Zie GAIT.md "Nav2-live-integratietest". | Yaw-drift bij phoenix_gait tripod is een stuk kleiner dan de STM32-firmware-gait — relevant voor Nav2's dead-reckoning tussen LiDAR-scans | Bewegingskwaliteit is bevestigd goed; **resterend knelpunt is AMCL-lokalisatienauwkeurigheid** (zie punt 8), niet de driver zelf |
| 8 | **AMCL-lokalisatienauwkeurigheid verbeteren** — rotatie-burst-procedure convergeert niet altijd betrouwbaar (covariantie daalt, maar objectieve raycast-verificatie blijft vaak op 1-2 van de 4 richtingen afwijken). Handmatige kaartafbeelding-correctie werkt beter voor positie, maar oriëntatie bleek bij een navigatietest alsnog onvoldoende nauwkeurig (deuropening rechts, doel ging recht vooruit). Twee nieuwe, herbruikbare verificatietools gebouwd: `mark_amcl_pose.py` (visuele check) en `verify_amcl_pose.py` (objectieve laser-vs-raycast-check). **Root cause nu gevonden (11 aug 2026):** rf2o overschat rotatie 2,4-3,4× tijdens tripod-gait — drie hypotheses (sway, ramp-timing, pure-vibratie) verworpen via isolatiemetingen, code-analyse sluit een offset-/QoS-bug in rf2o uit, literatuur bevestigt dat rf2o's Range-Flow-linearisatie een erkende, algemene mismatch heeft met schoksgewijze gait-beweging. Zie PROBLEMS.md "rf2o Odometrie" voor het volledige traject. | Zonder betrouwbare lokalisatie is elk navigatiedoel gebaseerd op een gok — dit is nu de kern-blokkade voor bruikbare autonome navigatie | Middel-groot; root cause is nu bekend (fundamenteel, geen losse bug), vervolg is een architectuurkeuze i.p.v. verder zoeken |

### Testdoelen volgende sessie (rf2o/AMCL-vervolg, per 11 aug 2026)

1. **Externe IMU terugzetten als primaire yaw-bron in de EKF** (i.p.v. de seriële-poort-gedeelde, 2Hz-beperkte onboard-STM32-yaw) — `ekf_params.yaml`'s `imu0_config` yaw/vyaw weer aanzetten, `imu1` (STM32) weer uitzetten of als secundaire bron laten staan, rf2o (`odom0_config`) strikt beperkt houden tot x/y. Meten: dezelfde rotatieburst-vs-IMU-ratio-test herhalen (`isolate_odomfused_vs_imu.py`) — doel is een ratio dicht bij 1,0× op de yaw-as van `/odom_fused`.
2. **AMCL-rotatie-burst-convergentie herhalen** met de aangepaste EKF-config — objectieve raycast-verificatie (`verify_amcl_pose.py`) op alle 4 richtingen (0/90/180/270°), met bijzondere aandacht voor de nog onbevestigde "90°-blinde-hoek"-observatie.
3. **Pas ná bevestigde, stabiele lokalisatie:** een tweede live `NavigateToPose`-test naar een zichtbaar doel (bijv. de eerder gebruikte deuropening), ditmaal met verificatie vooraf dat AMCL's geschatte oriëntatie klopt (via `mark_amcl_pose.py`) — succescriterium is dat de robot de juiste kant op beweegt, niet alleen dat de actie SUCCEEDED teruggeeft.
4. **Optioneel, als (1) onvoldoende verbetert:** overweeg de EKF-frequentie/`sensor_timeout` te verlagen zodat de yaw-fusie sneller reageert op de externe IMU tijdens een gait-cyclus, of onderzoek of de externe IMU op een hogere rate dan zijn huidige publicatiefrequentie kan publiceren.

---

## Wat NIET meer op deze lijst staat (bewust)

- ~~`app_muto.py`'s autostart permanent uitschakelen~~ — bewust behouden, zie [README.md](../README.md) regel 7 en [TIMELINE.md](TIMELINE.md). Elke stack lost dit zelf op bij eigen opstart.
