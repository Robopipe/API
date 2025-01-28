# Streams

Each camera contains a number of sensors of different types. Each sensor (or combination of multiple sensors) provides an image **stream** which can be consumed directly as video stream, or fed as input into a neural network. Our API exposes operations through which these **streams** can be consumed or manipulated. Each stream is addresses either by its sensor name  - CAM\_(A-H)[^1] or by its combined name - DEPTH\_(A-H)\_(A-H)[^2]_._

## Depth API

Some camera models containing multiple image sensors, support a feature called _Stereo Depth_. This feature combines data from two image sensors at a time, to calculate the depth of the image in front of it. The result is a single image stream. The image will consist of depth data calculated by the camera, lighter areas will contain objects that are closer to the camera while darker areas will contain objects further away. This stream is configurable the same way as a single sensor.

{% hint style="info" %}
Depth stream and the respective sensors it uses cannot be both active at the same time. E.g. if stream DEPTH\_B\_C is active, then streams CAM\_B and CAM\_C will be inactive and vice versa.
{% endhint %}

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

    CAM\_B, CAM\_C, ... depending on you camera model.

[^2]: The first and second capital letters A-H in the stream name correspond to the left and right image sensor respectively.
