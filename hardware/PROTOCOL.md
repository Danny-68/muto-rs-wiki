# 📡 Communicatieprotocol Referentie

---

## STM32 Baseboard Protocol (Pi → STM32)

### Packet structuur (9 bytes, vast)

```
0x55  0x00  0x09  0x01  ADDR  DATA  CHECKSUM  0x00  0xAA
 │     │     │     │     │     │       │        │     │
header2│   length  WR   adres data  checksum  tail1  tail2
      header1
```

**Checksum berekening:**
```python
checksum = (0xFF - (0x09 + 0x01 + ADDR + DATA)) & 0xFF
```

### Bewegingscommando's

| Adres | Commando | Data range | Beschrijving |
|---|---|---|---|
| 0x11 | Stop | 0x00 | Stop + poten op grond |
| 0x12 | Vooruit | 10-25 | Stapgrootte |
| 0x13 | Achteruit | 10-25 | Stapgrootte |
| 0x14 | Links schuiven | 10-25 | Stapgrootte |
| 0x15 | Rechts schuiven | 10-25 | Stapgrootte |
| 0x16 | Links roteren | 10-25 | Stapgrootte |
| 0x17 | Rechts roteren | 10-25 | Stapgrootte |

### Acties & animaties

| Adres | Commando | Data | Beschrijving |
|---|---|---|---|
| 0x3E | Performance mode | 0-8 | Zie animatietabel |
| 0x06 | Herstel standstand | 0x00 | Reset naar standing posture |

**Animatie groepen (adres 0x3E):**

| Data | Animatie |
|---|---|
| 0 | Reset / initieel |
| 1 | Stretch |
| 2 | Begroeting (greet) |
| 3 | Bang (afraid) |
| 4 | Warming-up squats |
| 5 | Draaien in cirkels |
| 6 | Zwaaien (wave) |
| 7 | Oprollen (curl up) |
| 8 | Grote pas vooruit (stride forward) |

### Hoogte aanpassing

| Adres | Data | Hoogte |
|---|---|---|
| 0x27 | 1 | Laag |
| 0x27 | 2 | Medium |
| 0x27 | 3 | Hoog |

### Servo controle (enkelvoudig)

```
0x55 0x00 0x0C 0x01 0x40 SERVO_ID ANGLE SPEED_H SPEED_L CHECKSUM 0x00 0xAA
```
- SPEED = `(SPEED_H << 8) | SPEED_L`

### Buzzer

| Adres | Data | Beschrijving |
|---|---|---|
| 0x18 | 0 | Buzzer uit |
| 0x18 | 255 | Buzzer aan (continu) |
| 0x18 | N | Buzzer N×100ms |

### IMU uitlezen

**Commando (gefuseerde hoeken):**
```
0x55 0x00 0x09 0x02 0x60 0x07 0x8D 0x00 0xAA
```

**Antwoord:**
```
bytes[9,10]  = yaw   (÷100 voor graden)
bytes[7,8]   = pitch
bytes[5,6]   = roll
byte[11]     = temperatuur
```

**IMU ruwe data:**
```
0x55 0x00 0x09 0x02 0x61 0x12 0x81 0x00 0xAA
```

### Servo hoek uitlezen

**Commando (alle 18 servo's):**
```
0x55 0x00 0x1A 0x12 0x07 [18x 0x00] CHECKSUM 0x00 0xAA
```

**Servo hoek lezen (enkelvoudig, addr 0x60):**
```python
# Antwoord: 15 bytes
# data[1] = hoek in graden (byte index 6 van response frame)
# data[0] = altijd 0xFF (status byte)
```

### Servo hardware interpolatie (executietijd)

**Register 0x2C (2 bytes):**
```python
exec_time_ms = 18  # ~18ms voor 50Hz updates
# Checksum voor 2-byte data:
checksum = (0xFF - sum(payload_bytes)) & 0xFF
```
Aanbevolen: 18ms zodat hardware interpolatie combineert met sinusoïdale easing.

---

## CSPower Servo Protocol (STM32 → Servos)

> ⚠️ Pi communiceert NIET direct met servos. Altijd via STM32 baseboard.

### Bus topologie
- **USART2:** Rechter poten (RF, RM, RR) — servo IDs 1-9
- **USART3:** Linker poten (LF, LM, LR) — servo IDs 10-18

### Tibia servo IDs
| Poot | Servo ID |
|---|---|
| RF tibia | 3 |
| RM tibia | 6 |
| RR tibia | 9 |
| LR tibia | 12 |
| LM tibia | 15 |
| LF tibia | 18 |

### Voetcontact detectie (aanpak A)
- Servo positiefout > 12° = grondcontact
- Op grond: 20-38° fout (servo geblokkeerd door grondkracht)
- In zwaaifase: 2-5° fout (alleen mechanische speling)
- ⚠️ Alleen betrouwbaar tijdens LOPENDE gait, niet bij vrijhangend testen

---

## Dify HTTP API Formaten

### Stack B: `/execute_commands` (muto_yahboom, port 8080)

**Request (JSONPlanRequest):**
```json
{
  "status": "success",
  "plan": [
    {"id": "1", "command": "forward(speed=15, duration=2)"},
    {"id": "2", "command": "stop()"}
  ]
}
```

**Beschikbare functies:**
```
forward(speed, duration)    backward(speed, duration)
shift_left(speed, duration) shift_right(speed, duration)
rotate(speed, duration)     spin_in_place(speed, duration)
stop()                      adjust_height(level)
big_stride(speed, duration) have_a_look(user_query)
get_lidar_data()            get_lidar_360_data()
get_lidar_range_at_angle(angle)
robot_speak(text, volume)   wave_no()
say_hello()                 curl_up()
stretch()                   warm_up_squat(action)
```

### Stack A: robot_bridge.py (port 5000)

| Endpoint | Method | Beschrijving |
|---|---|---|
| `/health` | GET | Systeem status |
| `/robot/forward` | POST | Vooruit (speed, duration) |
| `/robot/backward` | POST | Achteruit |
| `/robot/rotate_to_angle` | POST | IMU gesloten-lus rotatie |
| `/robot/imu` | GET | Yaw, pitch, roll |
| `/lidar/obstacle` | GET | Hindernis detectie |
| `/camera/depth/obstacle` | GET | Diepte hindernis |
| `/camera/describe` | GET | Visuele beschrijving (qwen-vl) |
