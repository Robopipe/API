# OS

## Description

Robopipe OS is a custom pre-configured OS image based on [Debian](https://www.debian.org/). It comes with all the packages and tools you need to build a AI/CV application pre-installed. You can find all releases along with the configuration scripts in [this repository](https://github.com/Robopipe/OS).

## Default configuration

### Users

The default user you should use when working on the controller directly is `admin`. The password is `robopipe.io`.

### Hostname & mDNS

A hostname is assigned to the controller on startup. The assigned hostname is in the format `robopipe-<id>`, where _id_ is determined dynamically on each startup. When the controller is started it will scan the local network, and assign itself the lowest possible _id_ which is not already taken. This means that the first controller you start will have _id_ 1, the next will have _id_ 2 and so on. At the same time, it will also broadcast an [mDNS](https://en.wikipedia.org/wiki/Multicast_DNS) record based on its hostname (`robopipe-<id>.local`). This means that the controller can be addresses not only by its IP address, but also by its hostname in the local network. This behaviour is enabled via `robopipehostname` service, if you wish to disable it, you can do so using:

```bash
sudo systemctl disable robopipehostname # this will take effect on the next startup
```

### SSH

SSH server is running on the controller by default on port 22.

### Robopipe API

Robopipe API is configured to start automatically at startup. If you wish to disable this, you can do so using:

```bash
sudo systemctl disable robopipeapi
```

## Service Mode

Sevice mode is used for backing up the operating system, uploading new OS images or restoring access to the unit. This mode does not publish an mDNS record.

### Entering the Service Mode

* Turn off the controller
* Press and hold the _SERVICE_ button on your controller (usually located next to USB labels)
* Turn on the controller while still hodling the _SERVICE_ button
* Release the _SERVICE_ button when all the LEDs start blinking periodically

