# 🔧 Hardware Referentie — Yahboom Muto RS

---

## Robot Platform

| Component | Details |
|---|---|
| Robot | Yahboom Muto RS (4ROS versie) |
| Compute | Raspberry Pi 5 |
| Baseboard | Yahboom YB-MAE02-V1.0 met STM32F103RCT6 |
| Servos | 18× CSPower 35KG bus servos |
| LiDAR | YDLidar TG30 (TOF type, firmware 2.1) |
| Camera | Orbbec Astra Pro Plus |
| IMU (extern) | Pimoroni ICM20948 |
| Audio | Soundblaster Play! 3 (USB, extern op aparte Pi poort) |

---

## Hexapod Geometrie (caliper gemeten, as-tot-as)

> ⚠️ GEBRUIK ALTIJD DEZE WAARDEN. `muto_rs_gait.txt` bevat onbetrouwbare maten.

| Segment | Waarde | Gemeten |
|---|---|---|
| Coxa (body mount → coxa servo as) | 27.5 mm | — |
| Coxa (coxa → femur as) | 50.59 mm | 52 mm |
| Femur | 72.60 mm | 73 mm |
| Tibia | 134.5 mm | 140 mm |

---

## Poot Volgorde (MutoLib)

```
Leg index:  0=RF  1=RM  2=RR  3=LR  4=LM  5=LF
                                    ⚠️ 4 en 5 zijn FYSIEK OMGEKEERD
```

| Index | Naam | Mount hoek |
|---|---|---|
| 0 | Right Front (RF) | -45° |
| 1 | Right Middle (RM) | 0° |
| 2 | Right Rear (RR) | 45° |
| 3 | Left Rear (LR) | 135° |
| 4 | Left Middle (LM) ⚠️ | 180° |
| 5 | Left Front (LF) ⚠️ | 225° |

**Tibia servo IDs** voor voetcontact detectie: 3, 6, 9, 12, 15, 18 (RF→RR→LR→LF)

---

## USB Apparaten & udev Mappings

### Permanente symlinks (via udev)

| Symlink | Target | Apparaat | Vendor ID |
|---|---|---|---|
| `/dev/myserial` | ttyUSB0 | STM32 CH340 | 1a86:7523 |
| `/dev/mylidar` | ttyUSB1 | YDLidar CP210x | 10c4:ea60 |

### Tijdelijke symlink (elke reboot opnieuw)
```bash
sudo ln -sf /dev/mylidar /dev/rplidar
```

### Orbbec Astra Pro Plus udev fix
Bestand: `/etc/udev/rules.d/56-orbbec-usb.rules`
- Unbindt `uvcvideo` (pid 050f)
- Unbindt `snd-usb-audio` (pid 060f)

### Soundblaster Play! 3
- USB ID: `041e:324d`
- Aangesloten op aparte Pi USB poort (NIET de Yahboom expansion hub)
- Reden: interne hub heeft battery-voltage powerbudget conflict met camera

---

## I2C Bus Configuratie

| Bus | Apparaat | Adres | GPIO SDA | GPIO SCL |
|---|---|---|---|---|
| I2C bus 1 | LCD display | 0x3C | pin 3 | pin 5 |
| I2C bus 4 | ICM20948 IMU | 0x68 | pin 8 (GPIO14) | pin 10 (GPIO15) |

**Config in** `/boot/firmware/config.txt`:
```
dtoverlay=i2c-gpio,bus=4,i2c_gpio_sda=14,i2c_gpio_scl=15
```

**Verificatie:**
```bash
i2cdetect -y 4   # Moet 0x68 tonen
# WHO_AM_I check vanuit container:
docker exec humble_run python3 -c "
import smbus2; b=smbus2.SMBus(4)
print(hex(b.read_byte_data(0x68,0x00)))  # Verwacht: 0xEA
"
```

---

## YDLidar TG30 Configuratie

```yaml
# ydlidar.yaml — kritieke instellingen
port: /dev/mylidar
baudrate: 512000
lidar_type: 0          # TYPE_TOF (NIET TYPE_TRIANGLE=1)
reversion: false       # true → 180° roterende scan!
frame_id: laser_frame
```

**Altijd voor herstart:**
```bash
pkill -9 -f ydlidar    # Meerdere instanties → kaart chaos
```

---

## TF Waarden (definitief vastgesteld)

| Frame | x (m) | y | z (m) | roll | pitch | yaw |
|---|---|---|---|---|---|---|
| laser_frame | -0.04 | 0 | 0.24 | 0 | 0 | **0** |
| camera_link | 0.06 | 0 | 0.225 | 0 | 0.1047 rad (6°) | 0 |
| imu_link | 0 | 0 | 0 | 0 | 0 | 0 |

> ⚠️ laser yaw=0 is DEFINITIEF. Niet 1.5708 of -1.5708.

---

## Jetson Orin Nano Super

| Spec | Waarde |
|---|---|
| Model | P3766 (945-13766-0000-000) |
| RAM | 8GB LPDDR5 |
| GPU | 1024 Ampere CUDA cores |
| AI Performance | 67 TOPS (MAXN mode) |
| Formaat | 148×100mm (past NIET op chassis) |
| Voeding | 19V extern |
| IP adres | 192.168.68.86 |
| Jetpack | 6.1 rev 1 |
| Container | `jetson_run` |
| Home directory | `/home/Danny` (hoofdletter D!) |

**Niet mogelijk op chassis** → vaste externe co-processor via WiFi.

---

## Snelheidstabel (gemeten, vlakke ondergrond)

| Step waarde | Snelheid (m/s) |
|---|---|
| 10 | 0.027 |
| 15 | 0.061 |
| 18 | 0.069 |
| 20 | 0.096 |
| 25 | 0.125 |

`resolve_duration()` gebruikt lineaire interpolatie. 1 stap = 10cm (Yahboom aanpak).
