# Cameras

Camera is a basic building block of Robopipe. It represent a single Luxonis device that can be manipulated through our API. Each camera corresponds to a real camera device and is independent of other devices. Camera can be connected via USB or Ethernet interface, the API doesn't make any distinctions regarding this matter. Camera is always addressed by its unique [MXID](https://docs.luxonis.com/software/depthai/examples/device_information/).

{% hint style="warning" %}
If you're using PoE devices, make sure that they are connected to a network with running DHCP server. While this step can be ommited, the autodiscovery might be unreliable. If you run into any troubles connecting to PoE cameras, visit our [troubleshooting guide](../../other/troubleshooting.md), or refer to  [Luxonis PoE docs](https://docs.luxonis.com/hardware/platform/deploy/poe-deployment-guide/#PoE%20deployment%20guide-Initial%20Connection-Debugging).
{% endhint %}

## API Reference

{% swagger src="../../.gitbook/assets/oas.yaml" path="/cameras/" method="get" %}
[oas.yaml](../../.gitbook/assets/oas.yaml)
{% endswagger %}

{% swagger src="../../.gitbook/assets/oas.yaml" path="/cameras/{mxid}/" method="get" %}
[oas.yaml](../../.gitbook/assets/oas.yaml)
{% endswagger %}

{% swagger src="../../.gitbook/assets/oas.yaml" path="/cameras/{mxid}/" method="post" %}
[oas.yaml](../../.gitbook/assets/oas.yaml)
{% endswagger %}

{% swagger src="../../.gitbook/assets/oas.yaml" path="/cameras/{mxid}/" method="delete" %}
[oas.yaml](../../.gitbook/assets/oas.yaml)
{% endswagger %}

{% swagger src="../../.gitbook/assets/oas.yaml" path="/cameras/{mxid}/stats" method="get" %}
[oas.yaml](../../.gitbook/assets/oas.yaml)
{% endswagger %}
