# Inputs/Outputs

## Digital inputs

**Digital input** in is a type of input signal that represents binary states: either **ON (1)** or **OFF (0)**. These inputs are typically used to detect the presence or absence of a signal or condition, in case of Robopipe controllers **voltage levels**, and translate it into a form the PLC can process. Use cases include:

* **Switch Detection** - Monitoring the state of push-buttons, limit switches, or toggle switches to start or stop processes
* **Proximity Sensors** - Detecting objects or positions using sensors that output digital signals (e.g., inductive or photoelectric sensors)
* **Safety Devices** - Receiving signals from emergency stop buttons or interlocks
* **System Feedback** - Monitoring signals like "door open/closed" or "motor running/stopped" from other components

All digital inputs on Robopipe controllers feature a counter functionality - are equipped with a counter that is able to detect long pulses as well as very short high-frequency pulses.

To read more about digital inputs, refer to the [digital inputs section](digital-inputs.md).

## Digital outputs

**Digital output** is a type of output signal that the PLC uses to control external devices by switching them **ON (1)** or **OFF (0)**. These outputs send binary signals, typically as voltage or current, to actuate connected devices. Only the power supply negative pole (GND) can be switched by DOs. Digital outputs on Robopipe controllers also feature [**PWM**](#user-content-fn-1)[^1], which means they can be used to generate variable-duty-cycle signal. Use cases include:

* **Actuator Control** - Turning solenoids, relays, or valves on or off to control mechanical systems
* **Indicator Lights** - Activating LEDs or other indicators to show machine status or alerts
* **Motor Starters** - Sending signals to start or stop motors via contactors
* **Alarms** - Triggering buzzers or warning devices in case of faults or specific conditions

To read more about digital outputs, refer to the [digital outputs section](digital-outputs.md).

## Relay outputs

**Relay output** uses electromechanical relays to control external devices. Unlike solid-state digital outputs, relay outputs provide electrical isolation between the control circuit and the load, making them versatile for switching various types of loads, including AC or DC devices. ROs on Robopipe controllers are rated for **maximum current of 5A at 230 V\~ or 30 V⎓**. Use cases include:

* **Motor Control** - Starting or stopping motors through contactors
* **Lighting** - Switching industrial or commercial lighting systems
* **Signal Conversion** - Controlling devices that require higher voltages or different types of current than the PLC itself can directly provide

To read more about relay outputs, refer to the [relay outputs section](relay-outputs.md).

## Analog inputs

**Analog input** is used to measure continuous signals, allowing the PLC to monitor variable parameters such as temperature, pressure, speed, or liquid level. Unlike digital inputs, which only detect ON/OFF states, analog inputs interpret a range of values, typically represented as voltage (e.g., 0–10 V), current (e.g., 4–20 mA), or resistance (e.g., from thermistors or RTDs). Use cases include:

* **Temperature Monitoring** - Using thermocouples or RTDs for real-time temperature data
* **Level Sensing** - Monitoring liquid levels in tanks via ultrasonic or pressure sensors
* **Speed or Position Feedback** - Interfacing with encoders or potentiometers for motion control

To read more about analog inputs, refer to the [analog inputs section](analog-inputs.md).

## Analog outputs

**Analog output** is used to send continuous signals to external devices, enabling the control of parameters like speed, position, or intensity. These outputs provide a range of values, typically as a voltage (e.g., 0–10 V) or current (e.g., 4–20 mA), to control actuators, drives, or other analog-responsive systems. Use cases include:

* **Motor Speed Control** - Sending a variable signal to a variable frequency drive (VFD) for precise motor speed adjustment
* **Valve Positioning** - Controlling valve actuators in fluid systems for flow or pressure regulation
* **Lighting Control** - Adjusting the brightness of lights in industrial or commercial settings

To read more about analog outputs, refer to the [analog outputs section](analog-outputs.md).

[^1]: Pulse Width Modulation
