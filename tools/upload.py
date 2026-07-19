import base64,json,urllib.request,urllib.error,subprocess,os,sys
TOKEN=os.environ.get("GH_TOKEN") or (sys.argv[1] if len(sys.argv)>1 else "")
REPO="Danny-68/muto-rs-wiki"
BASE="https://api.github.com"
H={"Authorization":f"token {TOKEN}","Accept":"application/vnd.github+json","Content-Type":"application/json","X-GitHub-Api-Version":"2022-11-28"}
def up(p,d):
 url=f"{BASE}/repos/{REPO}/contents/{p}"
 b=base64.b64encode(d).decode()
 try:
  with urllib.request.urlopen(urllib.request.Request(url,headers=H)) as r:sha=json.load(r)["sha"];pl={"message":f"Add {p}","content":b,"sha":sha}
 except urllib.error.HTTPError as e:
  if e.code==404:pl={"message":f"Add {p}","content":b}
  else:print(f"ERR {p} {e.code}");return
 try:
  with urllib.request.urlopen(urllib.request.Request(url,data=json.dumps(pl).encode(),headers=H,method="PUT")):print(f"OK {p}")
 except urllib.error.HTTPError as e:print(f"FAIL {p} {e.code}")
def rd(p):return open(p,"rb").read() if os.path.exists(p) else None
def dc(p):r=subprocess.run(["docker","exec","humble_run","cat",p],capture_output=True);return r.stdout if r.returncode==0 and r.stdout else None
def js(p):r=subprocess.run(["ssh","-o","StrictHostKeyChecking=no","-o","PasswordAuthentication=no","Danny@192.168.68.86",f"cat {p}"],capture_output=True);return r.stdout if r.returncode==0 and r.stdout else None
def jc(p):r=subprocess.run(["ssh","-o","StrictHostKeyChecking=no","-o","PasswordAuthentication=no","Danny@192.168.68.86",f"sudo docker exec jetson_run cat {p}"],capture_output=True);return r.stdout if r.returncode==0 and r.stdout else None
H_FILES={"software/pi/gait/phoenix_gait.py":"/home/pi/phoenix_gait.py","software/pi/gait/centipede_gait.py":"/home/pi/centipede_gait.py","software/pi/gait/foot_contact.py":"/home/pi/foot_contact.py","software/pi/ros2/muto_driver_fixed.py":"/home/pi/muto_driver_fixed.py","software/pi/ros2/sensor_relay.py":"/home/pi/sensor_relay.py","software/pi/ros2/scan_timestamped.py":"/home/pi/scan_timestamped.py","software/pi/ros2/odom_publisher.py":"/home/pi/odom_publisher.py","software/pi/ros2/odom_tf_publisher.py":"/home/pi/odom_tf_publisher.py","software/pi/ros2/robot_bridge.py":"/home/pi/robot_bridge.py","software/pi/sensors/imu_publisher.py":"/home/pi/imu_publisher.py","software/pi/sensors/imu_test.py":"/home/pi/imu_test.py","software/pi/sensors/imu_diag.py":"/home/pi/imu_diag.py","software/pi/sensors/servo_angle_test.py":"/home/pi/servo_angle_test.py","software/pi/sensors/servo_angle_verify.py":"/home/pi/servo_angle_verify.py","software/pi/sensors/foot_contact_probe_test.py":"/home/pi/foot_contact_probe_test.py","software/pi/tools/rotate_calib.py":"/home/pi/rotate_calib.py","software/pi/tools/yahboom_oled.py":"/home/pi/yahboom_oled.py","software/pi/tools/speed_calibration.py":"/home/pi/muto-llm-2.0/speed_calibration_30_levels.py","software/pi/voice/voice_raw.py":"/home/pi/voice_raw.py","software/pi/voice/voice_raw2.py":"/home/pi/voice_raw2.py","software/pi/voice/voice_test.py":"/home/pi/voice_test.py","software/pi/scripts/muto_rtabmap_start.sh":"/home/pi/muto_rtabmap_start.sh","software/pi/scripts/muto_slam_start.sh":"/home/pi/muto_slam_start.sh","software/pi/scripts/rtabmap_restart.sh":"/home/pi/rtabmap_restart.sh","software/pi/scripts/switch_to_yahboom.sh":"/home/pi/switch_to_yahboom.sh","software/pi/scripts/switch_to_own_stack.sh":"/home/pi/switch_to_own_stack.sh","software/pi/scripts/start_lidar.sh":"/home/pi/start_lidar.sh","software/pi/config/cyclone_dds.xml":"/home/pi/cyclone_dds.xml","software/pi/config/ekf_config.yaml":"/home/pi/ekf_config.yaml","software/pi/config/muto_slam.yaml":"/home/pi/muto_slam.yaml","software/pi/config/rtabmap_params.yaml":"/home/pi/rtabmap_params.yaml","setup/udev/99-usb-serial.rules":"/etc/udev/rules.d/99-usb-serial.rules","setup/udev/56-orbbec-usb.rules":"/etc/udev/rules.d/56-orbbec-usb.rules"}
C_FILES={"software/container/muto_rtabmap_launch.py":"/root/muto_rtabmap_launch.py","software/container/rgbd_throttle.py":"/root/rgbd_throttle.py","software/container/scan_relay.py":"/root/scan_relay.py","software/container/config/hexapod_nav_params.yaml":"/root/hexapod_nav_params_custom.yaml","software/container/config/muto_map.yaml":"/root/muto_map.yaml","software/container/config/rtabmap_params.yaml":"/root/rtabmap_params.yaml","software/container/config/cyclone_dds.xml":"/root/cyclone_dds.xml","software/container/config/ekf_config.yaml":"/root/ekf_config.yaml"}
J_FILES={"software/jetson/scripts/muto_jetson_start.sh":"/home/Danny/muto_jetson_start.sh","software/jetson/config/cyclone_dds.xml":"/home/Danny/cyclone_dds.xml","software/jetson/config/ekf_config.yaml":"/home/Danny/ekf_config.yaml"}
print("PI HOST")
for g,l in H_FILES.items():
 d=rd(l)
 if d:up(g,d)
 else:print(f"SKIP {l}")
print("CONTAINER")
for g,c in C_FILES.items():
 d=dc(c)
 if d:up(g,d)
 else:print(f"SKIP {c}")
print("JETSON")
for g,j in J_FILES.items():
 d=js(j)
 if d:up(g,d)
 else:print(f"SKIP {j}")
print("JETSON CONTAINER")
d=jc("/root/rtabmap_params.yaml")
if d:up("software/jetson/container/config/rtabmap_params.yaml",d)
else:print("SKIP jetson_run:/root/rtabmap_params.yaml")
print("DONE")
