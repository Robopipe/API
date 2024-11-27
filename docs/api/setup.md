---
description: >-
  This guide covers the setup of Robopipe API to start interacting with your
  Robopipe or local devices.
---

# Setup

## Running on Robopipe device

Robopipe API comes pre-installed on all Robopipe devices. If you own a Robopipe device, make sure it is turned on and avilable on your local network and that should be it! You can go ahead to the next section to start interacting with Robopipe API. If you're unsure whether the API is running, or run into any problems, visit our [troubleshooting guide](../other/troubleshooting.md).

## Running from source

Robopipe API is open source and free for anyone to download, play with, and modify. Follow these steps to get Robopipe API running on your local device. The source code can be found [here](https://github.com/Koala42/io.robopipe.api).

### System requirements

Before you run Robopipe API on your device, make sure you have the following prerequisites.

* You have cloned the [Robopipe API GitHub repository](https://github.com/Koala42/io.robopipe.api).
* You have [Python](https://www.python.org/) 3.11.10 or higher installed.
* Though it is not a requirement for running the API, you should be able to connect to a Luxonis device, otherwise the things you can do with the API are greatly limited.

### Running the API

In your terminal, change directory to the one containing the Robopipe API source code.

```sh
cd robopipe-api
```

Set up and activate virtual environment (this step is optional).

```bash
python -m venv .venv 
source .venv/bin/activate
```

Install dependencies.

```bash
python -m pip install requirements.txt
```

Run the API.

{% tabs %}
{% tab title="Running on uvicorn server" %}
```bash
python3 -m robopipe_api
```
{% endtab %}

{% tab title="Running  via FastAPI CLI" %}
If you want to run the API using FastAPI CLI, you also need to install the CLI additionally to already installed dependencies. To learn more about FastAPI CLI please refer to [this documentation](https://fastapi.tiangolo.com/fastapi-cli/).

```bash
python -m pip install "fastapi-cli[standard]"
fastapi run robopipe_api/robopipe.py
```
{% endtab %}
{% endtabs %}
