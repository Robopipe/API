# Cameras

Camera is a basic building block of Robopipe. It represent a single Luxonis device that can be manipulated through our API. Each camera corresponds to a real camera device and is independent of other devices. Camera can be connected via USB or Ethernet interface, the API doesn't make any distinctions regarding this matter. Camera is always addressed by its unique [MXID](https://docs.luxonis.com/software/depthai/examples/device_information/).

{% hint style="warning" %}
If you're using PoE devices, make sure that they are connected to a network with running DHCP server. While this step can be ommited, the autodiscovery might be unreliable. If you run into any troubles connecting to PoE cameras, visit our [troubleshooting guide](../../other/troubleshooting.md), or refer to  [Luxonis PoE docs](https://docs.luxonis.com/hardware/platform/deploy/poe-deployment-guide/#PoE%20deployment%20guide-Initial%20Connection-Debugging).
{% endhint %}

## API Reference

{% openapi-operation spec="robopipe-api" path="/cameras/" method="get" %}
[OpenAPI robopipe-api](https://gitbook-x-prod-openapi.4401d86825a13bf607936cc3a9f3897a.r2.cloudflarestorage.com/raw/61c09c137433794c1f1727040fd632d7a56c4ad805d94fa4404486ea4c326b25.yaml?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Content-Sha256=UNSIGNED-PAYLOAD&X-Amz-Credential=dce48141f43c0191a2ad043a6888781c%2F20250718%2Fauto%2Fs3%2Faws4_request&X-Amz-Date=20250718T111324Z&X-Amz-Expires=172800&X-Amz-Signature=9a5482f6e9a1d554674b652e3c19284a32fc5fc1f3506011a1337170323ab66a&X-Amz-SignedHeaders=host&x-amz-checksum-mode=ENABLED&x-id=GetObject)
{% endopenapi-operation %}

{% openapi src="../../.gitbook/assets/spaces_TuTP9kHNw4UoUZQjsC6o_uploads_git-blob-9d61ed7a38f530cfdaca89fd71d55514141079c4_oas.yml" path="/cameras/{mxid}/" method="get" %}
[spaces_TuTP9kHNw4UoUZQjsC6o_uploads_git-blob-9d61ed7a38f530cfdaca89fd71d55514141079c4_oas.yml](../../.gitbook/assets/spaces_TuTP9kHNw4UoUZQjsC6o_uploads_git-blob-9d61ed7a38f530cfdaca89fd71d55514141079c4_oas.yml)
{% endopenapi %}

{% openapi src="../../.gitbook/assets/spaces_TuTP9kHNw4UoUZQjsC6o_uploads_git-blob-9d61ed7a38f530cfdaca89fd71d55514141079c4_oas.yml" path="/cameras/{mxid}/" method="post" %}
[spaces_TuTP9kHNw4UoUZQjsC6o_uploads_git-blob-9d61ed7a38f530cfdaca89fd71d55514141079c4_oas.yml](../../.gitbook/assets/spaces_TuTP9kHNw4UoUZQjsC6o_uploads_git-blob-9d61ed7a38f530cfdaca89fd71d55514141079c4_oas.yml)
{% endopenapi %}

{% openapi src="../../.gitbook/assets/spaces_TuTP9kHNw4UoUZQjsC6o_uploads_git-blob-9d61ed7a38f530cfdaca89fd71d55514141079c4_oas.yml" path="/cameras/{mxid}/" method="delete" %}
[spaces_TuTP9kHNw4UoUZQjsC6o_uploads_git-blob-9d61ed7a38f530cfdaca89fd71d55514141079c4_oas.yml](../../.gitbook/assets/spaces_TuTP9kHNw4UoUZQjsC6o_uploads_git-blob-9d61ed7a38f530cfdaca89fd71d55514141079c4_oas.yml)
{% endopenapi %}

{% openapi src="../../.gitbook/assets/spaces_TuTP9kHNw4UoUZQjsC6o_uploads_git-blob-9d61ed7a38f530cfdaca89fd71d55514141079c4_oas.yml" path="/cameras/{mxid}/stats" method="get" %}
[spaces_TuTP9kHNw4UoUZQjsC6o_uploads_git-blob-9d61ed7a38f530cfdaca89fd71d55514141079c4_oas.yml](../../.gitbook/assets/spaces_TuTP9kHNw4UoUZQjsC6o_uploads_git-blob-9d61ed7a38f530cfdaca89fd71d55514141079c4_oas.yml)
{% endopenapi %}

{% openapi src="../../.gitbook/assets/spaces_TuTP9kHNw4UoUZQjsC6o_uploads_git-blob-9d61ed7a38f530cfdaca89fd71d55514141079c4_oas.yml" path="/cameras/{mxid}/ir" method="get" %}
[spaces_TuTP9kHNw4UoUZQjsC6o_uploads_git-blob-9d61ed7a38f530cfdaca89fd71d55514141079c4_oas.yml](../../.gitbook/assets/spaces_TuTP9kHNw4UoUZQjsC6o_uploads_git-blob-9d61ed7a38f530cfdaca89fd71d55514141079c4_oas.yml)
{% endopenapi %}

{% openapi src="../../.gitbook/assets/spaces_TuTP9kHNw4UoUZQjsC6o_uploads_git-blob-9d61ed7a38f530cfdaca89fd71d55514141079c4_oas.yml" path="/cameras/{mxid}/ir" method="post" %}
[spaces_TuTP9kHNw4UoUZQjsC6o_uploads_git-blob-9d61ed7a38f530cfdaca89fd71d55514141079c4_oas.yml](../../.gitbook/assets/spaces_TuTP9kHNw4UoUZQjsC6o_uploads_git-blob-9d61ed7a38f530cfdaca89fd71d55514141079c4_oas.yml)
{% endopenapi %}

## IR Perception

The PRO line-up of Luxonis devices has notch IR filters at 940nm on the stereo camera pair, which allows both visible light and IR light from illumination LED/laser dot projector to be perceived by the camera.

{% hint style="warning" %}
This product is classified as a **Class 1 Laser Product** under the **EN/IEC 60825-1, Edition 3 (2014)** internationally. You should take safety precautions when working with this product.
{% endhint %}

{% hint style="info" %}
RGB cameras do not perceive IR light, only monochromatic sensors have IR perception.
{% endhint %}

### Dot Projector

A laser dot projector emits numerous tiny dots in front of the device, aiding in disparity matching, particularly on surfaces with low visual features or texture, such as walls or floors. This method, known as ASV (Active Stereo Vision), functions similarly to passive stereo vision but incorporates active depth enhancement.

### Flood IR (Led)

LED lighting enables visibility in environments with minimal or no light. It allows you to execute AI or computer vision (CV) tasks on frames illuminated by the infrared (IR) LED.

{% openapi src="../../.gitbook/assets/spaces_TuTP9kHNw4UoUZQjsC6o_uploads_git-blob-9d61ed7a38f530cfdaca89fd71d55514141079c4_oas.yml" path="/cameras/{mxid}/ir" method="get" %}
[spaces_TuTP9kHNw4UoUZQjsC6o_uploads_git-blob-9d61ed7a38f530cfdaca89fd71d55514141079c4_oas.yml](../../.gitbook/assets/spaces_TuTP9kHNw4UoUZQjsC6o_uploads_git-blob-9d61ed7a38f530cfdaca89fd71d55514141079c4_oas.yml)
{% endopenapi %}

{% openapi src="../../.gitbook/assets/spaces_TuTP9kHNw4UoUZQjsC6o_uploads_git-blob-9d61ed7a38f530cfdaca89fd71d55514141079c4_oas.yml" path="/cameras/{mxid}/ir" method="post" %}
[spaces_TuTP9kHNw4UoUZQjsC6o_uploads_git-blob-9d61ed7a38f530cfdaca89fd71d55514141079c4_oas.yml](../../.gitbook/assets/spaces_TuTP9kHNw4UoUZQjsC6o_uploads_git-blob-9d61ed7a38f530cfdaca89fd71d55514141079c4_oas.yml)
{% endopenapi %}
