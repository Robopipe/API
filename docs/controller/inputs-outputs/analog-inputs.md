# Analog inputs

**Analog inputs (AIs)** in Robopipe controllers are versatile and capable of measuring voltage, current, or resistance, depending on the device section and configuration. These inputs are wired through **AIx** or **AIy.x** terminals, with a common ground connection at **AGND**.

## Connection

* **Voltage/Current Measurements**:
  * Connect the positive pole of the measured device to the AI terminal
  * Connect the negative pole to the AGND terminal
* **Resistance Measurements**:
  * For **two-wire connections**, attach both sensor wires to the AI and AGND terminals
  * For **three-wire connections** (available only in Sections 2 and 3 or compatible units), the additional wire is used to compensate for measurement errors caused by wire resistance

{% hint style="info" %}
Section 1 analog inputs are limited to voltage and current measurements. Resistance measurements must be performed on Sections 2 and 3 or by utilizing analog outputs.
{% endhint %}

## Modes of Operation

### **Section 1 (AI1)**

* Supports **voltage** (0–10 V⎓) and **current** (0–20 mA) measurements.
* Factory default is **voltage measurement mode**.

### **Sections 2 and 3**

* Supports **voltage**, **current**, and **resistance** measurements.
* Measurement Modes:
  * 0–10 V⎓ voltage
  * 0–2.5 V⎓ voltage
  * 0–20 mA current
  * 0–1960 Ω resistance (three-wire)
  * 0–100 kΩ resistance (two-wire)

## Special Functions

### **Default Configuration**

* Saves the current section settings to memory
* Ensures continuity of configurations upon power cycling or reboot

### **Master Watchdog**

* Continuously monitors commands from the control application
* Reverts to safe default configurations (e.g., voltage measurement) if communication is lost, ensuring protection of connected devices

## Technical Specifications

| **Parameter**                  | **Section 1 (AI1)**    | **Sections 2/3, S5xx Units** |
| ------------------------------ | ---------------------- | ---------------------------- |
| **Input Terminals**            | AI                     | AI, AIS                      |
| **Common Ground**              | AGND                   | AGND                         |
| **Input Modes**                | 0–10 V⎓ voltage        | 0–10 V⎓ voltage              |
|                                | 0–20 mA current        | 0–2.5 V⎓ voltage             |
|                                |                        | 0–20 mA current              |
|                                |                        | 0–1960 Ω resistance (3-wire) |
|                                |                        | 0–100 kΩ resistance (2-wire) |
| **Max Input Voltage**          | 12 V DC                | 15 V DC                      |
| **Input Resistance (Voltage)** | 66 kΩ                  | 44 kΩ                        |
| **Input Resistance (Current)** | 100 Ω                  | 100 Ω                        |
| **Accuracy**                   | ±0.5 %                 | ±0.2 %                       |
| **Resolution**                 | 12 bits                | 16 bits (voltage/current)    |
|                                |                        | 24 bits (resistance)         |
| **Conversion Time**            | 10 μs                  | 60 μs (voltage/current)      |
|                                |                        | 400 ms (resistance)          |
| **Protection Type**            | Integrated overvoltage | Integrated overvoltage       |
| **Galvanic Isolation**         | No                     | Yes (from other sections\*)  |
