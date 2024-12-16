---
description: Capture images, label data, train model, and deploy it on Robopipe controller
---

# Hello world

## Description

In this example we will learn the basics of working with Robopipe API. We will list all devices and select one we want to use. Then we will capture the training data, label them and build a simple neural network which we will then deploy on a device. Then we will run inference directly on the device and observe the results.

The model we will build will be an image classification model detecting 2 classes - _red_ and _other._ It will simply say whether the object it sees is red or no&#x74;_._

The complete example with all the python code is available below.

{% file src="../.gitbook/assets/hello_world.py" %}

## Listing devices

In order to capture training data we need to specify device from which to capture from. To do this we will list all device.

{% code fullWidth="false" %}
```python
import requests

SN = 1001 # substitue with the serial number of your controller
API_BASE = f"http://robopipe-controller-{SN}"

def get_devices():
    return requests.get(f"{API_BASE}/cameras").json()

devices = get_devices()
```
{% endcode %}

Devices will contain an array of connected devices, containing their MXID along with other information. To find out more about devices API head over to the [API reference](../api-reference/cameras.md#cameras).

We will use the first device.

```python
mxid = devices[0].get("mxid")
```

We will also need to select a camera. To list all cameras you can use the function below.

```python
def get_cameras(mxid: str):
    return requests(f"{API_BASE}/cameras/{mxid}/sensors").json()
```

```python
camera = "CAM_A"
```

## Capturing images

In order to train our model we first need to get the training data. These data will be RGB images captured by our device via out API. We will create a function that will periodically call the API to capture an image and save it to specified destination.

```python
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
```

To capture data we simply call `capture_data(n=<image count>, delay=<capturing interval>)`. This will, however, capture the data in full camera resolution, which might not be desired. In our case, the model will be trained on images of size 200x200. We can create another function, which will properly configure the camera, so that the captured images are the right size. There are numerous options which you can configure via the [config](../api-reference/sensors.md#cameras-mxid-sensors-sensor_name-config) and [control](../api-reference/sensors.md#cameras-mxid-sensors-sensor_name-control) API.

```python
def configure_camera(width: int, height: int):
    data = {"still_size": (width, height)}
    return requests.post(
        f"{API_BASE}/cameras/{mxid}/sensors/{sensor_name}/config", data
    ).json()
```

## Data labeling

We will use [label studio](https://labelstud.io/) for labeling.

```bash
# Install and run label studio
pip install label-studio
label-studio start
```

Now head over to [http://localhost:8080](http://localhost:8080), create an account and create a new empty project. In the labeling setup tab, choose _Image Classification_, and enter _red_ and _other_ as choices. After you're done with the project configuration, click _Save_.

<figure><img src="../.gitbook/assets/image.png" alt=""><figcaption></figcaption></figure>

