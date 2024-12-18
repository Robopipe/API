import requests
import os

ID = 1  # substitute with the id of your controller
API_BASE = f"http://robopipe-controller-{ID}.local"


def get_devices():
    return requests.get(f"{API_BASE}/cameras").json()


devices = get_devices()
mxid = get_devices()[0].get("mxid")


def get_cameras():
    return requests.get(f"{API_BASE}/cameras/{mxid}/sensors").json()


sensor_name = list(get_cameras().keys())[0]  # for me this is CAM_A which is RGB camera


def save_image(path: str, image: bytes):
    dirname = os.path.dirname(path)

    if not os.path.exists(dirname):
        os.makedirs(dirname)

    with open(path, "wb") as f:
        f.write(image)


def capture_data():
    i = 1

    while True:
        key = input("Enter input ('s' to save image, 'q' to quit): ")

        if key == "s":
            image_response = requests.get(
                f"{API_BASE}/cameras/{mxid}/sensors/{sensor_name}/still"
            )
            image = image_response.content
            save_image(f"data/{i}.jpeg", image)
            i += 1
        elif key == "q":
            break


def configure_camera(width: int, height: int):
    config = requests.get(
        f"{API_BASE}/cameras/{mxid}/sensors/{sensor_name}/config"
    ).json()
    config.update({"still_size": [width, height]})

    return requests.post(
        f"{API_BASE}/cameras/{mxid}/sensors/{sensor_name}/config", json=config
    ).json()


config = configure_camera(200, 200)
capture_data()


def deploy_model(path="model.blob"):
    requests.post(
        f"{API_BASE}/cameras/{mxid}/sensors/{sensor_name}/nn",
        files={"model": open(path, "rb")},
    )


WS_BASE = f"ws://robopipe-controller-{ID}.local"

import anyio
import websockets


async def main():
    async with websockets.connect(
        f"{WS_BASE}/cameras/{mxid}/sensors/{sensor_name}/nn"
    ) as ws:
        while True:
            msg = await ws.recv()
            print(msg)


anyio.run(main)
