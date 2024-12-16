---
description: Connecting your devices.
---

# Connection

## Controller

{% hint style="danger" %}
In case of any manipulation with the controller, first turn off all power sources as theres is a risk of electrocution or damage. Improper handling can result in significant property damage, bodily injury or death. Please refer to [Unipi Patron manual](https://kb.unipi.technology/_media/en:files:products:unipi-patron-manual-en.pdf) to read all safety instructions.&#x20;
{% endhint %}

### Connection using router

Connect the controller and luxonis camera to a router with running DHCP server (most routers have DHCP server on by default) and then connect the controller to a power supply as shown in the diagram below.

<div data-full-width="true"><figure><img src="../.gitbook/assets/plc-router-luxonis-pc.png" alt=""><figcaption></figcaption></figure></div>

### Direct connection

Connect the luxonis camera directly to the controller via USB and then connect the controller to your PC via ethernet as shown in the diagram below.

<figure><img src="../.gitbook/assets/plc-pc-luxonis.png" alt=""><figcaption></figcaption></figure>

### Accessing the controller

The easiest way to check if everything is running is to head over to `http://robopipe-controller-<sn>.local`, where _sn_ is the [serial number of your controller.](#user-content-fn-1)[^1] You should see output:&#x20;

```
Hello from Robopipe API!
```

The controller is also accesible via [SSH](https://en.wikipedia.org/wiki/Secure_Shell). The default hostname is set to `robopipe-controller-<sn>.local`. The default user is `robopipe` with password `robopipe.io`. Enter this command into your terminal to connect to the controller, enter `robopipe.io` when prompted for password:

```bash
ssh robopipe@robopipe-controller-<sn>.local
```

When connecting for the first time, you will be asked to verify the authenticity of the controller's key. Enter `yes` and press enter.&#x20;

[^1]: You can find your controller's serial number printed on the controller's box.
