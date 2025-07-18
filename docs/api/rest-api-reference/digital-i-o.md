# Digital I/O

**Digital inputs** receive signals from external devices like switches, sensors, or push buttons, indicating whether a condition is active or inactive (e.g., a door is open or closed). **Digital outputs** enable the PLC to control devices such as relays, lights, or solenoids by sending on/off signals to activate or deactivate them. These I/O channels are essential for processes that rely on clear, binary decisions, ensuring reliable control of equipment and systems in automated operations. The main difference between digital I/O and analog I/O is that digital I/O provides binary values (on/off, true/false, ...). Digital I/O API provides interface for controlling all digital inputs and outputs on your controller.

## API Reference

{% openapi-operation spec="robopipe-api" path="/controller/di" method="get" %}
[OpenAPI robopipe-api](https://gitbook-x-prod-openapi.4401d86825a13bf607936cc3a9f3897a.r2.cloudflarestorage.com/raw/61c09c137433794c1f1727040fd632d7a56c4ad805d94fa4404486ea4c326b25.yaml?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Content-Sha256=UNSIGNED-PAYLOAD&X-Amz-Credential=dce48141f43c0191a2ad043a6888781c%2F20250718%2Fauto%2Fs3%2Faws4_request&X-Amz-Date=20250718T112050Z&X-Amz-Expires=172800&X-Amz-Signature=3f8b922c5752cb8f921b1ca0d273b0ccf15660c98a9201cc0f687e9a5d7f760c&X-Amz-SignedHeaders=host&x-amz-checksum-mode=ENABLED&x-id=GetObject)
{% endopenapi-operation %}

{% openapi-operation spec="robopipe-api" path="/controller/di/{circuit}" method="get" %}
[OpenAPI robopipe-api](https://gitbook-x-prod-openapi.4401d86825a13bf607936cc3a9f3897a.r2.cloudflarestorage.com/raw/61c09c137433794c1f1727040fd632d7a56c4ad805d94fa4404486ea4c326b25.yaml?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Content-Sha256=UNSIGNED-PAYLOAD&X-Amz-Credential=dce48141f43c0191a2ad043a6888781c%2F20250718%2Fauto%2Fs3%2Faws4_request&X-Amz-Date=20250718T112050Z&X-Amz-Expires=172800&X-Amz-Signature=3f8b922c5752cb8f921b1ca0d273b0ccf15660c98a9201cc0f687e9a5d7f760c&X-Amz-SignedHeaders=host&x-amz-checksum-mode=ENABLED&x-id=GetObject)
{% endopenapi-operation %}

{% openapi-operation spec="robopipe-api" path="/controller/di/{circuit}" method="post" %}
[OpenAPI robopipe-api](https://gitbook-x-prod-openapi.4401d86825a13bf607936cc3a9f3897a.r2.cloudflarestorage.com/raw/61c09c137433794c1f1727040fd632d7a56c4ad805d94fa4404486ea4c326b25.yaml?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Content-Sha256=UNSIGNED-PAYLOAD&X-Amz-Credential=dce48141f43c0191a2ad043a6888781c%2F20250718%2Fauto%2Fs3%2Faws4_request&X-Amz-Date=20250718T112051Z&X-Amz-Expires=172800&X-Amz-Signature=4d21029758779c17d573643c236e9f9069a5ee15193b1272c66a3df1100916b6&X-Amz-SignedHeaders=host&x-amz-checksum-mode=ENABLED&x-id=GetObject)
{% endopenapi-operation %}

{% openapi-operation spec="robopipe-api" path="/controller/di" method="post" %}
[OpenAPI robopipe-api](https://gitbook-x-prod-openapi.4401d86825a13bf607936cc3a9f3897a.r2.cloudflarestorage.com/raw/61c09c137433794c1f1727040fd632d7a56c4ad805d94fa4404486ea4c326b25.yaml?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Content-Sha256=UNSIGNED-PAYLOAD&X-Amz-Credential=dce48141f43c0191a2ad043a6888781c%2F20250718%2Fauto%2Fs3%2Faws4_request&X-Amz-Date=20250718T112051Z&X-Amz-Expires=172800&X-Amz-Signature=4d21029758779c17d573643c236e9f9069a5ee15193b1272c66a3df1100916b6&X-Amz-SignedHeaders=host&x-amz-checksum-mode=ENABLED&x-id=GetObject)
{% endopenapi-operation %}

{% openapi-operation spec="robopipe-api" path="/controller/do" method="get" %}
[OpenAPI robopipe-api](https://gitbook-x-prod-openapi.4401d86825a13bf607936cc3a9f3897a.r2.cloudflarestorage.com/raw/61c09c137433794c1f1727040fd632d7a56c4ad805d94fa4404486ea4c326b25.yaml?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Content-Sha256=UNSIGNED-PAYLOAD&X-Amz-Credential=dce48141f43c0191a2ad043a6888781c%2F20250718%2Fauto%2Fs3%2Faws4_request&X-Amz-Date=20250718T112051Z&X-Amz-Expires=172800&X-Amz-Signature=4d21029758779c17d573643c236e9f9069a5ee15193b1272c66a3df1100916b6&X-Amz-SignedHeaders=host&x-amz-checksum-mode=ENABLED&x-id=GetObject)
{% endopenapi-operation %}

{% openapi-operation spec="robopipe-api" path="/controller/do/{circuit}" method="get" %}
[OpenAPI robopipe-api](https://gitbook-x-prod-openapi.4401d86825a13bf607936cc3a9f3897a.r2.cloudflarestorage.com/raw/61c09c137433794c1f1727040fd632d7a56c4ad805d94fa4404486ea4c326b25.yaml?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Content-Sha256=UNSIGNED-PAYLOAD&X-Amz-Credential=dce48141f43c0191a2ad043a6888781c%2F20250718%2Fauto%2Fs3%2Faws4_request&X-Amz-Date=20250718T112051Z&X-Amz-Expires=172800&X-Amz-Signature=4d21029758779c17d573643c236e9f9069a5ee15193b1272c66a3df1100916b6&X-Amz-SignedHeaders=host&x-amz-checksum-mode=ENABLED&x-id=GetObject)
{% endopenapi-operation %}

{% openapi-operation spec="robopipe-api" path="/controller/do/{circuit}" method="post" %}
[OpenAPI robopipe-api](https://gitbook-x-prod-openapi.4401d86825a13bf607936cc3a9f3897a.r2.cloudflarestorage.com/raw/61c09c137433794c1f1727040fd632d7a56c4ad805d94fa4404486ea4c326b25.yaml?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Content-Sha256=UNSIGNED-PAYLOAD&X-Amz-Credential=dce48141f43c0191a2ad043a6888781c%2F20250718%2Fauto%2Fs3%2Faws4_request&X-Amz-Date=20250718T112051Z&X-Amz-Expires=172800&X-Amz-Signature=4d21029758779c17d573643c236e9f9069a5ee15193b1272c66a3df1100916b6&X-Amz-SignedHeaders=host&x-amz-checksum-mode=ENABLED&x-id=GetObject)
{% endopenapi-operation %}

{% openapi-operation spec="robopipe-api" path="/controller/do" method="post" %}
[OpenAPI robopipe-api](https://gitbook-x-prod-openapi.4401d86825a13bf607936cc3a9f3897a.r2.cloudflarestorage.com/raw/61c09c137433794c1f1727040fd632d7a56c4ad805d94fa4404486ea4c326b25.yaml?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Content-Sha256=UNSIGNED-PAYLOAD&X-Amz-Credential=dce48141f43c0191a2ad043a6888781c%2F20250718%2Fauto%2Fs3%2Faws4_request&X-Amz-Date=20250718T112051Z&X-Amz-Expires=172800&X-Amz-Signature=4d21029758779c17d573643c236e9f9069a5ee15193b1272c66a3df1100916b6&X-Amz-SignedHeaders=host&x-amz-checksum-mode=ENABLED&x-id=GetObject)
{% endopenapi-operation %}
