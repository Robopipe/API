---
description: Configure the API
---

# Configuration

Configuration is done via environment variables (usually located in .env file) and controller config file.

## Environment variables

Environment variables are set using a `.env` file located in the root of the project. You can also set custom file location by exporting `ROBOPIPE_API_ENV` environment variable. You can find an example in `.env.example`. To modify these values simply copy the file into `.env` and change the desired keys.

{% hint style="info" %}
Please note that changing the **CORS\_ORIGINS** to a value that does _not_ include the URL of these docs will render the _Try it_ and _stream_ _player_ functionality in these do&#x63;_&#x73;_ unusable.
{% endhint %}

* **HOST** - domain name or IP address of the host that serves the API
  * DEFAULT - 0.0.0.0
* **PORT** - Por on which the API is running
  * DEFAULT - 8080
* **CORS\_ORIGINS** - comma separated list of allowed origins for the CORS preflight requests
  * DEFAULT - "\*"
* **CONTROLLER\_CONFIG** - path to the _config.yaml_ file defining controller configuration.
  * DEFAULT - _empty_

## Controller configuration

Controller configration is done using a _config.yaml_ file located at path specified by _CONTROLLER\_CONFIG_ environment variable. In this path a _config.yaml_ file and a directory named _hw\_definitions_ must be present.

### config.yaml

This file should contain one key named comm\_channels with the follow structure:

```yaml
comm_channels:
    <bus_name>:
        type: <bus_type>
        <bus specific settings>: <specific parameters>
        devices:
            <device_name>:
                slave-id: <slave_id>
                model: <model_id>
                scan_frequency: <scan_frequency>
```

#### Bus configuration

* _\<bus\_name>_ - Your choice, but has to be unique
* `type` options:
  * `MODBUSTCP`
    * `hostname` - hostname of the Modbus server
    * `port` - port of the Modbus server
  * `MODBUSRTU`
    * `port` - path to the Modbus device
    * `boudrate` - baudrate of the Modbus device
    * `parity` - parity of the Modbus device (`N` / `E` / `O`)
  * `OWBUS`
    * `interval` - interval of values updating
    * `scan_interval` - new devices will be automatically assigned
    * `owpower` - [Circuit](https://evok.readthedocs.io/en/stable/circuit/) of owpower device (for restarting bus; optional parameter)

#### Device configuration <a href="#device-configuration" id="device-configuration"></a>

* _\<device\_name>_: the device will be available in the API under this name. Has to be unique.

**MODBUSTCP & MODBUSRTU**

* `model_id` - assigns a Modbus register map (examples: `xS51`, `xS11`), see [hw\_definitions](https://evok.readthedocs.io/en/stable/configs/hw_definitions/).
* `slave_id` - slave address or unit-ID of the Modbus device.
* `scan_frequency` - an optional parameter, determines how often values are read from the device (Default value is 50).

**OWBUS**

* `type` - 1-Wire sensor type, options: \[`DS18B20`, `DS18S20`, `DS2438`, `DS2408`, `DS2406`, `DS2404`, `DS2413`]
* `address` - 1-Wire device address

### HW definitions
