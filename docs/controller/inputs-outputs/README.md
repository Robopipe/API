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

**Digital output** is a type of output signal that the PLC uses to control external devices by switching them **ON (1)** or **OFF (0)**. These outputs send binary signals, typically as voltage or current, to actuate connected devices.

* **Actuator Control** - Turning solenoids, relays, or valves on or off to control mechanical systems.
* **Indicator Lights** - Activating LEDs or other indicators to show machine status or alerts.
* **Motor Starters** - Sending signals to start or stop motors via contactors.
* **Alarms** - Triggering buzzers or warning devices in case of faults or specific conditions.
