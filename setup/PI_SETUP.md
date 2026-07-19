# 🐧 Raspberry Pi 5 — From Scratch Setup

---

## Systeem specificaties (productie)

| Component | Waarde |
|---|---|
| OS | Debian GNU/Linux 12 (Bookworm) |
| Kernel | 6.12.93+rpt-rpi-2712 |
| Docker image | `ros2-humble-final:3.2.0` |
| Gebruiker | `pi` |
| Hostname | `raspberrypi` |
| IP | `192.168.68.88` |

---

## Stap 1 — OS installatie

**Raspberry Pi Imager** → Raspberry Pi OS Lite (64-bit, Bookworm)

Instellingen:
- Hostname: `raspberrypi`
- Gebruiker: `pi`
- SSH inschakelen
- WiFi configureren

---

## Stap 2 — Basis systeem

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y \
  git curl wget nano htop \
  python3-pip python3-serial python3-smbus \
  i2c-tools usbutils \
  docker.io \
  alsa-utils

sudo usermod -aG docker pi
newgrp docker
```

---

## Stap 3 — I2C bus 4 voor IMU (ICM20948)

Voeg toe aan `/boot/firmware/config.txt`:
```
dtoverlay=i2c-gpio,bus=4,i2c_gpio_sda=14,i2c_gpio_scl=15
```

Na reboot verificeren:
```bash
i2cdetect -y 4   # → moet 0x68 tonen (ICM20948)
i2cdetect -y 1   # → moet 0x3C tonen (LCD display)
```

---

## Stap 4 — udev regels

### `/etc/udev/rules.d/99-usb-serial.rules`
```
# STM32 baseboard (CH340) → /dev/myserial
SUBSYSTEM=="tty", KERNELS=="3-1.3", ATTRS{idVendor}=="1a86", ATTRS{idProduct}=="7523", SYMLINK+="myserial", MODE="0666"

# YDLidar TG30 (CP210x) → /dev/mylidar
SUBSYSTEM=="tty", KERNELS=="1-1", ATTRS{idVendor}=="10c4", ATTRS{idProduct}=="ea60", SYMLINK+="mylidar", MODE="0666"
```

> ⚠️ KERNELS waarden zijn USB-poort-specifiek. Controleer met:
> `udevadm info -a -n /dev/ttyUSB0 | grep KERNELS`

Zie `setup/udev/` voor exacte bestanden.

### Orbbec camera fix → zie `setup/udev/56-orbbec-usb.rules`

```bash
sudo udevadm control --reload-rules && sudo udevadm trigger
ls -la /dev/myserial /dev/mylidar   # Moeten bestaan
```

---

## Stap 5 — Yahboom software

```bash
# Kloon Yahboom repository
git clone https://github.com/YahboomTechnology/Muto-RS.git /home/pi/yahboomcar_ros2_ws
# Volg installatiegids op: yahboom.net/study/Muto-RS
```

Na installatie bevestigd aanwezig:
```
/home/pi/yahboomcar_ros2_ws/software/library_ws_humble/install/   ← ROS2 packages
/home/pi/yahboomcar_ros2_ws/software/MutoLib/                     ← Python servo lib
```

---

## Stap 6 — Docker container (humble_run)

```bash
docker pull yahboom/ros2-humble-final:3.2.0

docker run -d \
  --name humble_run \
  --net=host \
  --privileged \
  -v /home/pi/yahboomcar_ros2_ws:/root/yahboomcar_ros2_ws \
  -v /dev:/dev \
  --restart unless-stopped \
  yahboom/ros2-humble-final:3.2.0 \
  bash -c "while true; do sleep 3600; done"
```

### ROS2 packages in container (bevestigd aanwezig)
Nav2 volledig (amcl t/m waypoint_follower), rtabmap volledig (slam, sync, odom, viz),
robot_localization, tf2 volledig, image_transport + compressed, cv_bridge

### pip packages in container (bevestigd)
```
fastapi==0.122.0   icm20948==1.0.0   pyserial==3.5
smbus2==0.6.1      uvicorn==0.38.0
```

Extra installeren indien nodig:
```bash
docker exec humble_run pip3 install \
  fastapi==0.122.0 uvicorn==0.38.0 \
  icm20948==1.0.0 smbus2==0.6.1 pyserial==3.5
```

---

## Stap 7 — Eigen scripts deployen

```bash
# Pi host scripts
cp software/pi/scripts/*.sh /home/pi/ && chmod +x /home/pi/*.sh
cp software/pi/config/* /home/pi/

# Scripts naar container
for f in muto_driver_fixed.py sensor_relay.py scan_timestamped.py \
          odom_publisher.py imu_publisher.py; do
  docker cp software/pi/ros2/$f humble_run:/root/
done
for f in phoenix_gait.py centipede_gait.py foot_contact.py; do
  docker cp software/pi/gait/$f humble_run:/root/
done
docker cp software/container/config/hexapod_nav_params.yaml \
  humble_run:/root/hexapod_nav_params_custom.yaml
docker cp software/container/config/rtabmap_params.yaml humble_run:/root/
docker cp software/container/config/cyclone_dds.xml    humble_run:/root/
docker cp software/container/config/ekf_config.yaml    humble_run:/root/
```

---

## Stap 8 — Environment variabelen

```bash
echo 'export ROS_DOMAIN_ID=0' >> ~/.bashrc
echo 'export CYCLONEDDS_URI=/home/pi/cyclone_dds.xml' >> ~/.bashrc
source ~/.bashrc
```

---

## Stap 9 — Verificatie

```bash
ls -la /dev/myserial /dev/mylidar          # udev OK
i2cdetect -y 4 | grep 68                  # IMU OK
docker ps | grep humble_run               # Container OK
docker exec humble_run bash -c \
  "source /opt/ros/humble/setup.bash && ros2 topic list" # ROS2 OK
```

---

## Volledig systeem starten

```bash
sudo bash /home/pi/muto_rtabmap_start.sh
```
