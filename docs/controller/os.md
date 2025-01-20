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
* Release the _SERVICE_ button when all the LEDs start blinking periodically (except for _PWR_ and _RUN_)

### IP address

In service mode, the controller will try to obtain an IP address from DHCP server, if there is one on the network. To find your controller's IP address, you can use [nmap](https://nmap.org/).

```bash
sudo nmap -sn <local network IP address>/<mask> # e.g. sudo nmap -sn 10.0.0.0/24
```

This will scan the network and list all found devices. Search for the line that includes your controller's MAC address (can be found on the box). The controller's IP address will be printed above that.

The controller will also have a static IP address `192.168.200.200/24`. You can use this by setting you PC's IP address to `192.168.200.100/24` and then connecting to the controller.

### Service Mode Web Interface

Service mode provides a comprehensible web interface. To use this interface simply enter your controller's IP addres into your browser. Make sure that the controller is connected to the same network as your computer.

<figure><img src="../.gitbook/assets/image (4).png" alt=""><figcaption></figcaption></figure>

## Updating the OS

{% hint style="warning" %}
Updating the OS will delete all your saved data on the controller
{% endhint %}

Use this guide to install the latest version of Robopipe OS on your device.

* Start your controller in [service mode](os.md#service-mode)
* Download the [latest release of Robopipe OS](https://github.com/Robopipe/OS/releases/latest)
  * Donwload the **archive.swu** file
* Open the service mode website in your browser
  * Enter the IP address of your controller into your browser (check the [guide above ](os.md#ip-address)to see how to find your controller's IP address)
* Upload the archive.swu file into the Software Update window
  * Drag and drop the file into the window or click on the window and select the file from your files
