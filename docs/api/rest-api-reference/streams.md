# Streams

Each camera contains a number of sensors of different types. Our API currently supports manipulation of color and monochromatic image sensors. Each sensor produces image data in various formats and is configurable independently of other sensor on the same device. Sensors are addressed by their socket name which is in the format [_CAM\_(A-H)_](#user-content-fn-1)[^1]_._

## API Reference

{% swagger src="../../.gitbook/assets/oas.yml" path="/cameras/{mxid}/streams/" method="get" %}
[oas.yml](../../.gitbook/assets/oas.yml)
{% endswagger %}

{% swagger src="../../.gitbook/assets/oas.yml" path="/cameras/{mxid}/streams/{stream_name}/" method="post" %}
[oas.yml](../../.gitbook/assets/oas.yml)
{% endswagger %}

{% swagger src="../../.gitbook/assets/oas.yml" path="/cameras/{mxid}/streams/{stream_name}/" method="delete" %}
[oas.yml](../../.gitbook/assets/oas.yml)
{% endswagger %}

{% swagger src="../../.gitbook/assets/oas.yml" path="/cameras/{mxid}/streams/{stream_name}/config" method="get" %}
[oas.yml](../../.gitbook/assets/oas.yml)
{% endswagger %}

{% swagger src="../../.gitbook/assets/oas.yml" path="/cameras/{mxid}/streams/{stream_name}/config" method="post" %}
[oas.yml](../../.gitbook/assets/oas.yml)
{% endswagger %}

{% swagger src="../../.gitbook/assets/oas.yml" path="/cameras/{mxid}/streams/{stream_name}/control" method="get" %}
[oas.yml](../../.gitbook/assets/oas.yml)
{% endswagger %}

{% swagger src="../../.gitbook/assets/oas.yml" path="/cameras/{mxid}/streams/{stream_name}/control" method="post" %}
[oas.yml](../../.gitbook/assets/oas.yml)
{% endswagger %}

{% swagger src="../../.gitbook/assets/oas.yml" path="/cameras/{mxid}/streams/{stream_name}/still" method="get" %}
[oas.yml](../../.gitbook/assets/oas.yml)
{% endswagger %}

[^1]: This means that there are up to **8**

    available sensor, with names CAM\_A,

    CAM\_B, CAM\_C, etc.
