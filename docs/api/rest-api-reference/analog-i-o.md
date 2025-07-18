# Analog I/O

**Analog inputs** allow the PLC to read variable values from sensors, such as temperature, pressure, or flow, by converting physical measurements into electrical signals, typically in the form of _voltage_ (e.g., 0-10V) or _current_ (e.g., 4-20mA). Conversely, **analog outputs** enable the PLC to control devices like motors, valves, or actuators by sending continuous electrical signals to adjust their operation with precision. These I/O channels are crucial for processes that require more than simple on/off control, providing fine-tuned adjustments to optimize performance in dynamic environments. Analog I/O API provides interface for controlling all analog inputs and outputs on your controller.

## API Reference

{% openapi-operation spec="robopipe-api" path="/controller/ai" method="get" %}
[OpenAPI robopipe-api](https://gitbook-x-prod-openapi.4401d86825a13bf607936cc3a9f3897a.r2.cloudflarestorage.com/raw/61c09c137433794c1f1727040fd632d7a56c4ad805d94fa4404486ea4c326b25.yaml?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Content-Sha256=UNSIGNED-PAYLOAD&X-Amz-Credential=dce48141f43c0191a2ad043a6888781c%2F20250718%2Fauto%2Fs3%2Faws4_request&X-Amz-Date=20250718T112050Z&X-Amz-Expires=172800&X-Amz-Signature=3f8b922c5752cb8f921b1ca0d273b0ccf15660c98a9201cc0f687e9a5d7f760c&X-Amz-SignedHeaders=host&x-amz-checksum-mode=ENABLED&x-id=GetObject)
{% endopenapi-operation %}

{% openapi-operation spec="robopipe-api" path="/controller/ai/{circuit}" method="get" %}
[OpenAPI robopipe-api](https://gitbook-x-prod-openapi.4401d86825a13bf607936cc3a9f3897a.r2.cloudflarestorage.com/raw/61c09c137433794c1f1727040fd632d7a56c4ad805d94fa4404486ea4c326b25.yaml?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Content-Sha256=UNSIGNED-PAYLOAD&X-Amz-Credential=dce48141f43c0191a2ad043a6888781c%2F20250718%2Fauto%2Fs3%2Faws4_request&X-Amz-Date=20250718T112050Z&X-Amz-Expires=172800&X-Amz-Signature=3f8b922c5752cb8f921b1ca0d273b0ccf15660c98a9201cc0f687e9a5d7f760c&X-Amz-SignedHeaders=host&x-amz-checksum-mode=ENABLED&x-id=GetObject)
{% endopenapi-operation %}

{% openapi-operation spec="robopipe-api" path="/controller/ai/{circuit}" method="post" %}
[OpenAPI robopipe-api](https://gitbook-x-prod-openapi.4401d86825a13bf607936cc3a9f3897a.r2.cloudflarestorage.com/raw/61c09c137433794c1f1727040fd632d7a56c4ad805d94fa4404486ea4c326b25.yaml?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Content-Sha256=UNSIGNED-PAYLOAD&X-Amz-Credential=dce48141f43c0191a2ad043a6888781c%2F20250718%2Fauto%2Fs3%2Faws4_request&X-Amz-Date=20250718T112050Z&X-Amz-Expires=172800&X-Amz-Signature=3f8b922c5752cb8f921b1ca0d273b0ccf15660c98a9201cc0f687e9a5d7f760c&X-Amz-SignedHeaders=host&x-amz-checksum-mode=ENABLED&x-id=GetObject)
{% endopenapi-operation %}

{% openapi-operation spec="robopipe-api" path="/controller/ai" method="post" %}
[OpenAPI robopipe-api](https://gitbook-x-prod-openapi.4401d86825a13bf607936cc3a9f3897a.r2.cloudflarestorage.com/raw/61c09c137433794c1f1727040fd632d7a56c4ad805d94fa4404486ea4c326b25.yaml?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Content-Sha256=UNSIGNED-PAYLOAD&X-Amz-Credential=dce48141f43c0191a2ad043a6888781c%2F20250718%2Fauto%2Fs3%2Faws4_request&X-Amz-Date=20250718T112050Z&X-Amz-Expires=172800&X-Amz-Signature=3f8b922c5752cb8f921b1ca0d273b0ccf15660c98a9201cc0f687e9a5d7f760c&X-Amz-SignedHeaders=host&x-amz-checksum-mode=ENABLED&x-id=GetObject)
{% endopenapi-operation %}

{% openapi-operation spec="robopipe-api" path="/controller/ao" method="get" %}
[OpenAPI robopipe-api](https://gitbook-x-prod-openapi.4401d86825a13bf607936cc3a9f3897a.r2.cloudflarestorage.com/raw/61c09c137433794c1f1727040fd632d7a56c4ad805d94fa4404486ea4c326b25.yaml?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Content-Sha256=UNSIGNED-PAYLOAD&X-Amz-Credential=dce48141f43c0191a2ad043a6888781c%2F20250718%2Fauto%2Fs3%2Faws4_request&X-Amz-Date=20250718T112050Z&X-Amz-Expires=172800&X-Amz-Signature=3f8b922c5752cb8f921b1ca0d273b0ccf15660c98a9201cc0f687e9a5d7f760c&X-Amz-SignedHeaders=host&x-amz-checksum-mode=ENABLED&x-id=GetObject)
{% endopenapi-operation %}

{% openapi-operation spec="robopipe-api" path="/controller/ao/{circuit}" method="get" %}
[OpenAPI robopipe-api](https://gitbook-x-prod-openapi.4401d86825a13bf607936cc3a9f3897a.r2.cloudflarestorage.com/raw/61c09c137433794c1f1727040fd632d7a56c4ad805d94fa4404486ea4c326b25.yaml?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Content-Sha256=UNSIGNED-PAYLOAD&X-Amz-Credential=dce48141f43c0191a2ad043a6888781c%2F20250718%2Fauto%2Fs3%2Faws4_request&X-Amz-Date=20250718T112050Z&X-Amz-Expires=172800&X-Amz-Signature=3f8b922c5752cb8f921b1ca0d273b0ccf15660c98a9201cc0f687e9a5d7f760c&X-Amz-SignedHeaders=host&x-amz-checksum-mode=ENABLED&x-id=GetObject)
{% endopenapi-operation %}

{% openapi-operation spec="robopipe-api" path="/controller/ao/{circuit}" method="post" %}
[OpenAPI robopipe-api](https://gitbook-x-prod-openapi.4401d86825a13bf607936cc3a9f3897a.r2.cloudflarestorage.com/raw/61c09c137433794c1f1727040fd632d7a56c4ad805d94fa4404486ea4c326b25.yaml?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Content-Sha256=UNSIGNED-PAYLOAD&X-Amz-Credential=dce48141f43c0191a2ad043a6888781c%2F20250718%2Fauto%2Fs3%2Faws4_request&X-Amz-Date=20250718T112050Z&X-Amz-Expires=172800&X-Amz-Signature=3f8b922c5752cb8f921b1ca0d273b0ccf15660c98a9201cc0f687e9a5d7f760c&X-Amz-SignedHeaders=host&x-amz-checksum-mode=ENABLED&x-id=GetObject)
{% endopenapi-operation %}

{% openapi-operation spec="robopipe-api" path="/controller/ao" method="post" %}
[OpenAPI robopipe-api](https://gitbook-x-prod-openapi.4401d86825a13bf607936cc3a9f3897a.r2.cloudflarestorage.com/raw/61c09c137433794c1f1727040fd632d7a56c4ad805d94fa4404486ea4c326b25.yaml?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Content-Sha256=UNSIGNED-PAYLOAD&X-Amz-Credential=dce48141f43c0191a2ad043a6888781c%2F20250718%2Fauto%2Fs3%2Faws4_request&X-Amz-Date=20250718T112050Z&X-Amz-Expires=172800&X-Amz-Signature=3f8b922c5752cb8f921b1ca0d273b0ccf15660c98a9201cc0f687e9a5d7f760c&X-Amz-SignedHeaders=host&x-amz-checksum-mode=ENABLED&x-id=GetObject)
{% endopenapi-operation %}
