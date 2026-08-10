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
| `phoenix_gait.py` | `/root/phoenix_gait.py` (container) | Tripod + Centipede gait |
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
