# Analog I/O

**Analog inputs** allow the PLC to read variable values from sensors, such as temperature, pressure, or flow, by converting physical measurements into electrical signals, typically in the form of _voltage_ (e.g., 0-10V) or _current_ (e.g., 4-20mA). Conversely, **analog outputs** enable the PLC to control devices like motors, valves, or actuators by sending continuous electrical signals to adjust their operation with precision. These I/O channels are crucial for processes that require more than simple on/off control, providing fine-tuned adjustments to optimize performance in dynamic environments. Analog I/O API provides interface for controlling all analog inputs and outputs on your controller.

{% swagger src="../../.gitbook/assets/oas.yaml" path="/controller/ai" method="get" %}
[oas.yaml](../../.gitbook/assets/oas.yaml)
{% endswagger %}

{% swagger src="../../.gitbook/assets/oas.yaml" path="/controller/ai" method="post" %}
[oas.yaml](../../.gitbook/assets/oas.yaml)
{% endswagger %}

{% swagger src="../../.gitbook/assets/oas.yaml" path="/controller/ai/{circuit}" method="get" %}
[oas.yaml](../../.gitbook/assets/oas.yaml)
{% endswagger %}

{% swagger src="../../.gitbook/assets/oas.yaml" path="/controller/ai/{circuit}" method="post" %}
[oas.yaml](../../.gitbook/assets/oas.yaml)
{% endswagger %}

{% swagger src="../../.gitbook/assets/oas.yaml" path="/controller/ao" method="get" %}
[oas.yaml](../../.gitbook/assets/oas.yaml)
{% endswagger %}

{% swagger src="../../.gitbook/assets/oas.yaml" path="/controller/ao" method="post" %}
[oas.yaml](../../.gitbook/assets/oas.yaml)
{% endswagger %}

{% swagger src="../../.gitbook/assets/oas.yaml" path="/controller/ao/{circuit}" method="get" %}
[oas.yaml](../../.gitbook/assets/oas.yaml)
{% endswagger %}

{% swagger src="../../.gitbook/assets/oas.yaml" path="/controller/ao/{circuit}" method="post" %}
[oas.yaml](../../.gitbook/assets/oas.yaml)
{% endswagger %}
