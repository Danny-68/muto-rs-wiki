#!/usr/bin/env python3
"""
sensor_relay.py — draait IN de humble_run container (NetworkMode: host).

Abonneert op /scan, /camera/depth/{image_raw,camera_info} en
/camera/color/image_raw, en serveert de laatste waarden via een lokale
HTTP-server op poort 5001. Omdat de container in 'host' netwerkmode draait,
is dit vanaf de Pi-host bereikbaar via http://localhost:5001/...

Gebruikt alleen de Python-standaardbibliotheek + numpy (geen Flask, geen
cv_bridge nodig). JPEG-encodering gebeurt met OpenCV als beschikbaar, met
een pure-numpy PNG-fallback als OpenCV in de container ontbreekt.

Startcommando (in de container):
  source /opt/ros/humble/setup.bash
  source /root/yahboomcar_ros2_ws/software/library_ws_humble/install/setup.bash
  python3 /root/sensor_relay.py

Endpoints:
  GET /scan/nearest          -> dichtstbijzijnde LiDAR-afstand + hoek
  GET /depth/point?u=..&v=.. -> pinhole-projectie op pixel (u,v)
  GET /depth/center          -> alias voor /depth/point op het midden van het beeld
  GET /camera/color/jpeg     -> laatste kleurenframe als JPEG (of PNG-fallback)
"""
import json
import math
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

import numpy as np
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import LaserScan, Image, CameraInfo

# OpenCV is optioneel — alleen voor nette JPEG-encodering
try:
    import cv2
    _HAS_CV2 = True
except Exception:
    _HAS_CV2 = False

state = {
    "scan": None,
    "depth_image": None,
    "camera_info": None,
    "color_image": None,       # numpy array in BGR
    "color_encoding": None,
}
lock = threading.Lock()


class SensorRelayNode(Node):
    def __init__(self):
        super().__init__('sensor_relay')
        self.create_subscription(LaserScan, '/scan', self.on_scan, 10)
        self.create_subscription(Image, '/camera/depth/image_raw', self.on_depth, 10)
        self.create_subscription(CameraInfo, '/camera/depth/camera_info', self.on_camera_info, 10)
        self.create_subscription(Image, '/camera/color/image_raw', self.on_color, 10)
        self.get_logger().info('sensor_relay actief, HTTP op poort 5001')

    def on_scan(self, msg: LaserScan):
        ranges = np.array(msg.ranges)
        mask = (ranges > msg.range_min) & (ranges < msg.range_max) & np.isfinite(ranges)
        valid_idx = np.where(mask)[0]
        if len(valid_idx) == 0:
            with lock:
                state["scan"] = {"distance_m": None, "angle_deg": None}
            return
        nearest_idx = valid_idx[np.argmin(ranges[valid_idx])]
        distance = float(ranges[nearest_idx])
        angle_deg = math.degrees(msg.angle_min + nearest_idx * msg.angle_increment)
        with lock:
            state["scan"] = {"distance_m": round(distance, 3), "angle_deg": round(angle_deg, 1)}

    def on_depth(self, msg: Image):
        if msg.encoding == '16UC1':
            arr = np.frombuffer(msg.data, dtype=np.uint16).reshape(msg.height, msg.width)
            arr = arr.astype(np.float32) / 1000.0  # mm -> m
        elif msg.encoding == '32FC1':
            arr = np.frombuffer(msg.data, dtype=np.float32).reshape(msg.height, msg.width)
        else:
            self.get_logger().warn(f'Onbekende depth-encoding: {msg.encoding}')
            return
        with lock:
            state["depth_image"] = arr

    def on_camera_info(self, msg: CameraInfo):
        with lock:
            state["camera_info"] = {
                "fx": msg.k[0], "fy": msg.k[4],
                "cx": msg.k[2], "cy": msg.k[5],
                "width": msg.width, "height": msg.height,
            }

    def on_color(self, msg: Image):
        # Meest voorkomende encodings voor de Astra kleurenstream: rgb8 / bgr8
        if msg.encoding in ('rgb8', 'bgr8'):
            arr = np.frombuffer(msg.data, dtype=np.uint8).reshape(msg.height, msg.width, 3)
            if msg.encoding == 'rgb8':
                arr = arr[:, :, ::-1]  # RGB -> BGR (voor OpenCV/JPEG)
        else:
            self.get_logger().warn(f'Onbekende color-encoding: {msg.encoding}')
            return
        with lock:
            state["color_image"] = arr.copy()
            state["color_encoding"] = msg.encoding


def get_depth_point(u=None, v=None):
    with lock:
        depth = state["depth_image"]
        info = state["camera_info"]
    if depth is None or info is None:
        return {"ok": False, "error": "nog geen depth/camera_info data ontvangen"}

    if u is None:
        u = info["width"] // 2
    if v is None:
        v = info["height"] // 2
    u = max(0, min(info["width"] - 1, int(float(u))))
    v = max(0, min(info["height"] - 1, int(float(v))))

    z = float(depth[v, u])
    if z <= 0 or not math.isfinite(z):
        window = depth[max(0, v - 5):v + 6, max(0, u - 5):u + 6]
        valid = window[(window > 0) & np.isfinite(window)]
        if len(valid) == 0:
            return {"ok": False, "error": "geen geldige diepte op dit punt"}
        z = float(np.median(valid))

    x = (u - info["cx"]) * z / info["fx"]
    y = (v - info["cy"]) * z / info["fy"]
    return {"ok": True, "u": u, "v": v, "x_m": round(x, 3), "y_m": round(y, 3), "z_m": round(z, 3)}


def get_color_jpeg():
    """Retourneert (bytes, content_type) van het laatste kleurenframe, of (None, None)."""
    with lock:
        img = state["color_image"]
    if img is None:
        return None, None
    if _HAS_CV2:
        ok, buf = cv2.imencode('.jpg', img)
        if ok:
            return buf.tobytes(), 'image/jpeg'
    # Fallback: pure-numpy PNG (geen OpenCV nodig)
    png = _encode_png(img[:, :, ::-1])  # BGR -> RGB voor PNG
    return png, 'image/png'


def _encode_png(rgb):
    """Minimale pure-Python PNG-encoder (RGB uint8). Alleen als OpenCV ontbreekt."""
    import struct, zlib
    h, w, _ = rgb.shape
    raw = bytearray()
    for y in range(h):
        raw.append(0)  # filter type 0
        raw.extend(rgb[y].tobytes())
    def chunk(tag, data):
        return (struct.pack('>I', len(data)) + tag + data +
                struct.pack('>I', zlib.crc32(tag + data) & 0xffffffff))
    sig = b'\x89PNG\r\n\x1a\n'
    ihdr = struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0)
    idat = zlib.compress(bytes(raw), 6)
    return sig + chunk(b'IHDR', ihdr) + chunk(b'IDAT', idat) + chunk(b'IEND', b'')


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def _send_json(self, payload, status=200):
        body = json.dumps(payload).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_bytes(self, data, content_type, status=200):
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)

        if parsed.path == '/scan/nearest':
            with lock:
                s = state["scan"]
            if s is None:
                self._send_json({"ok": False, "error": "nog geen /scan data ontvangen"}, 503)
            else:
                self._send_json({"ok": True, **s})

        elif parsed.path in ('/depth/point', '/depth/center'):
            u = qs.get('u', [None])[0]
            v = qs.get('v', [None])[0]
            result = get_depth_point(u, v)
            self._send_json(result)

        elif parsed.path == '/camera/color/jpeg':
            data, ctype = get_color_jpeg()
            if data is None:
                self._send_json({"ok": False, "error": "nog geen /camera/color data ontvangen"}, 503)
            else:
                self._send_bytes(data, ctype)

        else:
            self._send_json({"ok": False, "error": "onbekend endpoint"}, 404)


def run_http_server():
    server = HTTPServer(('0.0.0.0', 5001), Handler)
    server.serve_forever()


def main():
    rclpy.init()
    node = SensorRelayNode()
    http_thread = threading.Thread(target=run_http_server, daemon=True)
    http_thread.start()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()