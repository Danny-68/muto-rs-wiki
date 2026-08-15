# 🗺️ Roadmap — Autonome navigatie, Dify-besturing & Jetson-AI

Overkoepelend statusoverzicht van de grote visie: een volledig autonome, natuurlijke-taal-aangestuurde hexapod met SLAM/Nav2-navigatie, Dify/LLM-besturing, en de Jetson als GPU-co-processor. Opgesteld 9 augustus 2026 door het hele project (lokale code + `muto-llm-2.0`-broncode, niet alleen de documentatie) door te lezen.

---

## 🎯 Planningssessie 15 augustus 2026 — IMU-taakverdeling, stop-and-correct-navigatie, afstandskalibratie (nog niet getest)

**Pure planningssessie, geen hardware aangeraakt.** Doorgesproken op basis van deze wiki plus de codebase; hieronder de conclusies en het vervolgplan. Bouwt voort op Pad A hieronder (11 aug) en de AMCL-grid-search-procedure (14 aug, zie PROBLEMS.md) — vervangt die niet.

**⚠️ Reconciliatie nodig bij start volgende sessie:** dit hele overleg ging uit van `ekf_params.yaml` (Pad A, externe ICM20948 als primaire yaw) als actuele config. De 14-augustus-overdracht meldt echter dat de externe IMU die avond is losgekoppeld (magnetometer-timeout) en dat de EKF sindsdien op `ekf_params_stm32_yaw.yaml` draait. Niet geverifieerd of dit inmiddels hersteld is — zie OVERDRACHT.md punt 1.

### A. Odometrie/EKF-architectuur
- Bevestigd al geïmplementeerd (11 aug, zie hieronder): RF2O alleen x/y, geen yaw; externe IMU primaire yaw/vyaw; STM32-yaw (`imu1`) uit voor isolatietest.
- **Nog onbewezen:** RF2O x/y-betrouwbaarheid specifiek tijdens gait (los van de al onderzochte yaw-vraag) — hier is nooit apart naar gekeken, alleen naar yaw.
- **Nieuw idee, nog niet gebouwd:** residual-gate-node — vergelijk `gyro_z` (IMU) met RF2O's hoeksnelheid; bij grote afwijking RF2O's covariance in het doorgestuurde odom-bericht dynamisch ophogen i.p.v. RF2O hard aan/uit te zetten. `robot_localization` gebruikt de covariance uit het inkomende bericht zelf, dus dit is technisch direct haalbaar als een kleine tussenlaag-node. Pas zinvol ná bevestiging dat RF2O x/y inderdaad wisselend betrouwbaar is.
- Magnetometer (AK09916 in de ICM20948): bewust nog niet fuseren — 18 busservo's met wisselende stroom per gaitfase kunnen gecorreleerde (niet middelbare) storing geven. Eerst los karakteriseren.

### B. IMU-taakverdeling (onboard STM32 vs. externe ICM20948)
- **Onboard STM32-IMU** → lokale closed-loop besturing (`rotate_to_angle()` in `robot_bridge.py`, pollt op 50Hz zonder gemelde problemen zolang er geen gelijktijdige gait-servocommando's over dezelfde seriële lijn lopen).
- **Externe ICM20948** → bedoeld als primaire yaw/vyaw voor ROS2/EKF, aparte I²C-bus, geen bus-contentie met servobesturing.
- Preciezere verklaring van het eerder gevonden "10Hz breekt de gait"-probleem (`phoenix_driver.py`, `STM32_IMU_HZ = 2`): het is niet de sensor die inherent problematisch is, het is **bus-contentie bij gelijktijdig pollen terwijl gait-servocommando's over dezelfde seriële lijn lopen**. Dat verklaart waarom `rotate_to_angle()`'s 50Hz-onboard-polling wél probleemloos werkt (geen gelijktijdige gait-stream).
- Geen dubbele yaw-fusie in de EKF (al zo, zie A).
- **Nieuw idee, goedkoop toe te voegen:** beide IMU-yaws (extern + onboard) naast elkaar loggen tijdens dezelfde gait, puur als plausibiliteitscheck/diagnose — geen fusie, wel een vroege waarschuwing als één van beide duidelijk afwijkt.

### C. Stop-and-correct navigatie
Idee: tijdens het lopen niet proberen continu perfecte odometrie te leveren, maar periodiek stoppen en de LiDAR/AMCL een absolute correctie laten geven — analoog aan de al bewezen aanpak dat losse metingen na voldoende stilstand (`/pose_settling`, ≥24s) veel betrouwbaarder zijn dan tijdens beweging.
- Bouwstenen bestaan al: `/pose_settling`-topic (`phoenix_driver.py`) + `guarded_navigate_test.py` (wacht op settled → one-shot AMCL-poll, met workaround voor het latched-topic-probleem → stuurt één relatief `NavigateToPose`-doel).
- **Nog te bouwen:** dit patroon omvormen tot een herhalende lus die de totale afstand in segmenten opknipt (bv. 50cm-1m) met een settle+AMCL-correctie tussen elk segment, i.p.v. de hele afstand in één Nav2-doel te laten afleggen.
- **Open vraag:** de bewezen AMCL-procedure uit de 14-augustus-sessie (grid-search over x,y,yaw + visuele bevestiging) is een zware, meerdere-seconden-procedure. Een korte tussenstop van een paar honderd ms + één `/amcl_pose`-poll is veel lichter — nog niet aangetoond of dat voldoende betrouwbaar is voor een correctie, of dat de zwaardere procedure nodig blijft. Eerst empirisch checken (AMCL-pose+covariance loggen bij korte stops, vergelijken met de grid-search-referentie).
- Segmentlengte tussen correcties is geen vrije keuze: die volgt uit hoeveel drift IMU+gait-dead-reckoning opbouwt over die afstand (zie D/E) plus AMCL's "capture range".
- Noodrem (obstakel tijdens lopen) blijft functioneel gescheiden van deze correctielus, en moet — net als het bestaande e-stop-lesje — de STM32-seriële stop raken, niet alleen ROS `cmd_vel=0`.

### D/E. Karakterisering + afstandskalibratie (gecombineerd uit te voeren)
- **Bevinding (via bestandsdatums, niet aannames):** `SPEED_TABLE` in `robot_bridge.py` is gemeten **1 juli 2026**; alle `logs/forward_drift_test*.py`/`backward_drift_test.py`-runs zijn van **9 augustus**. Beide liggen vóór twee gait-wijzigingen die de effectieve staplengte plausibel beïnvloeden: `fix_foot_delta.py` (10 aug, herschrijft `_foot_delta()`-formule volledig) en `deepen_splay.py`/`find_deep_splay.py` (12 aug, dieper/vlakker beenstand-profiel). **De huidige afstandskalibratie dekt dus een gait-versie die niet meer bestaat.**
- `STEP_DISTANCE_M = 0.10` (`robot_bridge.py`) heeft geen dateringscomment — vermoedelijk nooit empirisch bevestigd, apart meenemen.
- Yahboom's officiële repo (`YahboomTechnology/Muto-RS`, GitHub) doorzocht: geen bruikbare gait/staplengte-broncode, alleen cursus-PDF's (`18.Robot chassis control/1.Hexapod gait and kinematics.pdf`). `phoenix_gait.py` is eigen code — geen externe referentiewaarden beschikbaar, alles moet zelf gemeten worden.
- **Voorstel:** één combi-testscript (uitbreiding van `phoenix_yaw_drift_test.py`'s log-/meetlint-patroon + `forward_drift_test*.py`'s afstandsmeting) dat in dezelfde sessie afdekt: IMU-drift-karakterisering, RF2O-x/y-betrouwbaarheid, yaw-rate-residual-logging (voor A), én de afstandskalibratie zelf — inclusief een in-place-draai-variant zonder netto translatie, om vibratie-invloed te scheiden van de translatie+rotatie-combinatie.

### Samengevat stappenplan
Zie OVERDRACHT.md "Direct te doen" voor de genummerde, uitvoerbare volgorde (begint met het verifiëren van de externe-IMU-status).

---

## ✅ Uitvoering 15 augustus 2026 — karakteriseringstests gedraaid, MAG_GAIN-rotatiebug gevonden

Vervolg op de planningssessie hierboven, zelfde dag. Externe IMU is door de gebruiker opnieuw aangesloten (in de verhoogde/geïsoleerde positie van 11 aug); `imu_publisher.py` los getest, geen magnetometer-timeout meer, `/imu` stabiel op 20Hz. `ekf_params.yaml` (Pad A) bleek in de container al onveranderd correct te staan (RF2O x/y, extern IMU yaw, STM32-yaw uit) — het losse `ekf_params_stm32_yaw.yaml`-bestand van 14 aug staat er nog maar wordt door niets meer aangeroepen.

**Nieuw testscript:** [`combi_calibration_test.py`](../../../combi_calibration_test.py) (host: `/home/pi/`, container: `/root/`) — combineert `phoenix_yaw_drift_test.py`'s meetlint-/yaw-logpatroon met continue `/imu`+`/odom`-logging via een losse `rclpy`-node, geïnterleaved met de 50Hz-gaitloop (non-blocking `spin_once`). Vereist LiDAR+robot_state_publisher+rf2o+imu_publisher draaiend, NIET phoenix_driver.py/ekf_node (zelfde exclusieve-serial-poort-reden als het bestaande testscript). Fases: `stationary`, `stm32_hz`, `forward` (met `--direction`), `rotate_inplace` (met `--rotate-direction`), `combined` (met `--pattern` van F/L/R/U-stappen).

### Stationary-fase (IMU-ruisband in rust, geen beweging)
| Kanaal | Min | Max | Gem. |
|---|---|---|---|
| roll_deg | -1,642 | -1,512 | -1,567 |
| pitch_deg | -0,019 | 0,503 | 0,400 |
| gyro_z_dps | -0,417 | 0,285 | -0,060 |
| accel_mag_mps2 | 10,245 | 10,379 | 10,310 |

Twee dingen: (1) roll/pitch hebben een kleine **statische offset** (montagehoek, geen ruis rond 0) — toekomstige noodstop-drempels moeten hier relatief aan zijn. (2) `accel_mag` ligt structureel op **~10,31 m/s², niet 9,81** — vermoedelijk een ongekalibreerde schaalfactor in `imu_publisher.py` (geen accel-kalibratie in de code). Ook hier: drempels relatief aan 10,31, niet aan de natuurkundige 9,81.

**Scriptbug gevonden en gefixt tijdens deze fase:** de eerste ~10ms na elke buffer-reset gaf een opstart-transiënt (17,14 i.p.v. ~10,3 m/s²) — `SensorLogger.noise_band()` slaat nu de eerste 0,2s na een reset over.

### STM32-Hz-bus-contentie (continu pollen tijdens actieve gait, op verschillende rates)
Reproduceert/actualiseert de "10Hz breekt de gait"-bevinding uit `phoenix_driver.py` op de huidige (post-`fix_foot_delta`/post-`deepen_splay`) gait. **Meetprincipe:** `iface._ser` is dezelfde seriële poort als de servo-commando's, dus een STM32-read verdringt letterlijk het eerstvolgende servo-commando — meetbaar als extra wall-clock-tijd t.o.v. de verwachte duur (`steps_needed * dt`).

**Eerste run had een timing-bug** (`next_poll += interval_s` i.p.v. relatief aan nu) die bij 5Hz/10Hz op hol sloeg (poll-op-elke-stap zodra een read langer duurde dan het interval) — wall-tijd liep op tot 104-107s i.p.v. de verwachte 8,5s. Gefixt (`next_poll = time.monotonic() + interval_s`) en herhaald:

| Rate | Wall-tijd | Verwacht | Overhead | STM32-reads | Werkelijke rate |
|---|---|---|---|---|---|
| 0Hz (baseline) | 11,58s | 8,48s | +36,6% | 0 | — |
| 2Hz (huidige productie) | 15,92s | 8,48s | **+87,8%** | 22 | ~1,38Hz |
| 5Hz | 22,54s | 8,48s | +165,8% | 53 | ~2,35Hz |
| 10Hz | 31,36s | 8,48s | +269,8% | 105 | ~3,35Hz |

**Conclusie: nee, 2Hz is niet "voldoende zonder hinder"** (dat stond nog als open vraag in `phoenix_driver.py`'s comment) — het is alleen minder erg dan hogere rates. Overhead schaalt ~lineair met de gevraagde rate; de werkelijk haalbare rate plafonneert rond ~3,4Hz (harde seriële-protocol-beperking, niet oplosbaar door hoger te vragen). Zelfs de 0Hz-baseline heeft al +36,6% overhead puur door de Python/rclpy-loop zelf.

### Afstandskalibratie vooruit/achteruit
2 reps continu (geen reset ertussen, dus gemeten als 1 doorlopende meting van 10,6 cycli):

| Richting | Meetlint totaal | cm/cyclus | RF2O totaal | RF2O-ratio |
|---|---|---|---|---|
| Vooruit | 101,0cm | 9,53 | 94,9cm | 0,940 |
| Achteruit | 102,5cm | 9,67 | 95,5cm | 0,932 |
| **Gemiddeld** | | **9,60** | | **0,936** |

- **`MAX_LINEAR_SPEED_MPS` in `phoenix_driver.py` blijft bevestigd geldig**: 9,60cm/cyclus ÷ 1,6s ≈ 0,0600 m/s tegenover de huidige 0,0594 m/s — binnen meetruis, ondanks de twee gait-wijzigingen sindsdien. Geen update nodig.
- **Belangrijk scoping-punt:** dit kalibreert `phoenix_driver.py`'s cycle-gebaseerde constante (het pad dat Nav2 gebruikt), NIET `robot_bridge.py`'s `SPEED_TABLE` (STM32-firmware-gait via `muto_driver_fixed.py`, een ander bewegingsmechanisme, gebruikt door de Dify/spraak/HTTP-commando's). Die laatste kalibratie is dus nog steeds niet vernieuwd.
- **Nieuwe bevinding: RF2O onderschat x/y consistent ~6-7% in beide richtingen** (0,940 en 0,932, niet toevallig verschillend) — eerste concrete data op de eerder openstaande vraag "is RF2O x/y betrouwbaar tijdens gait" (was 🟡). Consistente richtingsonafhankelijke onderschatting, geen teken-wisselende fout zoals bij yaw — zou in principe met een vaste factor te corrigeren zijn (in tegenstelling tot yaw). Nog n=2, dus voorlopig signaal.

### Rotate_inplace — belangrijke bevinding: externe IMU onbetrouwbaar bij actieve rotatie, in BEIDE richtingen (niet alleen linksom zoals eerder gedacht)

**Scriptbug gevonden en gefixt tijdens deze fase:** yaw-delta-berekeningen (`stm32_drift_deg`, `ext_drift_deg`) deden een kale aftrekking zonder rekening te houden met de ±180°-wrap van de yaw-representatie — gaf een keer -304,98° i.p.v. de werkelijke +55,02°. Nieuwe `wrap_deg()`-helper toegevoegd, overal toegepast.

Na de fix, met de originele `MAG_GAIN=0,01`:

| | STM32 | RF2O (geïmpliceerd) | Externe IMU |
|---|---|---|---|
| Links rep1 | +54,47° | — | +24,58° (te klein) |
| Links rep2 | +55,02° | +55,19° | **-42,03° (verkeerd teken)** |
| Rechts rep1 | -55,94° | — | **+15,0° (verkeerd teken)** |
| Rechts rep2 | -55,87° | -55,96° | **+26,3° (verkeerd teken)** |

STM32 en RF2O zijn onderling zeer consistent (~55-56° per rep, RF2O binnen 0,2° van STM32) in beide richtingen — beide te vertrouwen voor rotatie. De externe IMU is structureel fout, **niet alleen linksom** zoals de 14-augustus-overdracht suggereerde — hier is rechtsom zelfs slechter (beide reps verkeerd teken, tegenover 1-van-2 bij links).

**Root cause gevonden (voorlopig, workaround bevestigd):** `imu_publisher.py` gebruikt `MAG_GAIN=0.01` (magnetometer-correctie), met een in de eigen docstring al gevlagde, nooit-geverifieerde as-remap tussen het magnetometer- en accel/gyro-die. Met `MAG_GAIN=0.0` (zuivere gyro-integratie, magnetometer-bijdrage uitgeschakeld) herhaald:

| | STM32 | Extern (MAG_GAIN=0) | Verschil |
|---|---|---|---|
| Links | +55,86° | +57,20° | 1,3° (~2,4%) |
| Rechts | -58,08° | -58,33° | 0,3° (~0,4%) |

Beide richtingen nu consistent. **Belangrijke nuance (gebruiker checkte dit expliciet):** de externe IMU zat al in de verhoogde/geïsoleerde positie van 11 augustus (niet vlak bij het metalen frame) — dus dit is waarschijnlijk niet dezelfde fysieke-interferentie-oorzaak van toen, eerder een echte softwarebug in de magnetometer-fusie. Niet 100% zeker; beide hypotheses (as-remap-bug vs. toch nog resterende fysieke interferentie) blijven open tot verder onderzocht.

**⚠️ `MAG_GAIN=0.0` is bewust een workaround, geen fix, en blijft zo staan** (besluit gebruiker, 15 aug). Backup van de originele waarde: `imu_publisher.py.bak_20260815_maggaintest` (host én container). **Consequentie: langetermijn-yaw-drift-risico is heropend** — zonder magnetometer-correctie is er geen absolute-heading-referentie meer, puur gyro-integratie zal over langere missies wegdrijven (dit was het allereerste punt van de hele 15-augustus-sessie, nu weer relevant). Root-cause-onderzoek (as-remap verifiëren tegen het ICM20948-datasheet, Figuur 12/13) staat open voor een latere sessie.

### Combined-test (F→U→F→L: vooruit, 180°-draai, vooruit, kleine draai) — bevestigt de fix houdt stand
Nieuw, flexibel patroon-systeem toegevoegd aan `phase_combined` (was: alleen afwisselend vooruit/altijd-linksom, liep bij elk segment verder van start af). Nu: `--pattern` van F/L/R/U-stappen, `U` = 180° (17,1 cycli, afgeleid van de rotatiemeting hierboven).

| Bron | Gemeten delta | 
|---|---|
| STM32 | -124,2° |
| Externe IMU (MAG_GAIN=0) | -123,7° |
| RF2O | -127,6° |

Verwacht (180°+55° links, gewrapt): -125°. Alle drie binnen ~4° van elkaar en van de verwachting, óók door een complexere manoeuvre heen (niet alleen een geïsoleerde rotatie) — goede extra bevestiging dat de `MAG_GAIN=0`-workaround robuust is, geen toevalstreffer. Ruisband tijdens actieve gait ook gelogd (`accel_mag` 8,92-12,19 m/s², gem. 10,31 — gelijk aan de stilstand-baseline maar bredere spreiding; `gyro_z` -24,9 tot +15,8°/s) — bruikbaar voor de eerder besproken noodstop-drempel-discussie.

### Openstaande punten na deze sessie
1. ~~As-remap-root-cause nog niet gevonden~~ — ✅ **opgelost, zie sectie hieronder.** As-remap bleek correct; werkelijke oorzaak was hard-iron-afwijking + nabijheid voedingsbord.
2. **`robot_bridge.py`'s `SPEED_TABLE`/`STEP_DISTANCE_M`** — nog steeds niet vernieuwd (ander bewegingspad dan wat vandaag gekalibreerd is, zie scoping-punt hierboven).
3. **STM32-Hz-overhead blijft bestaan zelfs bij 2Hz** (+87,8%) — geen actie ondernomen, alleen gekwantificeerd.
4. **Kleine steekproeven overal** (n=1-2 per conditie) — sterke, consistente signalen, maar nog geen robuuste kalibratie.
5. De residual-gate-node (A hierboven) en de stop-and-correct-navigatielus (C hierboven) zijn nog niet gebouwd — deze sessie leverde alleen de karakteriseringsdata die daarvoor nodig was.

---

## ✅ Vervolg 15 augustus 2026 (avond) — as-remap-root-cause opgelost: fysieke plaatsing + magnetometer-kalibratie

Zelfde dag, vervolg op de sectie hierboven. Doel: de `MAG_GAIN=0`-workaround vervangen door een echte fix, zodat de magnetometer-correctie (en daarmee de langetermijn-drift-correctie) weer aan kan.

### Stap 1: as-remap geverifieerd tegen het officiële datasheet — bleek correct
`ds-000189-icm-20948-v1.5.pdf` (TDK/InvenSense, via SparkFun-mirror gedownload) pagina 83, Figuur 12 (accel/gyro-assen) vs. Figuur 13 (magnetometer-assen) vergeleken met de remap in `imu_publisher.py` (`mx_b, my_b, mz_b = my, mx, -mz`). De Z-as-inversie is ondubbelzinnig bevestigd in de diagrammen; de X/Y-swap komt overeen met de veelgeciteerde community-standaardremap (ook gebruikt in SparkFun/Adafruit/InvenSense-eigen drivers). **Conclusie: de as-remap was nooit de bug.** Dit verschoof de verdenking naar de expliciet-niet-gedane hard-iron/soft-iron-kalibratie.

### Stap 2: fysieke montage bleek dicht bij het voedingsbord — verplaatst, 3 iteraties
Foto's van de montage lieten zien dat de ICM20948 op korte (deels metalen) afstandhouders zat, direct boven/naast het voedingsverdeelbord (elco's + XT30-connector, de plek met de grootste servo-stroomschommelingen) en dicht bij een servo. Dat is niet de "verhoogde/geïsoleerde" positie die de 11-augustus-overdracht beschreef.

Drie posities getest (rotatietest links/rechts, `MAG_GAIN=0,01`, telkens tegen STM32 als referentie):

| Positie | Links | Rechts |
|---|---|---|
| 1 — origineel, bij voedingsbord | 24,6°/-42,0° vs ~55° (verkeerd teken) | 15,0°/26,3° vs ~56° (verkeerd teken) |
| 2 — verhoogd, kunststof afstandhouder | 37,4° vs 49,7° (-25%) | -57,6° vs -51,3° (+12%) |
| 3 — nogmaals aangepast | 28,4° vs 46,2° (-38%) | -32,8° vs -50,2° (-35%) |

Niet monotoon verbeterd, maar wel een verschuiving in foutpatroon: van chaotisch/teken-wisselend (positie 1, past bij **dynamische** stroom-afhankelijke interferentie) naar consistent-richtingsonafhankelijk (posities 2-3, past bij een **statische** hard-iron-afwijking). Dat wees erop dat verplaatsing de dynamische component grotendeels wegnam, en dat een kalibratie het overblijvende statische deel zou moeten oplossen.

**Overwogen en verworpen alternatieve hypothese:** off-axis-montage (IMU niet op de rotatie-as) zou via centripetale/tangentiële versnelling de accel-gebaseerde roll/pitch-schatting kunnen verstoren, en zo indirect de yaw via de tilt-gecompenseerde magnetometer-heading. Berekend met gemeten hoeksnelheid (~6-10°/s) en geschatte montage-afstand (~4cm): centripetaal ≈0,001 m/s², tangentieel ≈0,07 m/s² — beide verwaarloosbaar t.o.v. de gemeten ruisband (±0,1-1,6 m/s²) en identiek aan roll/pitch-ruis die ook tijdens gewoon vooruit lopen optreedt (geen rotatie-specifieke signatuur). Fysiek plausibel punt, maar bij dit tempo/deze afstand niet de verklaring.

### Stap 3: hard-iron/soft-iron-kalibratie
Nieuw script [`mag_calibration.py`](../../../mag_calibration.py) (host `/home/pi/`, container `/root/`): 2 volle rotaties, ruwe magnetometer-x/y/z gelogd (5459 samples), min-max-kalibratie (niet een volledige ellipsoïde-fit — de robot draait vooral om de yaw-as, dus roll/pitch-variatie is te beperkt voor een goed geconditioneerde 3D-fit).

**Bevinding tijdens het draaien:** het script liep >2x langzamer dan verwacht (240s+ i.p.v. ~110s) — `ICM20948.read_magnetometer_data(timeout=1.0)` moet kennelijk regelmatig wachten tot een nieuwe sample klaar is, vergelijkbaar mechanisme als de STM32-Hz-bus-contentie (idem: vast aantal gaitstappen, dus geen vastloper, alleen uitgerekt in tijd — gebruiker bevestigde visueel "hij beweegt heel langzaam").

**Resultaat:**

| As | Range | Offset (hard-iron) | Schaal (soft-iron) |
|---|---|---|---|
| x | 39,15 | -7,575 | 0,727 |
| y | 36,15 | 22,575 | 0,787 |
| z | 10,05 (te klein, schaal overgeslagen) | 74,775 | 1,000 |

Verwerkt in `imu_publisher.py` als `MAG_OFFSET`/`MAG_SCALE`-constanten, toegepast op de ruwe magnetometerwaarden vóór de as-remap/tilt-compensatie. Volledig resultaat: `/root/logs/mag_calibration_result.json`.

### Validatie: `MAG_GAIN` terug naar 0,01 (correctie AAN) — probleem opgelost, geen workaround meer nodig

| | STM32 | Extern (gekalibreerd, MAG_GAIN=0,01) | Afwijking |
|---|---|---|---|
| Links | +52,56° | +52,49° | 0,13% |
| Rechts | -53,69° | -52,59° | 2,05% |

Gecombineerde manoeuvre (`F,U,F,L`) ter bevestiging herhaald:

| Bron | Gemeten delta |
|---|---|
| STM32 | -147,37° |
| Extern (gekalibreerd) | -149,76° |
| RF2O | -146,34° |

Spreiding van 3,4° tussen alle drie, ook door een complexere manoeuvre heen. **Dit is een echte fix, geen workaround** — de magnetometer-correctie staat weer aan, dus de langetermijn-drift-correctie is niet meer opgeofferd voor rotatienauwkeurigheid.

### Definitieve root cause
Twee samenwerkende factoren, geen van beide alleen voldoende:
1. **Dynamische interferentie** door nabijheid van het voedingsbord/de XT30-connector (servo-stroom-afhankelijk) — verholpen door fysieke verplaatsing.
2. **Statische hard-iron-afwijking**, nooit gekalibreerd — verholpen door `mag_calibration.py`.

De as-remap (het oorspronkelijke verdachte uit de docstring) bleek na verificatie tegen het officiële datasheet correct.

### Reflectie: wat dit betekent voor het architectuurplan van de planningssessie (zelfde dag)

Het plan uit de "🎯 Planningssessie"-sectie hierboven hoeft niet herzien te worden — het is grotendeels bevestigd. Puntsgewijs:

**Sterker onderbouwd dan bij het opstellen van het plan:**
- **Pad A (externe IMU primaire yaw)** — het uitgangspunt van de hele sessie werd tijdens het testen zelf tijdelijk twijfelachtig (de rotatiebug), maar is nu daadwerkelijk gevalideerd (0,1-2,1% afwijking, ook met magnetometer-correctie aan) i.p.v. alleen aangenomen.
- **IMU-taakverdeling (extern=continue EKF, onboard=lokaal)** — de STM32-Hz-bus-contentie-meting (+87,8% overhead zelfs bij 2Hz) onderbouwt waarom, en de externe IMU is nu bewezen betrouwbaar genoeg om die rol volledig te dragen.
- **Astra geparkeerd houden** — beide odometriebronnen zijn nu gekarakteriseerd en bruikbaar (RF2O met een correctiefactor); nog minder reden voor een extra sensor dan bij het opstellen van het plan.

**Overbodig of minder urgent geworden:**
- **De residual-gate-node (dynamische RF2O-covariance, plan-sectie A)** — dit idee ging uit van *wisselend* betrouwbare RF2O (soms goed, soms fout, vandaar een dynamische trust-gate). De meting laat i.p.v. daarvan een **consistente, richtingsonafhankelijke onderschatting van ~6-7%** zien — een stabiele bias, geen chaos. Dat vraagt om een simpele vaste schaalcorrectie (~1,068×), niet om het dynamische gate-mechanisme uit het oorspronkelijke plan.
- **Stop-and-correct-navigatie (plan-sectie C), urgentie verlaagd, niet weggevallen** — deels gemotiveerd door twee onzekerheden (onbetrouwbare RF2O-translatie, yaw-drift zonder correctie) die nu allebei zijn ingeperkt: RF2O heeft een voorspelbare bias, en de magnetometer-correctie bindt de yaw-drift al continu. Periodiek absoluut corrigeren blijft goede praktijk voor lange missies, maar is niet meer de noodzakelijke vangnet van toen beide odometriebronnen nog onbetrouwbaar leken.

**Nieuwe, goed gemotiveerde vervolgstap: Nav2 opnieuw testen.** De open bug van 14 augustus (`NavigateToPose` liep veel verder dan het doel, 30cm werd >50cm, 17 recoveries) is nooit verklaard. Nav2 laat de robot tijdens navigatie routinematig roteren om op het doel te richten — precies het scenario waarin de externe IMU tot vandaag kon falen (tot 75% fout, soms verkeerd teken). Als de EKF tijdens die test corrupte yaw kreeg tijdens zo'n rotatie, verklaart dat mogelijk het onvoorspelbare gedrag. Niet zeker, maar een plausibele kandidaat-oorzaak, nu voor het eerst testbaar met een gefixte yaw-bron. **Kanttekening:** de AMCL-initial-pose-valkuil (11 aug, een gok die in "lethal space" kan landen) is een losstaand, nog steeds geldig risico — eerst zorgvuldig via de bewezen procedure (`mark_amcl_pose.py`/grid-search) initialiseren, niet ervan uitgaan dat de IMU-fix ook dát oplost.

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

**✅ Doorbraak (11 aug 2026, laat op de avond): 180°-laser-TF-fout gevonden en gefixt — root cause van "confident maar verkeerd geconvergeerd".** Na de IMU-verbetering convergeerde AMCL nogmaals confident (lage covariantie) maar naar een **volledig verkeerde** positie/oriëntatie. In plaats van verder te gokken is gezocht in oudere sessie-transcripten (`mcp__ccd_session_mgmt__search_session_transcripts` gaf geen resultaten — bleek de index niet te dekken; in plaats daarvan direct de `.jsonl`-transcriptbestanden onder `~/.claude/projects/-home-pi/` doorzocht) naar eerder opgeloste, vergelijkbare problemen. **Gevonden:** een eerdere sessie (rond 30-31 juli) had exact dit patroon ("zoekt de krapste ruimte", AMCL confident-maar-fout) al eens grondig uitgezocht en teruggeleid tot een **180° laser-mounting-TF-fout** — bevestigd door Yahboom's eigen officiële URDF (`Muto.urdf`), die een `laser_scan_fix_joint` bevat (`rpy="0 0 π"`, exact 180°) tussen de link `laser` en een kind-link `laser_scan_fix`.

**Root cause vandaag:** deze correctie zit wél in het URDF, maar wordt nooit toegepast, omdat de YDLidar-driver `/scan` publiceert met `frame_id: laser` (de ONgecorrigeerde ouder-frame) i.p.v. `laser_scan_fix` (de gecorrigeerde kind-frame). Bevestigd via directe TF-checks: `base_link → laser` = identiteit (0°), `base_link → laser_scan_fix` = 180° — de correctie bestond dus in de TF-boom maar werd door niets gebruikt.

**Fix:** `frame_id: laser` → `frame_id: laser_scan_fix` in `ydlidar_ros2_driver/params/ydlidar.yaml`, gevolgd door een herstart van lidar → rf2o (die de laser-pose-TF eenmalig bij opstarten cachet, zie `setLaserPoseFromTf()`) → volledige Nav2-stack. Na deze fix + hernieuwde globale lokalisatie: **positie correct** (bevestigd door gebruiker), oriëntatie nog **~95° residuele afwijking** (waarschijnlijk een aparte, kleinere kalibratiekwestie — mogelijk gerelateerd aan een eerder genoteerd `reversion`-parameterverschil tussen onze YDLidar-config en Yahboom's officiële launch-config, nog niet verder onderzocht). Die 95° is **handmatig gecorrigeerd** via `/initialpose` (let op tekenconventie: een POSITIEVE yaw-correctie bleek in kaart-coördinaten een **linkse/CCW**-draai te zijn, niet rechts — het tegenovergestelde van de eerdere `cmd_vel`-tekenconventie).

**Bevestigde, werkende pose (11 aug 2026, laat):** x=-1,648, y=-0,870, yaw=162,5° — gebruiker bevestigde dit visueel als correct, covariantie laag (0,26/-/-). **Dit is nu het vertrekpunt voor de volgende Nav2-navigatietest.**

**Nog openstaand:**
- De resterende ~95°-oriëntatie-afwijking (vóór de handmatige correctie) verder root-causen — mogelijk het `reversion`-parameterverschil met Yahboom's officiële config.
- De `frame_id`-fix + eventuele `reversion`-fix structureel vastleggen in het opstartscript/params (nu een losse `sed`-aanpassing in een container-lokaal bestand, gaat verloren bij een image-rebuild of als een vers `ydlidar.yaml` wordt gebruikt).
- Deze hele TF-fix nog niet getest tegen een schone, ongecorrigeerde globale-lokalisatiepoging zonder de handmatige 95°-nacorrectie — nog niet bevestigd of de 95° een vaste, voorspelbare offset is of per sessie/positie varieert.
2. **`/pose_settling` daadwerkelijk consumeren** aan Nav2/AMCL-kant (bijv. `guarded_navigate_test.py` verder afmaken — bestaat al, wacht al op settling, maar de navigatiepoging zelf faalde nog op punt 1 hierboven, niet getest of de settling-gate zelf werkt in de praktijk).
3. **Een echte, korte `NavigateToPose`-test met werkende costmap-obstakel-vermijding** — dit is de eigenlijke test die zou moeten aantonen dat Nav2 zelfstandig een obstakel (zoals de deurpost) detecteert en vermijdt of stopt, ongeacht onderliggende gait-drift. Nog niet gelukt (faalde vandaag op de initial-pose-gok, punt 1).
4. **Pad B (zachte gait) blijft on hold** — werkte goed op de draaischijf (0,80-0,90×) maar gaf afzet-slip op de echte vloer (ratio zakte naar 0,58×). Fysieke inspectie van de looppunten (materiaal/slijtage) staat nog open, nog niet gedaan.

### 🟡 Bekend maar lagere prioriteit
- **Zijwaartse drift tijdens recht-vooruit-lopen (bewust uitgesteld, zie herprioritering hierboven).** Kwantitatief bevestigd 2-4× groter dan de 10-augustus-baseline (~12,25°/meter vandaag vs. ~2,6-5,6°/meter origineel) — geen normale spreiding. **Software-regressie uitgesloten** (byte-diff bevestigt `phoenix_gait.py` identiek aan de gevalideerde versie, nu beschermd bewaard in `software/pi/gait/originals/phoenix_gait_ORIGINAL_VALIDATED_10aug2026.py` — **dit bestand nooit overschrijven**; `phoenix_driver.py`'s bewegingslogica functioneel ongewijzigd). Oorzaak is dus fysiek: mechanische verstoring van de poten-neutraalstand door vandaag's torque-cycli (splay-stand, `get_up_from_deep.py`, draaischijf), of vloer/locatie-specifiek (drempel bij de deurpost). **⚠️ Herzieningspunt (11 aug 2026, later op de avond):** deze conclusie werd getrokken met metingen van de externe IMU **vóórdat** bleek dat die vlak bij het metalen frame gemonteerd zat (zie de nieuwe magnetometer-bevinding hieronder) — een deel van de gemeten "extra drift" kan dus een IMU-meetartefact zijn geweest, niet (uitsluitend) een echte fysieke afwijking. Vervolgtest zodra dit weer prioriteit krijgt: schone rechte-lijn-test op een vlakke plek, nu met de verplaatste/geïsoleerde IMU, bij voorkeur de oorspronkelijke 10-augustus-testlocatie, om vloer vs. mechanisch vs. meetartefact te scheiden.

### ✅ Nieuwe bevinding: externe IMU-magnetometer-interferentie door nabijheid metalen frame (bevestigd 11 aug 2026, avond)

Tijdens een rotatiekalibratie (vaste, veilige testduren, zie `software/pi/tools/rotation_calib_test.py`) bleek de externe IMU (ICM20948, gemonteerd vlak bij het metalen robotframe) sterk inconsistente metingen te geven: segmentsnelheden varieerend van 0,0005 tot 0,0333 rad/s, en zelfs **tekenwisselingen** (schijnbaar tegen de commando in draaiend) ondanks een constant rotatiecommando — dit was géén fysieke blokkade (gebruiker bevestigde de robot kon vrij draaien; visuele schatting van ~20° kwam wel overeen met de kleine IMU-cumulatief). Dit matcht een **al langer bekend, nooit opgelost punt** (IMU-magnetometer hard/soft-iron-kalibratie/as-remap, zie TIMELINE.md "Open punten") — metalen nabijheid is een klassieke bron van zowel statische (hard-iron) als **dynamische** (servo-stroom-afhankelijke) magnetometerverstoring.

**Test:** gebruiker verplaatste de externe IMU iets hoger en geïsoleerd van het metalen frame. Dezelfde rotatiekalibratie herhaald:

| duur | segment | cumulatief | snelheid |
|---|---|---|---|
| 5,0s | -17,2° | -17,2° | 0,0599 rad/s |
| 5,0s | -13,7° | -30,9° | 0,0479 rad/s |
| 8,0s | -22,6° | -53,4° | 0,0492 rad/s |
| 8,0s | -22,1° | -75,5° | 0,0481 rad/s |
| 8,0s | -18,1° | -93,6° | 0,0394 rad/s |

**Resultaat: alle segmenten consistent dezelfde kant op, snelheden nu allemaal in een smalle band (0,039-0,060 rad/s, gemiddeld ~0,049)** — dicht bij de oorspronkelijke `MAX_ANGULAR_SPEED_RADPS = 0,055`-kalibratie uit `phoenix_driver.py`. **Dit bevestigt de hypothese: IMU-plaatsing t.o.v. het metalen frame is een reële, significante foutbron**, niet alleen een theoretisch punt.

**Consequenties:**
1. Fysieke IMU-montage (hoger/geïsoleerd van metaal) is nu een aanbevolen, bevestigd-werkzame permanente wijziging, geen eenmalige test-only-actie.
2. Elke eerdere meting vandaag die de externe IMU als grondwaarheid gebruikte (Pad A/B/C-ratio's, de settle-curve-metingen, de drift-vergelijking hierboven) is **gedaan met de niet-geïsoleerde IMU** — die conclusies blijven waarschijnlijk kwalitatief geldig (de patronen waren consistent en verklaarbaar), maar de **exacte cijfers** verdienen een herhaling met de nu-verbeterde IMU-plaatsing voordat ze als definitief gelden.
3. **Methodologische les:** de externe IMU is de hele sessie als "grondwaarheid" behandeld zonder zijn eigen nauwkeurigheid onafhankelijk te verifiëren — dat bleek een reëel gat, nu gedicht voor toekomstige tests.

### ⚠️ Bijna-incident: runaway in het eerste, adaptieve kalibratiescript

Een eerste versie van `rotation_calib_test.py` berekende de duur van elk segment adaptief op basis van de laatst gemeten snelheid, met doelhoeken [45,90,135,180,270,360]. Toen de eerste, nog onzekere snelheidsschatting te laag bleek, draaide een bedoeld "45°"-segment in werkelijkheid veel verder door — en omdat de metingen via `wrap()` worden teruggebracht naar (-180°,180°], werd een grote werkelijke rotatie (bijv. >180°) foutief als een klein of tegengesteld getal gelezen. Die foute meting werd gebruikt om de volgende segmentduur te berekenen, wat tot een cascade van steeds onvoorspelbaardere bewegingen leidde (gebruiker meldde "eerst 45°, dan 270°, dan weer een grote hoek", en moest de robot laten stoppen). **Fix:** het script herschreven naar **vaste, korte, veilige testduren** (nooit afgeleid van een eerdere, mogelijk foute meting) — geen adaptieve/cascaderende duur-berekening meer. **Les:** bij een yaw-meting die via `wrap()`/atan2 tot (-180°,180°] beperkt is, nooit een vervolgactie (zoals een volgende bewegingsduur) baseren op een enkele, nog niet gevalideerde meting die in de buurt van de 180°-grens zou kunnen komen.
- Welk exact aspect van de gait (frequentie, amplitude, fase) rf2o tijdens het lopen laat mislukken — overbodig geworden nu Pad A het praktisch oplost, maar interessant voor dieper begrip.
- Zijwaartse beweging (`travel_z` in `phoenix_gait.py`) is nooit aangesloten in `phoenix_driver.py`'s `cmd_vel`-callback — potentieel nuttig, geen concrete stappen ondernomen.

### Advies voor de volgende sessie
Begin met punt 1 (zorgvuldige AMCL-initial-pose) en werk door naar punt 3 (een echte obstakel-vermijdende Nav2-test) — dat is de test die het meest direct aantoont of de robot veilig kan navigeren, belangrijker dan de drift zelf op te lossen. Doe dit met kleine, geïsoleerde stappen (zoals vandaag bij het rf2o-onderzoek), niet meerdere gelijktijdige aanpassingen.

---

## 🌙 Eindstatus sessie 11 augustus 2026 (laat op de avond) — vertrekpunt voor de volgende keer

Na de 180°-laser-TF-fix en de bevestigde, correcte pose (x=-1,648, y=-0,870, yaw=162,5°, zie hierboven) is geprobeerd de robot naar een door de gebruiker op de kaart aangewezen deuropening te laten draaien. Dit onthulde twee nieuwe, nog onopgeloste punten:

### ⚠️ Bijna-incident #2: blinde 50s-rotatie met niet-gevalideerde linksom-snelheid
Voor de draai naar de deuropening (berekend doel: +139,2° in kaart-yaw = linksom) is de **rechtsom**-snelheid van vanavond (0,049 rad/s, gekalibreerd ná de IMU-verplaatsing) zonder verificatie ook voor **linksom** aangenomen. Eén lange, blinde 50s-burst (dezelfde risicovolle aanpak die eerder vanavond al als onveilig was bestempeld — zie de eerdere "Bijna-incident: runaway in het eerste, adaptieve kalibratiescript") leidde tot een door de gebruiker geschatte ~200° rotatie i.p.v. de bedoelde 139°. Robot direct gestopt op gebruikersverzoek, geen schade. **Les (herhaald, nu extra nadrukkelijk):** nooit een enkele lange rotatieduur uitvoeren op basis van een voor die richting/dat moment niet-gevalideerde snelheid — ook niet voor praktische doelen, niet alleen voor testscripts. Linksom-snelheid met de verplaatste IMU is nog steeds niet apart gekalibreerd.

### ⚠️ Stapsgewijze correctiepoging: inconsistente resultaten, twee losse bugs gevonden
Vervolgens is geprobeerd stapsgewijs (3× ~30° rechtsom, met IMU-controle tussen elke stap) een gebruiker-geschatte -90°-correctie te doen. Resultaat: **-73,3° cumulatief gemeten (IMU)**, terwijl AMCL na afloop **-102,1°** t.o.v. het startpunt liet zien — de twee meetmethoden verschillen ~29° van elkaar, en AMCL's covariantie was op dat moment ook verhoogd (0,42, minder confident dan de eerdere 0,20-0,26).

Twee losse problemen geïdentificeerd:
1. **Wachttijd-bug in `incremental_rotate.py`:** de "27s-naslinger-wachttijd" tussen segmenten gebruikte `spin_once(timeout_sec=1.0)` in een lus van 27 iteraties i.p.v. een expliciete `time.sleep(27)`. `spin_once` keert terug zodra er een bericht binnenkomt, dus als IMU-berichten sneller dan elke seconde binnenkomen (aannemelijk), duurde de "wachttijd" in werkelijkheid veel korter dan 27s — de tussenmetingen zijn dus mogelijk genomen vóórdat de fysieke naslinger volledig was uitgedempt. **Fix nog niet doorgevoerd:** altijd expliciete `time.sleep()` gebruiken voor een wachttijd die een gegarandeerde reële duur moet hebben, nooit een spin-lus met een per-iteratie-timeout.
2. **Efficiëntieverlies bij korte segmenten (hypothese, niet hard bevestigd):** de behaalde hoek (-73,3°) was kleiner dan bedoeld (-90°) terwijl de totale tijd meer dan 2× zo lang was als een simpele snelheidsberekening zou voorspellen. Waarschijnlijke verklaring: bij elk kort segment gaat verhoudingsgewijs veel tijd op aan optrek-ramp (phoenix_gait's `_speed_ramp`, ~0,4-1s tot volle snelheid) en de vaste ~2s stopsequentie (decel+neutraal) — bij een korte 10,7s-burst is dat een aanzienlijk deel van de tijd niet op volle snelheid, wat de effectieve gemiddelde snelheid verlaagt t.o.v. een langere, doorlopende rotatie. Nog niet apart getest/bevestigd.

### Eindstatus: robot veilig gestopt, oriëntatie ONBEVESTIGD
- **Positie:** blijft vermoedelijk correct (x≈-1,65, y≈-0,87 — geen reden om aan te nemen dat de positie is veranderd, alleen rotatie is uitgevoerd).
- **Oriëntatie:** onzeker, ergens tussen de twee laatste, onderling tegenstrijdige metingen (yaw ≈ 89° volgens de IMU-som, ≈ 60,4° volgens AMCL — dus een verschil van ~29°). **Niet geverifieerd of de robot nu naar de deuropening kijkt.**
- Robot is fysiek gestopt en door de gebruiker bevestigd veilig.

### Concreet vertrekpunt voor de volgende sessie (vóór verder te gaan met Nav2/obstakel-vermijding)
1. **Eerst een schone, betrouwbare heroriëntatie-check** — een verse gemarkeerde-kaartafbeelding (`mark_amcl_pose.py`) om de werkelijke huidige oriëntatie vast te stellen, zonder te vertrouwen op de tegenstrijdige metingen van vanavond.
2. **Linksom-snelheid apart kalibreren** met de verplaatste IMU (zoals rechtsom al is gedaan: `rotation_calib_test.py sign=1`), vóór er weer een linksom-draai wordt gecommandeerd.
3. **`incremental_rotate.py` repareren** (`time.sleep()` i.p.v. de spin-lus) vóór hergebruik, en de efficiëntie-hypothese (korte segmenten = trager per seconde) apart valideren.
4. Pas daarna verder met de eerder geplande punten 1-3 (AMCL-initial-pose, `/pose_settling` consumeren, echte obstakel-vermijdende Nav2-test).

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
