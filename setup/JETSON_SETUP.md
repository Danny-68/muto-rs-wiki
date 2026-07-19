# 🤖 Jetson Orin Nano Super — From Scratch Setup

Volledige instructie voor de Jetson als externe GPU co-processor.

---

## Hardware

- Jetson Orin Nano Super Developer Kit (P3766, 8GB LPDDR5)
- NVMe SSD (aanbevolen: 256GB+)
- 19V voeding (meegeleverd of compatibel)
- Ethernet of WiFi voor LAN verbinding met Pi

**Vaste IP:** `192.168.68.86`
**Gebruiker:** `Danny` (hoofdletter D)
**Hostnaam:** `localhost`

---

## Stap 1 — JetPack flashen

> ⚠️ Gebruik JetPack **6.1 rev 1** — NIET 7.x (incompatibel met huidige packages)

### Vereisten (op Ubuntu host PC)
```bash
# NVIDIA SDK Manager installeren
# Download van: https://developer.nvidia.com/sdk-manager
sudo dpkg -i sdkmanager_*.deb
sdkmanager
```

### Flashprocedure
1. Sluit Jetson aan via USB-C op host PC
2. Zet Jetson in **recovery mode**: houd RECOVERY knop ingedrukt, druk RESET
3. Open SDK Manager → selecteer JetPack 6.1 rev 1
4. Selecteer target: Jetson Orin Nano Super (8GB)
5. Selecteer NVMe SSD als flash target
6. Flash + installeer alle componenten

---

## Stap 2 — Basis configuratie

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y \
  git curl wget nano htop \
  python3-pip \
  i2c-tools

# Vaste IP instellen (via NetworkManager of netplan)
# WiFi configureren zodat Jetson altijd op 192.168.68.86 zit
```

---

## Stap 3 — Docker met NVIDIA runtime

```bash
# Docker installeren
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker Danny

# NVIDIA container runtime (zit al in JetPack 6.x)
# Verificeer:
sudo docker run --rm --runtime=nvidia nvcr.io/nvidia/cuda:11.4-base nvidia-smi
```

---

## Stap 4 — Docker image bouwen

```bash
# Maak Dockerfile (opslaan als ~/Dockerfile.jetson)
cat > ~/Dockerfile.jetson << 'EOF'
FROM nvcr.io/nvidia/l4t-base:r36.2.0

RUN apt-get update && apt-get install -y \
    locales curl gnupg2 lsb-release \
    && locale-gen en_US en_US.UTF-8

# ROS2 Humble
RUN curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key \
    -o /usr/share/keyrings/ros-archive-keyring.gpg
RUN echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] \
    http://packages.ros.org/ros2/ubuntu $(lsb_release -cs) main" \
    > /etc/apt/sources.list.d/ros2.list

RUN apt-get update && apt-get install -y \
    ros-humble-desktop \
    ros-humble-nav2-bringup \
    ros-humble-rtabmap-ros \
    ros-humble-robot-localization \
    python3-pip

# rf2o
RUN pip3 install rf2o-laser-odometry 2>/dev/null || true

SHELL ["/bin/bash", "-c"]
RUN echo "source /opt/ros/humble/setup.bash" >> ~/.bashrc
CMD ["bash", "-c", "while true; do sleep 3600; done"]
EOF

docker build -f ~/Dockerfile.jetson -t muto-humble-jetson:1.0 .
```

---

## Stap 5 — Container starten

```bash
sudo docker run -d \
  --name jetson_run \
  --runtime=nvidia \
  --net=host \
  --privileged \
  -v /home/Danny:/home/Danny \
  -e NVIDIA_VISIBLE_DEVICES=all \
  -e NVIDIA_DRIVER_CAPABILITIES=all \
  -e ROS_DOMAIN_ID=0 \
  -e CYCLONEDDS_URI=/home/Danny/cyclone_dds.xml \
  --restart unless-stopped \
  muto-humble-jetson:1.0

# Autostart bij boot
sudo docker update --restart unless-stopped jetson_run
```

---

## Stap 6 — Config bestanden

```bash
# CycloneDDS unicast config
cp software/jetson/config/cyclone_dds.xml /home/Danny/
cp software/jetson/config/ekf_config.yaml /home/Danny/

# RTAB-Map params in container
docker cp software/jetson/container/config/rtabmap_params.yaml jetson_run:/root/
```

---

## Stap 7 — SSH key naar Pi (voor Jetson→Pi communicatie)

```bash
sudo ssh-keygen -t ed25519 -f /root/.ssh/id_ed25519 -N ""
sudo ssh-copy-id pi@192.168.68.88
# Verificeer: sudo ssh pi@192.168.68.88 echo OK
```

---

## Stap 8 — Opstartscript

```bash
cp software/jetson/scripts/muto_jetson_start.sh /home/Danny/
chmod +x /home/Danny/muto_jetson_start.sh
```

---

## Stap 9 — Verificatie DDS verbinding

Op Pi én Jetson tegelijk:
```bash
# Pi:
docker exec humble_run bash -c "source /opt/ros/humble/setup.bash && ros2 topic list"

# Jetson:
sudo docker exec jetson_run bash -c "source /opt/ros/humble/setup.bash && ros2 topic list"
# Moet Pi topics zien (zoals /scan, /odom)
```

---

## TF publishers op Jetson starten

```bash
# Laser TF (yaw=0 DEFINITIEF)
docker exec -d jetson_run bash -c "source /opt/ros/humble/setup.bash && \
  ros2 run tf2_ros static_transform_publisher -0.04 0 0.24 0 0 0 base_link laser_frame"

# Camera TF (pitch=0.1047rad = 6°)
docker exec -d jetson_run bash -c "source /opt/ros/humble/setup.bash && \
  ros2 run tf2_ros static_transform_publisher 0.06 0 0.225 0 0.1047 0 base_link camera_link"

# IMU TF
docker exec -d jetson_run bash -c "source /opt/ros/humble/setup.bash && \
  ros2 run tf2_ros static_transform_publisher 0 0 0 0 0 0 base_link imu_link"
```

---

## RTAB-Map op Jetson starten

```bash
sudo bash /home/Danny/muto_jetson_start.sh
```

Of handmatig:
```bash
docker exec -d jetson_run bash -c "
  source /opt/ros/humble/setup.bash && \
  ros2 run rtabmap_slam rtabmap \
    --ros-args \
    --params-file /root/rtabmap_params.yaml \
    --remap scan:=/scan_fixed \
    --remap odom:=/odom \
    --remap rgbd_image:=/rgbd_image \
    > /tmp/rtabmap.log 2>&1"
```
