# Analog outputs

**Analog outputs (AOs)** in Robopipe controllers are designed for controlling external devices such as valves, heat exchangers, or other actuators requiring analog voltage or current signals. These outputs provide precise signal regulation for various applications.

## Connection

* **Voltage Output (AOV)**:\
  Connect the positive terminal of the external device to **AOVx** or **AOVy.x** and the common ground to **AGND**
* **Current Output (AOR)**:\
  Connect the positive terminal of the external device to **AORx** or **AORy.x** and the common ground to **AGND**

{% hint style="warning" %}
Ensure no short circuits or prolonged overloading occurs, as these may cause permanent damage to the analog output, leading to errors or complete output failure.
{% endhint %}

## Modes of Operation

### **Section 1 Analog Outputs (AOR)**

* **Voltage Mode** - Provides a signal range of **0–10 V⎓**
* **Current Mode** - Provides a signal range of **0–20 mA**
* **Resistance Measurement** - Supports resistance sensors like PT1000 (up to **1960 Ω**)

#### Configuration:

* Select the desired mode via software (e.g., Mervis, EVOK)
* Output values are controlled by entering the corresponding signal value in software

### **Sections 2, 3**

* **Voltage Mode Only** - Provides a signal range of **0–10 V⎓**

#### Configuration:

* Enter the required output value in software (e.g., 0–4000, corresponding linearly to 0–10 V⎓)

## Special Functions

### **Default Configuration**

* Saves the current settings for the section into memory
* Restores the settings after power cycling or reboot

#### Default Values:

* **Output Mode**: Voltage output
* **Output Value**: 0 V⎓

### **Master Watchdog**

* Monitors communication between the unit and the control application
* Reverts to default configuration if communication is lost, ensuring connected devices are protected

## Technical Specifications

| **Parameter**              | **Section 1 (AOR)**               | **Sections 2/3, S5xx Units (AOV)** |
| -------------------------- | --------------------------------- | ---------------------------------- |
| **Output Terminals**       | AOR                               | AOV                                |
| **Common Conductor**       | AGND                              | AGND                               |
| **Output Modes**           | 0–10 V⎓ voltage                   | 0–10 V⎓ voltage                    |
|                            | 0–20 mA current                   | —                                  |
|                            | Resistance measurement (0–1960 Ω) | —                                  |
| **Output Voltage Range**   | 0–10 V⎓                           | 0–10 V⎓                            |
| **Output Current Range**   | 0–20 mA                           | —                                  |
| **Maximum Output Current** | 20 mA                             | 20 mA                              |
| **Accuracy**               | ±0.5 %                            | ±0.5 %                             |
| **Resolution**             | 12 bits                           | 12 bits                            |
| **Conversion Time**        | 1 ms                              | 300 μs                             |
| **Protection Type**        | Integrated overvoltage            | Integrated overvoltage             |
| **Galvanic Isolation**     | No                                | Yes (from other sections\*)        |
