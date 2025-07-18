# Streams

Each camera contains a number of sensors of different types. Each sensor (or combination of multiple sensors) provides an image **stream** which can be consumed directly as video stream, or fed as input into a neural network. Our API exposes operations through which these **streams** can be consumed or manipulated. Each stream is addresses either by its sensor name  - CAM\_(A-H)[^1] or by its combined name - DEPTH\_(A-H)\_(A-H)[^2]_._

## Depth API

Some camera models containing multiple image sensors, support a feature called _Stereo Depth_. This feature combines data from two image sensors at a time, to calculate the depth of the image in front of it. The result is a single image stream. The image will consist of depth data calculated by the camera, lighter areas will contain objects that are closer to the camera while darker areas will contain objects further away. This stream is configurable the same way as a single sensor.

{% hint style="info" %}
Depth stream and the respective sensors it uses cannot be both active at the same time. E.g. if stream DEPTH\_B\_C is active, then streams CAM\_B and CAM\_C will be inactive and vice versa.
{% endhint %}

## API Reference

{% openapi-operation spec="robopipe-api" path="/cameras/{mxid}/streams/" method="get" %}
[OpenAPI robopipe-api](https://gitbook-x-prod-openapi.4401d86825a13bf607936cc3a9f3897a.r2.cloudflarestorage.com/raw/61c09c137433794c1f1727040fd632d7a56c4ad805d94fa4404486ea4c326b25.yaml?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Content-Sha256=UNSIGNED-PAYLOAD&X-Amz-Credential=dce48141f43c0191a2ad043a6888781c%2F20250718%2Fauto%2Fs3%2Faws4_request&X-Amz-Date=20250718T112051Z&X-Amz-Expires=172800&X-Amz-Signature=4d21029758779c17d573643c236e9f9069a5ee15193b1272c66a3df1100916b6&X-Amz-SignedHeaders=host&x-amz-checksum-mode=ENABLED&x-id=GetObject)
{% endopenapi-operation %}

{% openapi-operation spec="robopipe-api" path="/cameras/{mxid}/streams/{stream_name}/" method="post" %}
[OpenAPI robopipe-api](https://gitbook-x-prod-openapi.4401d86825a13bf607936cc3a9f3897a.r2.cloudflarestorage.com/raw/61c09c137433794c1f1727040fd632d7a56c4ad805d94fa4404486ea4c326b25.yaml?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Content-Sha256=UNSIGNED-PAYLOAD&X-Amz-Credential=dce48141f43c0191a2ad043a6888781c%2F20250718%2Fauto%2Fs3%2Faws4_request&X-Amz-Date=20250718T112051Z&X-Amz-Expires=172800&X-Amz-Signature=4d21029758779c17d573643c236e9f9069a5ee15193b1272c66a3df1100916b6&X-Amz-SignedHeaders=host&x-amz-checksum-mode=ENABLED&x-id=GetObject)
{% endopenapi-operation %}

{% openapi-operation spec="robopipe-api" path="/cameras/{mxid}/streams/{stream_name}/" method="delete" %}
[OpenAPI robopipe-api](https://gitbook-x-prod-openapi.4401d86825a13bf607936cc3a9f3897a.r2.cloudflarestorage.com/raw/61c09c137433794c1f1727040fd632d7a56c4ad805d94fa4404486ea4c326b25.yaml?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Content-Sha256=UNSIGNED-PAYLOAD&X-Amz-Credential=dce48141f43c0191a2ad043a6888781c%2F20250718%2Fauto%2Fs3%2Faws4_request&X-Amz-Date=20250718T112051Z&X-Amz-Expires=172800&X-Amz-Signature=4d21029758779c17d573643c236e9f9069a5ee15193b1272c66a3df1100916b6&X-Amz-SignedHeaders=host&x-amz-checksum-mode=ENABLED&x-id=GetObject)
{% endopenapi-operation %}

{% openapi-operation spec="robopipe-api" path="/cameras/{mxid}/streams/{stream_name}/config" method="get" %}
[OpenAPI robopipe-api](https://gitbook-x-prod-openapi.4401d86825a13bf607936cc3a9f3897a.r2.cloudflarestorage.com/raw/61c09c137433794c1f1727040fd632d7a56c4ad805d94fa4404486ea4c326b25.yaml?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Content-Sha256=UNSIGNED-PAYLOAD&X-Amz-Credential=dce48141f43c0191a2ad043a6888781c%2F20250718%2Fauto%2Fs3%2Faws4_request&X-Amz-Date=20250718T112051Z&X-Amz-Expires=172800&X-Amz-Signature=4d21029758779c17d573643c236e9f9069a5ee15193b1272c66a3df1100916b6&X-Amz-SignedHeaders=host&x-amz-checksum-mode=ENABLED&x-id=GetObject)
{% endopenapi-operation %}

{% openapi-operation spec="robopipe-api" path="/cameras/{mxid}/streams/{stream_name}/config" method="post" %}
[OpenAPI robopipe-api](https://gitbook-x-prod-openapi.4401d86825a13bf607936cc3a9f3897a.r2.cloudflarestorage.com/raw/61c09c137433794c1f1727040fd632d7a56c4ad805d94fa4404486ea4c326b25.yaml?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Content-Sha256=UNSIGNED-PAYLOAD&X-Amz-Credential=dce48141f43c0191a2ad043a6888781c%2F20250718%2Fauto%2Fs3%2Faws4_request&X-Amz-Date=20250718T112051Z&X-Amz-Expires=172800&X-Amz-Signature=4d21029758779c17d573643c236e9f9069a5ee15193b1272c66a3df1100916b6&X-Amz-SignedHeaders=host&x-amz-checksum-mode=ENABLED&x-id=GetObject)
{% endopenapi-operation %}

{% openapi-operation spec="robopipe-api" path="/cameras/{mxid}/streams/{stream_name}/control" method="get" %}
[OpenAPI robopipe-api](https://gitbook-x-prod-openapi.4401d86825a13bf607936cc3a9f3897a.r2.cloudflarestorage.com/raw/61c09c137433794c1f1727040fd632d7a56c4ad805d94fa4404486ea4c326b25.yaml?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Content-Sha256=UNSIGNED-PAYLOAD&X-Amz-Credential=dce48141f43c0191a2ad043a6888781c%2F20250718%2Fauto%2Fs3%2Faws4_request&X-Amz-Date=20250718T112051Z&X-Amz-Expires=172800&X-Amz-Signature=4d21029758779c17d573643c236e9f9069a5ee15193b1272c66a3df1100916b6&X-Amz-SignedHeaders=host&x-amz-checksum-mode=ENABLED&x-id=GetObject)
{% endopenapi-operation %}

{% openapi-operation spec="robopipe-api" path="/cameras/{mxid}/streams/{stream_name}/control" method="post" %}
[OpenAPI robopipe-api](https://gitbook-x-prod-openapi.4401d86825a13bf607936cc3a9f3897a.r2.cloudflarestorage.com/raw/61c09c137433794c1f1727040fd632d7a56c4ad805d94fa4404486ea4c326b25.yaml?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Content-Sha256=UNSIGNED-PAYLOAD&X-Amz-Credential=dce48141f43c0191a2ad043a6888781c%2F20250718%2Fauto%2Fs3%2Faws4_request&X-Amz-Date=20250718T112051Z&X-Amz-Expires=172800&X-Amz-Signature=4d21029758779c17d573643c236e9f9069a5ee15193b1272c66a3df1100916b6&X-Amz-SignedHeaders=host&x-amz-checksum-mode=ENABLED&x-id=GetObject)
{% endopenapi-operation %}

{% openapi-operation spec="robopipe-api" path="/cameras/{mxid}/streams/{stream_name}/still" method="get" %}
[OpenAPI robopipe-api](https://gitbook-x-prod-openapi.4401d86825a13bf607936cc3a9f3897a.r2.cloudflarestorage.com/raw/61c09c137433794c1f1727040fd632d7a56c4ad805d94fa4404486ea4c326b25.yaml?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Content-Sha256=UNSIGNED-PAYLOAD&X-Amz-Credential=dce48141f43c0191a2ad043a6888781c%2F20250718%2Fauto%2Fs3%2Faws4_request&X-Amz-Date=20250718T112051Z&X-Amz-Expires=172800&X-Amz-Signature=4d21029758779c17d573643c236e9f9069a5ee15193b1272c66a3df1100916b6&X-Amz-SignedHeaders=host&x-amz-checksum-mode=ENABLED&x-id=GetObject)
{% endopenapi-operation %}

[^1]: This means that there are up to **8**

    available sensor, with names CAM\_A,

    CAM\_B, CAM\_C, ... depending on you camera model.

[^2]: The first and second capital letters A-H in the stream name correspond to the left and right image sensor respectively.
