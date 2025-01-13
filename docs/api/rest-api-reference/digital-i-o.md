# Digital I/O

**Digital inputs** receive signals from external devices like switches, sensors, or push buttons, indicating whether a condition is active or inactive (e.g., a door is open or closed). **Digital outputs** enable the PLC to control devices such as relays, lights, or solenoids by sending on/off signals to activate or deactivate them. These I/O channels are essential for processes that rely on clear, binary decisions, ensuring reliable control of equipment and systems in automated operations. The main difference between digital I/O and analog I/O is that digital I/O provides binary values (on/off, true/false, ...). Digital I/O API provides interface for controlling all digital inputs and outputs on your controller.

## API Reference

{% swagger src="../../.gitbook/assets/oas.yml" path="/controller/di" method="get" %}
[oas.yml](../../.gitbook/assets/oas.yml)
{% endswagger %}

{% swagger src="../../.gitbook/assets/oas.yml" path="/controller/di/{circuit}" method="get" %}
[oas.yml](../../.gitbook/assets/oas.yml)
{% endswagger %}

{% swagger src="../../.gitbook/assets/oas.yml" path="/controller/di/{circuit}" method="post" %}
[oas.yml](../../.gitbook/assets/oas.yml)
{% endswagger %}

{% swagger src="../../.gitbook/assets/oas.yml" path="/controller/di" method="post" %}
[oas.yml](../../.gitbook/assets/oas.yml)
{% endswagger %}

{% swagger src="../../.gitbook/assets/oas.yml" path="/controller/do" method="get" %}
[oas.yml](../../.gitbook/assets/oas.yml)
{% endswagger %}

{% swagger src="../../.gitbook/assets/oas.yml" path="/controller/do/{circuit}" method="get" %}
[oas.yml](../../.gitbook/assets/oas.yml)
{% endswagger %}

{% swagger src="../../.gitbook/assets/oas.yml" path="/controller/do/{circuit}" method="post" %}
[oas.yml](../../.gitbook/assets/oas.yml)
{% endswagger %}

{% swagger src="../../.gitbook/assets/oas.yml" path="/controller/do" method="post" %}
[oas.yml](../../.gitbook/assets/oas.yml)
{% endswagger %}
