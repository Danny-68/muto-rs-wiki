# 🗺️ Roadmap — Autonome navigatie, Dify-besturing & Jetson-AI

Overkoepelend statusoverzicht van de grote visie: een volledig autonome, natuurlijke-taal-aangestuurde hexapod met SLAM/Nav2-navigatie, Dify/LLM-besturing, en de Jetson als GPU-co-processor. Opgesteld 9 augustus 2026 door het hele project (lokale code + `muto-llm-2.0`-broncode, niet alleen de documentatie) door te lezen.

---

## 🎯 Puntenlijst voor de volgende sessie (bijgewerkt 11 augustus 2026, avond)

Deze sessie liep aan het eind te veel tests en aannames door elkaar (rf2o-onderzoek, Pad A/B/C, stopsequentie-experimenten, Nav2-poging, open-loop-vooruit-tests) — dit is de ontwarde, één-voor-één-lijst om vanaf te werken. **Niet meerdere punten tegelijk aanpakken.**

### ✅ Definitief opgelost/bevestigd (niet opnieuw onderzoeken)
1. **rf2o's rotatie-overschatting (2,4-3,4× tijdens gait) — root cause gevonden en empirisch bevestigd.** rf2o zelf is accuraat (0,97-1,02× op een schone draaischijf-test); de oscillerende, niet-gladde gait-beweging schendt rf2o's lineaire "gladde-verplaatsing"-aanname. Geen codefout, geen vaste schaalfout.
2. **Pad A (externe IMU als yaw-bron, rf2o alleen x/y) werkt, en de "resterende 18%" was een meettiming-artefact**, geen echte fout. Na een stop naslingert het lichaam fysiek ~15-25s (dempende oscillatie); bij ≥24s wachten convergeert de ratio naar 0,96-1,00×.
3. **`/pose_settling`-topic geïmplementeerd en getest werkend** in `phoenix_driver.py` — `true` gedurende 24s na elke stop, daarna `false`. Bouwsteen, nog niet geconsumeerd door Nav2/AMCL-kant.
4. **Twee stopsequentie-experimenten (sway-uitfasering, snellere neutraal-overgang) gaven geen effect** op de naslinger-duur — niet meer proberen, `phoenix_driver.py` staat terug op origineel (geverifieerd via diff).
5. **Pad C (UKF i.p.v. EKF): geen nauwkeurigheidswinst, wel betere herhaalbaarheid** (0,85/0,85× vs. EKF's 0,74/0,84×). Geen dringende reden om te wisselen.

### 🔴 Nieuw, nog open, hoogste prioriteit — één voor één aanpakken

**Herprioritering (11 aug 2026, avond):** de rauwe gait-drift is bewust naar lagere prioriteit verplaatst. Nav2 werkt closed-loop: zolang de lokalisatie (positie + oriëntatie) klopt en de costmap obstakels via de lidar ziet, corrigeert de controller continu de koers en kan hij om een obstakel heen plannen — ongeacht hoeveel de kale gait zelf drift. De botsing van vandaag gebeurde tijdens een bewust **open-loop** test (zonder Nav2, om de AMCL-complexiteit te omzeilen) — dat is precies het scenario waarin drift gevaarlijk is, en precies het scenario dat Nav2's obstakel-vermijding zou moeten voorkomen. Lokalisatie + obstakel-vermijding hebben dus meer directe waarde dan de drift zelf oplossen.

1. **Nav2/AMCL-initial-pose-workflow moet zorgvuldiger** dan de snelle gok van vandaag ((0,0,0°) bleek in "lethal space" te liggen — costmap dacht dat het startpunt zelf een obstakel was, vandaar de ABORTED-navigatiepoging). Dit was geen regressie van de odometrie-fixes, puur een slechte gok. Gebruik weer de gemarkeerde-kaart-feedback-loop (`mark_amcl_pose.py`) totdat de positie herhaaldelijk bevestigd is, vóór een nieuwe `NavigateToPose`-poging.
2. **`/pose_settling` daadwerkelijk consumeren** aan Nav2/AMCL-kant (bijv. `guarded_navigate_test.py` verder afmaken — bestaat al, wacht al op settling, maar de navigatiepoging zelf faalde nog op punt 1 hierboven, niet getest of de settling-gate zelf werkt in de praktijk).
3. **Een echte, korte `NavigateToPose`-test met werkende costmap-obstakel-vermijding** — dit is de eigenlijke test die zou moeten aantonen dat Nav2 zelfstandig een obstakel (zoals de deurpost) detecteert en vermijdt of stopt, ongeacht onderliggende gait-drift. Nog niet gelukt (faalde vandaag op de initial-pose-gok, punt 1).
4. **Pad B (zachte gait) blijft on hold** — werkte goed op de draaischijf (0,80-0,90×) maar gaf afzet-slip op de echte vloer (ratio zakte naar 0,58×). Fysieke inspectie van de looppunten (materiaal/slijtage) staat nog open, nog niet gedaan.

### 🟡 Bekend maar lagere prioriteit
- **Zijwaartse drift tijdens recht-vooruit-lopen (bewust uitgesteld, zie herprioritering hierboven).** Kwantitatief bevestigd 2-4× groter dan de 10-augustus-baseline (~12,25°/meter vandaag vs. ~2,6-5,6°/meter origineel) — geen normale spreiding. **Software-regressie uitgesloten** (byte-diff bevestigt `phoenix_gait.py` identiek aan de gevalideerde versie, nu beschermd bewaard in `software/pi/gait/originals/phoenix_gait_ORIGINAL_VALIDATED_10aug2026.py` — **dit bestand nooit overschrijven**; `phoenix_driver.py`'s bewegingslogica functioneel ongewijzigd). Oorzaak is dus fysiek: mechanische verstoring van de poten-neutraalstand door vandaag's torque-cycli (splay-stand, `get_up_from_deep.py`, draaischijf), of vloer/locatie-specifiek (drempel bij de deurpost). Vervolgtest zodra dit weer prioriteit krijgt: schone rechte-lijn-test op een vlakke plek, bij voorkeur de oorspronkelijke 10-augustus-testlocatie, om vloer vs. mechanisch te scheiden.
- Welk exact aspect van de gait (frequentie, amplitude, fase) rf2o tijdens het lopen laat mislukken — overbodig geworden nu Pad A het praktisch oplost, maar interessant voor dieper begrip.
- Zijwaartse beweging (`travel_z` in `phoenix_gait.py`) is nooit aangesloten in `phoenix_driver.py`'s `cmd_vel`-callback — potentieel nuttig, geen concrete stappen ondernomen.

### Advies voor de volgende sessie
Begin met punt 1 (zorgvuldige AMCL-initial-pose) en werk door naar punt 3 (een echte obstakel-vermijdende Nav2-test) — dat is de test die het meest direct aantoont of de robot veilig kan navigeren, belangrijker dan de drift zelf op te lossen. Doe dit met kleine, geïsoleerde stappen (zoals vandaag bij het rf2o-onderzoek), niet meerdere gelijktijdige aanpassingen.

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

### Wegen vooruit (bijgewerkt 11 augustus 2026, na afronding rf2o-onderzoek)

Het rf2o-rotatie-onderzoek (broncode-analyse → literatuur → zes schone draaischijf-metingen, alle 0,97-1,02×) is afgerond met een sluitende conclusie: **rf2o/LD06 zelf is betrouwbaar; de fout ontstaat specifiek doordat de oscillerende, schoksgewijze gait-beweging rf2o's lineaire "gladde-verplaatsing"-aanname schendt.** Volledige historie: [PROBLEMS.md](../problems/PROBLEMS.md#rf2o-overschat-rotatie-24-34-tijdens-phoenix_gait-tripod-beweging-11-aug-2026-root-cause-onderzoek) en [SLAM_NAV2.md](../slam/SLAM_NAV2.md#rf2o-rotatie-overschatting--broncode-onderzoek-11-aug-2026).

Op basis daarvan liggen nu vier paden open, elk apart testbaar:

**Pad A — Sensorarchitectuur — ✅ UITGEVOERD (11 aug 2026), forse verbetering, niet perfect.**
`ekf_params.yaml` aangepast: externe IMU (`imu0`) weer aan als enige yaw-bron (yaw+vyaw), `imu1` (STM32-onboard, 2Hz-beperkt) volledig uit, rf2o (`odom0`) blijft strikt tot x/y beperkt — één variabele tegelijk gewijzigd, zelfde methodologie als de eerdere isolatietests. Twee rotatieburst-tests (`isolate_odomfused_vs_imu.py`, phoenix_driver tripod-gait, 10s burst):
- Meting 1: IMU +12,0° → `/odom_fused` +9,0° → **ratio 0,74×**
- Meting 2: IMU +15,8° → `/odom_fused` +13,3° → **ratio 0,84×**

Gemiddeld ~0,79×, beide een onderschatting (i.p.v. rf2o's eerdere overschatting), en met een veel kleinere spreiding dan rf2o's eigen 2,4-3,4×-schommelingen. **Duidelijke verbetering** (fout van >140% naar ~20%), maar aanvankelijk nog niet 1,0×.

**✅ Doorbraak (zelfde dag, "Pad 4"-onderzoek naar de resterende afwijking): het was een meettiming-artefact, geen echte fout.** `settle_curve_test.py` bemonsterde `/imu` en `/odom_fused` herhaaldelijk ná de stop (i.p.v. één keer na een vaste 2,5-3s), en onthulde dat de externe IMU (grondwaarheid) na een gait-stop nog **~15-25 seconden fysiek naslingert** (een dempende oscillatie, vermoedelijk het lichaam dat nawiebelt na `phoenix_driver.py`'s abrupte stopsequentie) — geen sensorfout, een echte, langzaam dempende restbeweging. Convergentiecurve:

| t na stop | ratio |
|---|---|
| 1,4-13,0s | 0,73-0,79× |
| 16,3-22,0s | 0,86-0,94× |
| 25,4-38,2s | **0,96-1,00×** |

**Conclusie: bij voldoende wachttijd (~25-30s) is Pad A vrijwel perfect (0,96-1,00×).** Alle eerdere "0,74-0,90×"-metingen van vandaag (Pad A, B, C) zijn gemeten tijdens deze naslinger-transient (fixed ~2,5-3s wachttijd in `isolate_odomfused_vs_imu.py`/`isolate_odomfused_vs_imu.py`-achtige scripts) — dus systematisch te vroeg. De onderliggende nauwkeurigheid van Pad A was al die tijd al (bijna) perfect; alleen de meetmethode onderschatte hem.

**Nieuwe, praktische consequentie voor Nav2/AMCL:** de robot zelf/de EKF heeft na een stop wél echt ~15-25s nodig voor een volledig betrouwbare pose — Nav2 kan daar niet zomaar op wachten.

**Twee pogingen om de naslinger via de stopsequentie te verkorten — beide ZONDER aantoonbaar effect (11 aug 2026):**
1. **Sway/dip geleidelijk uitfaseren tijdens de decel-fase** (hypothese: de vaste-amplitude sway loopt door tot de abrupte overstap naar de statische neutraal-interpolatie, wat een snelheidssprong geeft). Geïmplementeerd door `_body_sway()` los aan te roepen — geen interne state, dus veilig te mengen met een dalende factor zonder de snelheids-ramp te verstoren. `settle_curve_test.py` gaf een vrijwel identieke convergentiecurve als zonder de fix (~25-30s tot 1,0×).
2. **Neutrale overgang 3× sneller** (`NEUTRAL_DURATION_S` 1,0s→0,3s; hypothese: een snelle, beslissende overstap geeft minder tijd om tijdens de overgang zelf te wiebelen). Ook hier geen meetbaar verschil — convergentie bleef rond ~25-30s.

**Beide wijzigingen teruggedraaid** naar de oorspronkelijke `phoenix_driver.py` (geverifieerd via diff tegen de wiki-mirror: functioneel identiek, alleen documentatie-commentaar toegevoegd). **Werkconclusie:** de bron van de naslinger zit dieper dan de stopsequentie-timing — waarschijnlijk mechanisch (lichaam/poten hebben na een verstoring nu eenmaal ~25-30s nodig om vlak te vallen, ongeacht hoe de laatste beweging eruitziet) of een langzame tijdconstante in de IMU's eigen interne filter. **Vervolgrichting:** niet verder zoeken naar een kortere stopsequentie, maar optie (b) — de EKF/AMCL de eerste ~25-30s na een stop-commando als "verhoogd-onzeker" laten behandelen i.p.v. de pose direct te vertrouwen. Nog niet geïmplementeerd.

**✅ Minimale veilige wachttijd bepaald (analyse van de drie `settle_curve_test.py`-runs samen):**

| t na stop | max. afwijking van 1,0× (over 3 runs) |
|---|---|
| 3-15s | 23-43% — volledig onbetrouwbaar |
| 18s | 6% — grens van bruikbaar, maar... |
| 21s | 14% — nog een terugval in één van de drie runs |
| **24-39s** | **2-6%, consistent over alle drie runs** |

**Vuistregel: minimaal ~24 seconden wachten** na een stop voordat een yaw-meting (of AMCL-pose-update) betrouwbaar is. Onder de 18s is de afwijking soms enorm (tot 43%); tussen 18-21s lijkt het bijna goed maar met een aangetoonde terugval; vanaf 24s bleef het in alle drie de onafhankelijke metingen stabiel klein.

**✅ Geïmplementeerd (11 aug 2026): `/pose_settling`-topic in `phoenix_driver.py`.** Nieuwe `std_msgs/Bool`-publisher op `pose_settling` (0,5Hz): `true` vanaf het moment dat `_do_stable_stop()` klaar is, gedurende `SETTLING_DURATION_S = 24.0`s, daarna automatisch `false`. Elke consument (AMCL-wrapper, Nav2 pre-flight-check, eigen scripts) kan dit aflezen om de pose tijdens dit venster als verhoogd-onzeker te behandelen i.p.v. de yaw direct te vertrouwen.
- **Getest en bevestigd werkend** (`test_settling_flag.py`): `settling=False` in rust → springt naar `True` bij het einde van de stopsequentie (~t=3,5s na het stop-commando, inclusief de ~2s stopsequentie zelf) → blijft `True` → valt terug naar `False` op **t=27,6s**, exact rond de verwachte 24s+opstarttijd.
- **Nog niet gedaan:** de daadwerkelijke consumptie van dit topic aan AMCL/Nav2-kant (bijv. `NavigateToPose` pas versturen als `pose_settling=false`, of AMCL's covariantie tijdelijk verhogen tijdens dit venster). Het topic zelf is de bouwsteen; de integratie in de navigatieketen is de vervolgstap.

**Pad B — Gait verzachten — deels bevestigd op draaischijf, verrassend probleem op echte vloer.**
Losse testvariant "soft_tripod" (`soft_gait_rotation_test.py`, standaard-TRIPOD-parameters niet gewijzigd): halve lift-hoogte (40→20mm), 50% langzamere cyclus (1,6→2,4s). Op de draaischijf: meerdere metingen 0,80-0,90× (t.o.v. standaard-tripod's 0,74-0,87×) — dichter bij 1,0×, gebruiker beoordeelde de beweging als "trager en minder lift, zag er goed uit". Stapgrootte vervolgens verhoogd op verzoek: 90mm (+50%) bleef goed (0,81×, geen zichtbare problemen), 120mm (verdubbeld) gaf duidelijke **slip** en ratio kelderde naar 0,38× — er zit dus een grens tussen 90-120mm.

**⚠️ Belangrijke correctie na verplaatsing naar de normale vloer:** dezelfde 90mm-zachte-variant gaf op de echte vloer (i.p.v. de gladde draaischijf) een veel slechtere ratio: **0,58×**. Standaard-tripod op diezelfde vloer bleef juist goed (**0,87×**) — dus dit is geen algemeen vloereffect, maar specifiek een probleem van de zachte/lage-lift-variant. **Twee samenhangende hypotheses (nog niet definitief onderscheiden, geen softwaretest mogelijk):**
1. **Onvoldoende grondspeling tijdens de zwaaifase:** bij normale lift (40mm) raken poten de grond nooit tijdens het zwaaien; bij de halve lift (20mm) kunnen ze net de vloer raken. Op de gladde draaischijf maakte dat weinig uit; op een vloer met meer grip/textuur kan een lage-lift-poot blijven haken/schuren.
2. **Looppunten (voettips) mogelijk te glad:** als de poten tijdens het lage-lift-zwaaien de vloer raken én de looppunten weinig grip hebben, kan dat contact **wegglijden** i.p.v. gewoon schuren — een onvoorspelbare verstoring. Vereist fysieke inspectie van de voettips (materiaal/slijtage), niet via software vast te stellen.
**Consequentie:** de reductie van de lift-hoogte (het kernelement van de zachte variant) is **niet zonder meer over te nemen** voor echt gebruik — werkt goed op een gladde testondergrond, faalt op de representatieve vloer. Cyclustijd-vertraging alléén (zonder lift-reductie) is nog niet apart getest en zou de eerdere winst mogelijk zonder dit risico kunnen geven — nog te proberen.

**Gerichte observatie (zelfde dag, herhaling op de vloer):** gebruiker keek specifiek naar de poten tijdens een herhaling van de 90mm-variant op de vloer (ratio dit keer 0,79×, dus wisselvalliger dan op de draaischijf) en zag **soms lichte slip tijdens het afzetten** (stand-/propulsiefase), niet tijdens het zwaaien. Dat verschuift het gewicht van de twee hypotheses hierboven: afzet-slip is een **grip/wrijvingsprobleem tijdens de standfase**, los van de lift-hoogte van de zwaaiende poten. Dit ondersteunt hypothese 2 (te gladde looppunten) directer dan hypothese 1 (onvoldoende zwaai-clearance) — al kunnen beide nog steeds samenspelen. Fysieke inspectie van de looppunten (materiaal/slijtage) blijft de aangewezen vervolgstap, nog niet gedaan.

**Zijdelingse vondst (nog niet geïmplementeerd):** `phoenix_gait.py`'s `foot_targets()` ondersteunt al een `travel_z`-parameter voor zijwaartse verplaatsing, maar `phoenix_driver.py`'s `cmd_vel`-callback leest alleen `linear.x`/`angular.z` — `linear.y` (zijwaarts) wordt genegeerd. Potentieel nuttig om Nav2 minder afhankelijk te maken van juist de in-place-rotatiebursts die dit hele rf2o/EKF-onderzoek veroorzaakten (zijwaartse correcties i.p.v. draaien voor kleine laterale afwijkingen), en voor smalle-doorgang-scenario's. Nieuw idee, geen concrete stappen ondernomen.

**Pad C — Ander EKF-filtertype — ✅ UITGEVOERD (11 aug 2026), geen nauwkeurigheidswinst, wel betere herhaalbaarheid.**
`ukf_node` (Unscented Kalman Filter, geen lineariserende Taylor-benadering) gedraaid met exact dezelfde `ekf_params.yaml` (zelfde parameterschema als `ekf_node`) en dezelfde standaard-tripod-gait als Pad A. Twee metingen: **0,85× en 0,85×** — vrijwel identiek aan elkaar, tegenover EKF's 0,74×/0,84× (spreiding 0,10). **Geen duidelijke verbetering in gemiddelde nauwkeurigheid t.o.v. Pad A/EKF, maar wél merkbaar consistenter/herhaalbaarder.** Voor nu geen doorslaggevende reden om van EKF naar UKF te wisselen, maar de betere herhaalbaarheid is het overwegen waard als er later méér ruis in de mix komt (bijv. bij herintroductie van rf2o- of STM32-yaw als secundaire bron).

**Pad D — Fundamenteel/hardware (lange termijn)**
IK + voetcontact + IMU (+ LiDAR) — de aanpak uit alle onderzochte legged-robot-implementaties (Cerberus, VILENS, OCELOT, Leg-KILO). Vereist nieuwe sensorhardware (voetcontact-detectie per poot), dus een echte investering, geen configuratiewijziging. Achter-de-hand-optie als A/B/C onvoldoende blijken.

**Downstream (geen apart pad, vervolgstap zodra A/B/C iets opleveren):**
1. AMCL-rotatie-burst-convergentie herhalen (`verify_amcl_pose.py`, alle 4 richtingen), inclusief de nog onbevestigde "90°-blinde-hoek"-observatie.
2. Een tweede live `NavigateToPose`-test naar een zichtbaar doel, met vooraf geverifieerde AMCL-oriëntatie (`mark_amcl_pose.py`) — succescriterium is de juiste richting, niet alleen SUCCEEDED.

---

## Wat NIET meer op deze lijst staat (bewust)

- ~~`app_muto.py`'s autostart permanent uitschakelen~~ — bewust behouden, zie [README.md](../README.md) regel 7 en [TIMELINE.md](TIMELINE.md). Elke stack lost dit zelf op bij eigen opstart.
