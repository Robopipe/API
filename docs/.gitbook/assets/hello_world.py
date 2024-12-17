import requests

API_BASE = f"http://localhost:8080"


def get_devices():
    return requests.get(f"{API_BASE}/cameras").json()


mxid = get_devices()[0].get("mxid")


def get_cameras():
    return requests.get(f"{API_BASE}/cameras/{mxid}/sensors").json()


print(get_cameras())
sensor_name = "CAM_A"

import os
import time


def save_image(path: str, image: bytes):
    dirname = os.path.dirname(path)

    if not os.path.exists(dirname):
        os.makedirs(dirname)

    with open(path, "wb") as f:
        f.write(image)


def capture_data(n: int = 100, delay: float = 5):
    for i in range(n):
        res = requests.get(f"{API_BASE}/cameras/{mxid}/sensors/{sensor_name}/still")
        image = res.content
        save_image(f"data/{i}.jpeg", image)
        time.sleep(delay)


capture_data(10)
