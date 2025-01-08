# Digital inputs

Digital inputs are designed to detect binary logic states (TRUE/FALSE) and can also function as counters for applications like reading pulse data from meters or monitoring engine RPM. Additionally, the **DirectSwitch** function enables direct input-to-output connections for time-sensitive operations.

## **Indicating Logic States**

* **TRUE State** - When active (voltage between 7-35 V⎓), an LED corresponding to the input label lights up
* **FALSE State** - Voltage below 3 V⎓ indicates a FALSE state
* **Non-Defined State** - Voltage between 3-7 V⎓ is considered undefined

## Connection

* Each digital input connector has a common **DIGND** terminal for connecting the negative pole of the DC power supply
* The positive pole of the power supply is connected to the DI terminal (e.g., DIx or DIy.x) via the external device

{% hint style="info" %}
To maintain galvanic isolation, use a separate power supply for external devices connected to digital inputs.
{% endhint %}

## Special functions

### **Debounce**

* Filters out signal noise by requiring a signal to maintain a TRUE state for a specified duration before being processed.
* Configurable in increments of 100 µs (e.g., a value of 10 equals 1 ms).

### **Counter Input**

* High-speed counters register rising edges independently of the control software.
* Suitable for recording data from energy, water, or gas meters, as well as engine RPMs.
* Features 64-bit registers, resetting to 0 after exceeding 4,294,967,295 counts.
* Operates at frequencies up to 10 kHz, labeled as **CNT** inputs in Mervis IDE.

### **DirectSwitch**

* Allows direct mapping of digital inputs to digital or relay outputs for time-critical applications.
* Modes:
  * **Copy**: Output mirrors the input state.
  * **Inverse Copy**: Output is the negation of the input state.
  * **Switch**: Toggles the output state on an input's rising edge.
  * **Block**: Disables DirectSwitch.
* Only corresponding inputs and outputs (e.g., DIx.y and DOx.y) can be linked. Multiple outputs cannot share a single input.
* When in use, outputs cannot be controlled conventionally without setting the **ForceOutput** register to TRUE for 1 second.

### **Default Configuration**

Stores section settings for reloading after a power cycle or reboot:

* **Debounce** - 5 ms
* **DirectSwitch** - Disabled
* **Counter** - Resets to 0

### **Master Watchdog**

Ensures safe fallback configurations by monitoring application commands. If commands are absent within a set timeout, the module reboots and reverts to default settings, minimizing risks during software or hardware failures.

## Technical Specifications

| Parameter                           | Value   |
| ----------------------------------- | ------- |
| Input Type                          | SINK    |
| Input Terminal                      | DI      |
| Common Ground                       | DIGND   |
| Maximum Voltage for FALSE           | 3 V⎓    |
| Minimum Voltage for TRUE            | 7 V⎓    |
| Maximum Voltage                     | 35 V⎓   |
| Non-Defined Voltage Range           | 3-7 V⎓  |
| Input Resistance (TRUE State)       | 6,200 Ω |
| Voltage Drop on DI Diode            | 1.2 V   |
| Minimum Pulse Length                | 20 µs   |
| FALSE → TRUE Delay                  | 20 µs   |
| TRUE → FALSE Delay                  | 60 µs   |
| Maximum CNT Frequency               | 10 kHz  |
| Galvanic Isolation (Between Groups) | Yes     |
| Insulation Voltage                  | 2,000 V |
