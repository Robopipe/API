# Sensors

Each camera contains a number of sensors of different types. Our API currently supports manipulation of color and monochromatic image sensors. Each sensor produces image data in various formats and is configurable independently of other sensor on the same device. Sensors are addressed by their socket name which is in the format [_CAM\_(A-H)_](#user-content-fn-1)[^1]_._

## API Reference

{% swagger src="../../.gitbook/assets/oas.yaml" path="/cameras/{mxid}/sensors/{sensor_name}/" method="post" %}
[oas.yaml](../../.gitbook/assets/oas.yaml)
{% endswagger %}

{% swagger src="../../.gitbook/assets/oas.yaml" path="/cameras/{mxid}/sensors/{sensor_name}/" method="delete" %}
[oas.yaml](../../.gitbook/assets/oas.yaml)
{% endswagger %}

{% swagger src="../../.gitbook/assets/oas.yaml" path="/cameras/{mxid}/sensors/" method="get" %}
[oas.yaml](../../.gitbook/assets/oas.yaml)
{% endswagger %}

{% swagger src="../../.gitbook/assets/oas.yaml" path="/cameras/{mxid}/sensors/{sensor_name}/config" method="get" %}
[oas.yaml](../../.gitbook/assets/oas.yaml)
{% endswagger %}

{% swagger src="../../.gitbook/assets/oas.yaml" path="/cameras/{mxid}/sensors/{sensor_name}/config" method="post" %}
[oas.yaml](../../.gitbook/assets/oas.yaml)
{% endswagger %}

{% swagger src="../../.gitbook/assets/oas.yaml" path="/cameras/{mxid}/sensors/{sensor_name}/control" method="get" %}
[oas.yaml](../../.gitbook/assets/oas.yaml)
{% endswagger %}

{% swagger src="../../.gitbook/assets/oas.yaml" path="/cameras/{mxid}/sensors/{sensor_name}/control" method="post" %}
[oas.yaml](../../.gitbook/assets/oas.yaml)
{% endswagger %}

{% swagger src="../../.gitbook/assets/oas.yaml" path="/cameras/{mxid}/sensors/{sensor_name}/still" method="get" %}
[oas.yaml](../../.gitbook/assets/oas.yaml)
{% endswagger %}

[^1]: This means that there are up to **8**

    available sensor, with names CAM\_A,

    CAM\_B, CAM\_C, etc.
