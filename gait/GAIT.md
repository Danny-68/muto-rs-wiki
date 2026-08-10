# 🦿 Gait Ontwikkeling — Yahboom Muto RS

---

## Architectuurprincipes

### Twee-laags communicatie (KRITIEK)
```
Pi → STM32 baseboard protocol → CSPower servo protocol
Pi communiceert NOOIT direct met servos
Enige correcte servo interface: Leg.move_tip(point3d)
```

### STM32 gait commands zijn incompatibel met move_tip()
Wanneer een Yahboom STM32 gait command (0x12-0x17) wordt gestuurd, worden **alle** servo posities gereset naar interne neutrale stand. Gevolg: simultaan body-yaw scannen en fysiek draaien is onmogelijk.

Correcte volgorde voor body-yaw + draaien:
1. Stretch naar doelhoek
2. Rubber snap back naar 0°
3. Yahboom STM32 draaien

---

## Phoenix Gait Engine (`phoenix_gait.py`)

**Inspiratie:** Zenta/Xan/KurtE Phoenix hexapod gait engine

### Gaittypes

| Type | Beschrijving | Swing fractie | Periode |
|---|---|---|---|
| Tripod | 2 groepen afwisselend | 0.50 | 1.0s |
| Ripple | 3 groepen ronde | 0.33 | 1.5s |
| Wave | 6 poten sequentieel | 0.17 | 2.5s |
| Centipede | Metachronal golf achter→voor | 0.17 | 2.5s |

### Continue fase model

```python
# Fase φ ∈ [0,1) loopt continu op 50Hz
# Sinusoïdale easing voor organische beweging:
ease = 0.5 - 0.5 * cos(π * t)  # t ∈ [0,1]
```

### Biologische bewegingsverbeteringen

1. **Body dip:** `body_dip_z = -D · sin(π · t_swing)` — neerwaartse beweging tijdens swing
2. **Snelheidsafhankelijke lift:** `eff_lift = h_lift · max(f_min, v_current/v_target)`
3. **Versnelling/vertraging:** lineaire ramp 20-30 mm/s², exponentieel decay α=0.85
4. **Body sway:** `body_sway_x = ±S · sin(π · t_swing)` — zwaai naar stance zijde

### Servo hardware interpolatie

```python
exec_time_ms = 18  # 18ms ≈ één 50Hz frame
# Stel in via STM32 register 0x2C
# Combineert met sinusoïdale easing voor maximale vloeiendheid
# Gelijk aan Yahboom built-in gait kwaliteit
```

---

## Centipede Wave Gait

### Poot offset volgorde
```python
# Metachronal golf: achter → voor
# ⚠️ Indices 4 en 5 zijn OMGEKEERD
leg_offsets = [4/6, 2/6, 0/6, 1/6, 5/6, 3/6]
#              RF    RM    RR    LR    LM    LF
```

### Bewezen werkend op hardware
- `swing_frac = 0.17` (1/6 van periode)
- `period = 2.5s`
- `step = 30mm`

---

## Rubber Band Effect (body-yaw scan)

**Formule (onderdempte harmonische oscillator):**
```
x(t) = from_deg · e^(-ζωt) · [cos(ω_d·t) + (ζ/√(1-ζ²))·sin(ω_d·t)]
```

**Parameters:**
```python
SNAP_OMEGA = 18.0   # Veersterkte
SNAP_ZETA  = 0.45   # Demping
# Geeft ~20% overshoot
```

Uitvoerend op 50Hz, bevestigd goed werkend.

---

## Camera Scan Gait

**Gelijktijdige body-yaw + body-pitch:**
- Z-as yaw eerst, dan X-as pitch
- Beide assen bewegen simultaan
- Snelheid: `YAW_RATE=12.0°/s`, `PITCH_RATE=6.0°/s`

---

## IMU Yaw Correctie

```python
# Baseboard command voor IMU hoeken
cmd = bytes([0x55, 0x00, 0x09, 0x02, 0x60, 0x07, 0x8D, 0x00, 0xAA])

# Antwoord parsing
yaw_raw = (response[9] << 8) | response[10]
yaw_deg = yaw_raw / 100.0

# Tijdens testen: robot houdt yaw binnen ±0.5°
```

---

## Bestandslocaties

| Bestand | Locatie | Beschrijving |
|---|---|---|
| `phoenix_gait.py` | `/root/phoenix_gait.py` (container) | Tripod + Ripple + Wave + Centipede gait (centipede-offsets ongevalideerd sinds 10 aug reconstructie) |
| `phoenix_driver.py` | `/root/phoenix_driver.py` (container), bron `/home/pi/` | Nav2-bewegingsbackend op basis van PhoenixGait, nog niet in de Nav2-launch-keten gehaakt |
| `phoenix_yaw_drift_test.py` | `/root/phoenix_yaw_drift_test.py` (container) | Yaw-drift-test via directe phoenix_gait-aanroepen |
| `rotation_calib_test.py` | `/root/rotation_calib_test.py` (container), bron `/home/pi/` | Rotatie-kalibratietest via `cmd_vel`/`/imu` (gebruikt voor `MAX_ANGULAR_SPEED_RADPS`) |
| `forward_drift_via_node_test.py` | `/root/forward_drift_via_node_test.py` (container), bron `/home/pi/` | Yaw-drift-test via `phoenix_driver.py`/`cmd_vel` i.p.v. directe aanroepen |
| `centipede_gait.py` | `/root/centipede_gait.py` | Standalone centipede |
| `foot_contact.py` | `/home/pi/foot_contact.py` | Voetcontact detectie |
| `muto_controller.py` | `/home/pi/muto_controller.py` | Joystick controller |

---

## Joystick Controller

**Bestand:** `/home/pi/muto_controller.py` (Pi host, NIET in container)

- Auto-kill `app_muto.py` bij start, herstart bij exit
- Behoudt alle originele bediening
- Scan modus via `BTN_RK2` (rechter stick klik)
- Joystick queue volledig draineren per frame (loop tot `select` niets teruggeeft)

---

## Voetcontact Detectie (`foot_contact.py`)

### Aanpak A: Servo positie fout

```python
# Lees tibia servo hoek
cmd = bytes([0x55, 0x00, 0x09, 0x02, 0x60, servo_id, CHECKSUM, 0x00, 0xAA])
# Antwoord: byte index 6 = hoek in graden (byte index 0 = 0xFF status)

CONTACT_THRESHOLD = 12  # graden
# Op grond: 20-38° fout
# In zwaaifase: 2-5° fout

# Retry mechanisme: 3 pogingen met toenemende delays
# (STM32 auto-packets vervuilen serial buffer)
```

### Integratie status
- `foot_contact.py` klaar op Pi
- Nog te integreren in `muto_driver_fixed.py` als ROS2 node
- Publiceert `/foot_contact` topic

### Aanpak B (niet geïmplementeerd): IMU vibratie detectie
### Aanpak C (niet geïmplementeerd): SH-U09B3 USB-UART direct op servo bus

---

## Yahboom Firmware Verzoeken (verstuurd, geen reactie)

### Verzoek 1: Servo stroom uitlezen (0x51)
- Doel: Contactdetectie via servo stroom (register 0x2E in CSPower protocol)
- Status: Verstuurd naar Yahboom, geen reactie ontvangen

### Verzoek 2: Velocity Twist Command (0x18)
- Parameters: Vx, Vy, Wz (signed 16-bit)
- Doel: Arc locomotie, directe Twist-naar-gait integratie
- Status: Verstuurd, geen reactie

### Servo executietijd truc (zelf ontdekt)
Yahboom bereikt hun vloeiende gait kwaliteit via servo hardware interpolatie (register 0x2C/0x2D, ~18ms executietijd). Dit combineert met software sinusoïdale easing voor optimale bewegingskwaliteit — als vervanging voor de ontbrekende firmware features.


---

## Sessie 10 augustus 2026 — Regressie gevonden en gefixt

### Regressie t.o.v. eerder werkende versie

Het bestand `/home/pi/phoenix_gait.py` (d.d. 8 juli, 7917 bytes) bleek een
terugval te zijn t.o.v. de eerder werkende versie eind juni. Ontbrekend:
continu fasemodel, sinusoidale easing op horizontale beweging,
centipede-gait, body dip / snelheidsafhankelijke lift / accel-decel,
servo hardware-interpolatie. Reconstructie uitgevoerd op basis van
projectgeschiedenis; centipede leg-offsets gebruiken de eerder
gedocumenteerde `[4/6, 2/6, 0/6, 1/6, 5/6, 3/6]` reeks (nog te bevestigen
op hardware in deze reconstructie).

### Rootcause: `_foot_delta` gebruikte mount-hoek i.p.v. wereldrichting

**Symptoom:** robot bleef op de plaats staan tijdens tripod-gait — poten
bewogen zichtbaar (lift, heen-en-weer) maar het lichaam verplaatste niet.

**Oorzaak:** de translatierichting (`tx`, `tz`) werd per poot geroteerd
met de mount-hoek van die poot (`MOUNT_RAD[leg]`):

```python
# FOUT — elke poot duwt radiaal t.o.v. eigen mount-hoek i.p.v. één
# gezamenlijke wereldrichting. Netto lichaamsverplaatsing ~0.
def _foot_delta(self, leg, gait, tx, tz, rot):
    angle = MOUNT_RAD[leg]
    dx = gait.step_length * tx * math.cos(angle)
    dy = gait.step_length * tx * math.sin(angle)
    dx += gait.step_length * tz *  math.sin(angle)
    dy += gait.step_length * tz * -math.cos(angle)
    ...
```

De rotatie-component (`rx, ry`) was wel correct — die gebruikt bewust
`nx, ny` (pootpositie) voor tangentiële beweging bij het draaien.

**Fix:** translatie loskoppelen van mount-hoek, vaste wereldrichting
voor alle poten (coordinatensysteem: +x=rechts, +y=voorwaarts):

```python
def _foot_delta(self, leg, gait, tx, tz, rot):
    nx, ny, _ = NEUTRAL_POS[leg]
    dx = gait.step_length * tz
    dy = gait.step_length * tx
    rot_scale = gait.step_length * 0.6
    rx = -ny * rot * rot_scale / max(math.hypot(nx, ny), 1)
    ry =  nx * rot * rot_scale / max(math.hypot(nx, ny), 1)
    return (dx + rx, dy + ry)
```

**Resultaat:** bevestigd op hardware — vloeiende voorwaartse beweging
met tripod-gait + sway. Backup van pre-fix bestand: `phoenix_gait.py.bak`
op de Pi.

### Testresultaten deze sessie

| Gait | Status | Opmerking |
|---|---|---|
| neutral | werkt | geen bewegingsindicatie mogelijk (kan vals-positief zijn als robot al neutraal staat) |
| one_leg | werkt | been 0 (RF) soepele op/neer beweging |
| tripod + sway | **werkt, bevestigd vloeiende voorwaartse loop** | na `_foot_delta`-fix |
| ripple | nog niet getest | |
| wave | nog niet getest | |
| centipede | nog niet getest | leg-offsets ongevalideerd sinds reconstructie |
| `--dip` (body dip) | nog niet expliciet getest | |

### Bekend openstaand gat in reconstructie

`eff_lift_scale` (snelheidsafhankelijke lift) wordt in `foot_targets()`
berekend maar nergens toegepast op `gait.lift_height` — dit is een
onafgemaakt onderdeel van de reconstructie, geen nieuwe regressie.


---

## Yaw-drift meting phoenix_gait.py tripod (10 augustus 2026)

Methodologie: schone karakterisering, geen auto-correctie, handmatig
heading-reset + terugkeer naar startpunt tussen reps (mirrort de
STM32-gait yaw-drift tests). Vloeiende stop-sequentie: decel binnen de
gait (target_speed → 0, laatste stap remt uit i.p.v. abrupt te stoppen
midden-swing) gevolgd door sinusoidale interpolatie naar NEUTRAL_POS —
geen instant snap meer.

### Kalibratie afstand

step_length=60mm in de GaitParams suggereert ~60mm/cyclus, maar gemeten
resultaat is ~9.5cm/cyclus (76cm over 8 cycli) — sway+dip zorgen
kennelijk voor meer effectieve voortgang per cyclus dan de kale
step_length-parameter alleen. **5.3 cycli ≈ 50cm**, empirisch bevestigd
(meerdere reps kwamen uit op 50-52cm).

### Resultaten (tripod-gait, 5.3 cycli ≈ 50cm, sway=aan)

| Richting | Reps | Individuele drift | Gemiddelde | Std.dev |
|---|---|---|---|---|
| Vooruit | n=3 | +3.04°, +2.82°, +2.54° | **+2.80°** | ~0.25° |
| Achteruit | n=3 | -1.38°, -1.78°, -0.92° | **-1.36°** | ~0.43° |

(één meetartefact genegeerd: een rep gaf yaw_before=217.6° en een
volgende rep crashte op een lege IMU-read — beide toegeschreven aan een
serieel-poort-conflict met `app_muto.py`, dat op dat moment nog niet was
gestopt. Zie "Bekende valkuil" hieronder.)

**Interpretatie:** fors beter dan de STM32-firmware-gait (0x12-0x17),
die -8° tot -16° vooruit en +2.8°/+4.7° achteruit gaf over vergelijkbare
afstand (zie PROBLEMS.md, sectie Rotatie & precisiebeweging). Zelfde
asymmetrie-patroon (tegengesteld teken vooruit/achteruit) als bij de
firmware-gait — wijst op een structureel verschil in pootbelasting
tussen voor- en achterwaartse tripod-cyclus, niet toevallig. Kwalitatief
bevestigd: bij achteruit lopen kwam de robot precies op de oorspronkelijke
startpositie uit.

**Kanttekening:** n=3 per richting is een eerste indicatie, geen
definitieve validatie — zelfde niveau van voorzichtigheid als bij de
vroege STM32-metingen aanhouden voordat dit als vaststaand feit wordt
behandeld.

### Bekende valkuil: serieel-poort-conflict met app_muto.py

`phoenix_gait.py` (en scripts die het importeren, zoals
`phoenix_yaw_drift_test.py`) openen `/dev/myserial` direct. Als
`app_muto.py` nog draait (autostart na koude boot), corrumpeert dat de
serial-buffer — symptoom: absurde yaw-sprongen (bijv. 217.6°) of lege
IMU-reads. **Altijd `pkill -f app_muto.py` vooraf**, net als bij Nav2 en
`robot_bridge.py`.

### Testscript

`/root/phoenix_yaw_drift_test.py` (in `humble_run` container) —
herbruikbaar voor andere gaits/afstanden via `--direction`, `--cycles`,
`--reps`. Bevat retry-mechanisme op IMU-read (3 pogingen, oplopende
delay, zelfde patroon als `foot_contact.py`) en de vloeiende
stop-sequentie hierboven.

---

## Nav2-integratie: `phoenix_driver.py` (10 augustus 2026, vervolgsessie)

Doel: `phoenix_gait.py`'s tripod-gait als bewegingsbackend voor Nav2 gebruiken
i.p.v. de STM32-firmware-gait (0x12-0x17) die `muto_driver_fixed.py` aanstuurt.
`muto_driver_fixed.py` en de STM32-gait-code blijven intact als terugvaloptie
— dit is een apart, zelfstandig te starten/stoppen bestand.

### Ontwerp

- Nieuw bestand: `phoenix_driver.py` (host: `/home/pi/`, container: `/root/`)
- Abonneert op `cmd_vel` — **niet** `cmd_vel_nav` zoals aanvankelijk gedacht.
  `muto_driver_fixed.py` luistert zelf ook naar `cmd_vel`; Nav2 publiceert naar
  `cmd_vel_nav` en een bestaande relay (`ros2 run topic_tools relay
  /cmd_vel_nav /cmd_vel`) zet dat om. `phoenix_driver.py` volgt hetzelfde
  patroon, dus geen wijziging nodig in de rest van de Nav2-stack.
- Uitsluitend tripod-gait (`GAITS['tripod']`), met sway+dip aan — de enige
  eerder gevalideerde configuratie.
- `linear.x` → `travel_x`, `angular.z` → `rotate`, continu bijgewerkt in de
  fase-loop (geen losse start/stop-commando's).
- Timeout op **5,0s** (bewuste keuze: matcht de huidige live waarde in
  `muto_driver_fixed.py`, niet de aanvankelijk voorgestelde 0,5s).
- Vloeiende stop-sequentie (decel + sinusoidale interpolatie naar
  `NEUTRAL_POS`, zelfde patroon als `stable_stop()` in
  `phoenix_yaw_drift_test.py`) wordt aangeroepen bij **zowel** een expliciete
  cmd_vel=0 **als** een timeout — bij alleen timeout blijft de robot anders
  "marcheren op de plek" na een normale Nav2-stop (lift/sway-animatie stopt
  niet vanzelf enkel omdat travel_x/rotate naar 0 gaan).
- Geen eigen IMU-publicatie nodig: de EKF gebruikt `imu0: /imu` (extern,
  ICM20948 via `imu_publisher.py`, losstaand proces) — niet `/imu_stm32` van
  `muto_driver_fixed.py`. `phoenix_driver.py` hoeft dus geen IMU-code te
  bevatten; `imu_publisher.py` blijft gewoon naast draaien.
- `_stop_app_muto()` in het bestand is **niet effectief** wanneer het in de
  container draait: de container deelt geen PID-namespace met de host, dus
  `pgrep`/`pkill` binnen de container ziet het host-proces `app_muto.py` niet
  (bevestigd getest, `PidMode` staat niet op `host`). `/dev/myserial` zelf is
  wél gedeeld (bind-mount), dus het conflict zou zich alsnog voordoen zonder
  dat de ingebouwde beveiliging het merkt. **Voor nu:** `app_muto.py` moet
  vanaf de host gestopt worden vóór `phoenix_driver.py` in de container start
  — dezelfde volgorde als alle bestaande opstartscripts al gebruiken. Zodra
  dit in een host-side opstartscript gehaakt wordt (Nav2-launch-integratie,
  nog te doen), hoort die stap daar te staan, niet in het container-side
  Python-bestand.

### Kalibratie: `MAX_ANGULAR_SPEED_RADPS` fout geraden, gecorrigeerd

Eerste versie gokte `0.5 rad/s` (geen meting beschikbaar). Live rotatietest
met `angular.z=0.15` (genormaliseerd `rotate=0.3`) gaf een resultaat dat een
gebruiker visueel inschatte als "geen rotatie" — vervolgtest op `angular.z=0.45`
(rotate=0.9) werd visueel geschat op "~40 graden". Precieze IMU-meting
(`/imu`, extern) via een los kalibratiescript gaf een heel ander beeld:

| test | commando | gemeten rotatie |
|---|---|---|
| 1 | angular.z=0.45, 2.0s | +5.14° |
| 2 (herhaling) | angular.z=0.45, 2.0s | +4.66° |
| 3 | angular.z=1.0, 5.0s | +15.24° |

Consistent, reproduceerbaar (tests 1-2), en veel lager dan de visuele "~40°"-
inschatting van test 2 — **de visuele schatting was fors overschat**, niet de
meting fout (mechanisme gaf hetzelfde resultaat bij herhaling). Werkelijke
volle-snelheid draaisnelheid: ~3.0-3.3°/s ≈ **0.055 rad/s**, ongeveer 9× lager
dan de oorspronkelijke gok. `MAX_ANGULAR_SPEED_RADPS` bijgewerkt naar `0.055`.
**Les:** bij een zwaaiende hexapod-gait is een visuele hoek-inschatting
onbetrouwbaar — vertrouw de IMU, ook als het resultaat verrassend klein is.

### Test resultaten (standalone, buiten Nav2, via `ros2 topic pub`/testscripts)

| Test | Resultaat |
|---|---|
| Start/stop naar neutraal | ✅ vloeiend, bevestigd door gebruiker |
| Voorwaartse beweging | ✅ vloeiend, juiste richting |
| Expliciete stop (cmd_vel=0) | ✅ vloeiend, 2× herhaald, geen timeout nodig |
| Timeout-stop (5.0s) | ✅ vloeiend, correct getriggerd |
| Rotatie | ✅ mechaniek werkt correct (na kalibratiefix) |

**Yaw-drift via de node (`cmd_vel`/ROS2), 5.3 cycli ≈ 50cm, vergeleken met de
directe-aanroep-baseline (zie sectie hierboven):**

| Richting | Via node (n) | Gemiddelde | Baseline (direct, n=3) |
|---|---|---|---|
| Vooruit | +1.02°, +1.27°, +1.62° (n=3) | **+1.30°** | +2.80° |
| Achteruit | -2.33°, -1.47° (n=2) | **-1.90°** | -1.36° |

Zelfde asymmetrie-patroon (vooruit positief, achteruit negatief) als de
baseline, vergelijkbare orde van grootte. **Conclusie:** geen aanwijzing dat
de ROS2/cmd_vel-integratielaag zelf een nieuwe driftbron toevoegt — de
afwijkingen die er zijn komen overeen met de al bekende gait-karakteristiek.
n=2/3 blijft een eerste indicatie, zelfde voorzichtigheid als bij de
oorspronkelijke meting aanhouden.

### Nog openstaand

1. Meer herhalingen voor statistische zekerheid (met name achteruit, nu n=2)
2. Nav2-launch-keten aanpassen: `phoenix_driver.py` i.p.v.
   `muto_driver_fixed.py` starten in `muto_fase1_start.sh` (of vergelijkbaar),
   inclusief het `app_muto.py`-stopprobleem hierboven correct oplossen op
   host-niveau
3. Lifecycle-status-check van alle Nav2-nodes (amcl, controller_server,
   planner_server, bt_navigator, map_server) vóór een eerste begeleide
   Nav2-navigatietest — `ros2 node list` bewijst niet dat een node actief is,
   gebruik `ros2 lifecycle get`
4. Een korte, begeleide Nav2-navigatietest op bekende, obstakelvrije
   ondergrond
