# Digital outputs

Digital outputs in Robopipe controllers function as open collector switches, using the negative pole of a connected power source to control external loads. Outputs are wired to **DOx** or **DOy.x** terminals, with a common **DOGND** terminal for connecting the negative pole of the DC power source. Each output is represented by an LED indicator that lights up when the output is active.

The **FBD** terminal can provide additional protection for specific load types, as detailed below.

## Connection

* Connect the **DOGND** terminal to the negative pole of the DC power source.
* The external device or load connects between the power source’s positive pole and the appropriate **DO** terminal.

### **Flyback Diode (FBD)**

For inductive loads (e.g., relays or contactors), use the integrated flyback diode available on the **FBD** terminal to suppress voltage spikes.

{% hint style="warning" %}
The flyback diode is intended for devices within the same output group. Using it across groups or for other purposes may cause permanent damage to the device.
{% endhint %}

## Special functions

### **Pulse Width Modulation (PWM)**

* Generates a rectangular signal with a specified frequency and duty cycle
* Common applications include controlling heating elements, LEDs, and motors via SSR relays
* PWM is ideal for efficiently transmitting analog-like signals (e.g., 0-100% intensity or power)

### **DirectSwitch**

* Links digital inputs to outputs for time-sensitive applications without requiring control software
* Modes:
  * **Copy** - Output mirrors input state
  * **Inverse Copy** - Output state is the negation of the input
  * **Switch** - Toggles output state on an input’s rising edge
  * **Block** - Disables DirectSwitch for the output

### **Important Notes**:

* Inputs and outputs must share corresponding labels (e.g., **DIy.x** with **DOy.x**)
* Outputs controlled by DirectSwitch cannot be manually written to unless the **ForceOutput** register is set to TRUE for approximately one second

### **Default Configuration**

Stored configurations allow outputs to resume a predefined state after a power cycle or reboot.

| Parameter         | Default Setting | Calculated Values |
| ----------------- | --------------- | ----------------- |
| Output Value      | FALSE           |                   |
| PWM Configuration | Off             | Frequency: 10 kHz |
|                   | Duty Cycle: 0   | Resolution: 4800  |
|                   |                 | Step: 0.02%       |

### **Master Watchdog**

The **Master Watchdog** monitors software commands and ensures outputs revert to a safe default configuration if no commands are detected within a preset timeout. This prevents potential damage to devices or hazards to personnel in case of hardware or software failure.

## Technical Specifications

| Parameter                            | Value                       |
| ------------------------------------ | --------------------------- |
| Output Type                          | SINK (NPN - open collector) |
| Output Terminals                     | DO                          |
| Common Ground                        | DOGND                       |
| Switching Voltage                    | 5–50 V DC                   |
| Switching Current (Continuous/Pulse) | 750 mA / 1 A                |
| Max Total Group Load                 | 1 A                         |
| Inductive Load Handling              | Integrated FBD Diode        |
| Switching Period (Open/Close)        | 130 ns / 20 ns              |
| Maximum PWM Resolution               | 16 bits                     |
| Maximum PWM Frequency                | 200 kHz                     |
| Galvanic Isolation                   | No                          |
