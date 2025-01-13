---
description: Run the API locally on your own device
---

# Generic Devices

## Known working devices

### Cameras

* Any [Luxonis](https://www.luxonis.com/) OAK camera from the OAK-1 or OAK-D series

### Controllers

* Any [Unipi](https://www.unipi.technology/) controller from the [Patron](https://www.unipi.technology/products/unipi-patron-374?categoryId=30\&categorySlug=unipi-patron) or [Neuron](https://www.unipi.technology/products/unipi-neuron-3?categoryId=2\&categorySlug=unipi-neuron) series.

## Running from source

Robopipe API is open source and free for anyone to download, play with, and modify. Follow these steps to get Robopipe API running on your local device. The source code can be found [here](https://github.com/Koala42/io.robopipe.api).

### System requirements

Before you run Robopipe API on your device, make sure you have the following prerequisites.

* You have cloned the [Robopipe API GitHub repository](https://github.com/Koala42/io.robopipe.api).
* You have [Python](https://www.python.org/) 3.11.10 or higher installed.
* Though it is not a requirement for running the API, you should be able to connect to a Luxonis device, otherwise the things you can do with the API are greatly limited.
* If you also wish to use the [controller API,](../api/rest-api-reference/controller.md) you need to run the API on a Unipi device.

### Running the API

Clone the [Robopipe API GitHub repository](https://github.com/Koala42/io.robopipe.api).

```bash
git clone https://github.com/Robopipe/api.git
```

In your terminal, change directory to the one containing the Robopipe API source code.

```sh
cd robopipe-api
```

Set up and activate virtual environment (this step is optional if you have venv already active).

```bash
python -m venv .venv 
source .venv/bin/activate
```

Configure the API according to [configuration reference](../api/configuration.md).

Install dependencies.

```bash
python -m pip install -r requirements.txt
```

Run the API.

{% tabs %}
{% tab title="Running on uvicorn server" %}
```bash
python3 -m robopipe_api
```
{% endtab %}

{% tab title="Running via FastAPI CLI" %}


If you want to run the API using FastAPI CLI, you also need to install the CLI additionally to already installed dependencies. To learn more about FastAPI CLI please refer to [this documentation](https://fastapi.tiangolo.com/fastapi-cli/).

```bash
python -m pip install "fastapi-cli[standard]"
fastapi run robopipe_api/robopipe.py
```
{% endtab %}
{% endtabs %}
