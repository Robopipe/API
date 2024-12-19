---
description: Real world usage example of counting capsules in manufacturing
---

# Capsule counting

## Problem description

We want to count capsules placed in a special holder in a machine to see if the holder is full or not. We then want to indicate to the machine that the holder is full which triggers an action on the machine side. We will do this by capturing and labeling our data as we did in our [hello world example](../getting-started/hello-world.md). The we will build a more advanced neural network, deploy it, and link the output to the controller for sending signals to the machine.

<figure><img src="../.gitbook/assets/capsules.jpg" alt=""><figcaption><p>The machine containing 3 holders for capsules</p></figcaption></figure>

## Collecting data

To collect the data, we will use a more automated approach than in our [hello world example](../getting-started/hello-world.md). We will create a function that captures a defined number of images from the camera at specific times automatically.

```python
import os
import requests
import time

API_BASE = "http://robopipe-controller-1.local"
mxid = "123456789"
sensor_name = "CAM_A"

def save_image(path: str, image: bytes):
    dirname = os.path.dirname(path)

    if not os.path.exists(dirname):
        os.makedirs(dirname)

    with open(path, "wb") as f:
        f.write(image)

def capture_images(n: int, delay: float):
    for i in range(n):
        img_res = requests.get(
            f"{API_BASE}/cameras/{mxid}/sensors/{sensor_name}/still"
        )
        img = img_res.content
        save_image(f"data/{i}.jpeg", img)
        time.sleep(delay)
```
