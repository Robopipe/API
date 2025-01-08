# Relay outputs

Relay outputs in Robopipe controllers are used for switching two-state devices and support both AC and DC voltages. Connections are made through **ROx** or **ROy.x** terminals alongside a shared **COM** terminal. The **COM** terminal enables the switching of voltage to the respective relay output. Relays are **normally open (NO)** by default, meaning there is no connection between the **COM** and **RO** terminals unless the relay is activated.

Each relay’s status (On/Off) is displayed via a corresponding LED indicator. Protection against overloads and overvoltage should be implemented externally, typically with a dedicated circuit breaker for each output. The breaker specifications should align with the load's characteristics.

{% hint style="warning" %}
**Protection Measures**

* **Inductive Loads** (e.g., motors, relay coils, contactors):\
  Protect the relay using a suitable external component like a varistor, RC circuit, or diode to prevent voltage spikes.
* **Capacitive Loads** (e.g., LED power supplies):\
  Use an appropriate thermistor at the relay's output to handle inrush currents and safeguard relay contacts.
{% endhint %}

## Connection

* Connect the **COM** terminal to the voltage source or desired power connection
* Attach the load to the corresponding **RO** terminal
* For inductive or capacitive loads, ensure additional external protection (e.g., varistor or thermistor)

## **Special Functions**

### **DirectSwitch**

* DirectSwitch links digital inputs to relay or digital outputs, enabling rapid response independent of control software.
* Modes:
  * **Copy** - Output replicates the input state
  * **Inverse Copy** - Output state is the logical negation of the input state
  * **Switch** - Toggles the output state on the input’s rising edge
  * **Block** - Deactivates DirectSwitch

#### **Key Notes**:

* DirectSwitch requires matching input and output labels (e.g., **DIy.x** and **ROy.x**)
* DirectSwitch cannot simultaneously control multiple outputs or mismatched labels
* When DirectSwitch is active, manual output control is disabled unless the **ForceOutput** register is temporarily set to TRUE

### **Default Configuration**

Relay outputs revert to stored settings after a reboot or power cycle.

| Parameter    | Default Setting |
| ------------ | --------------- |
| Output Value | FALSE           |

### **Master Watchdog**

The **Master Watchdog** monitors software activity and automatically reverts relay outputs to safe defaults if no commands are detected within a set timeout period. This mechanism prevents damage or hazards caused by communication failures, hardware issues, or software errors.

## Technical Specifications

| Parameter                        | Specification                           |
| -------------------------------- | --------------------------------------- |
| **Output Type**                  | Electromechanical, non-shielded         |
| **Output Terminal**              | RO                                      |
| **Common Terminal**              | COM                                     |
| **Contact Type**                 | Normally Open (SPST-NO)                 |
| **Relay Model**                  | FTR-F3AA024E-HA                         |
| **Max Switching Voltage**        | 250 V AC / 30 V DC                      |
| **Max Switching Current**        | 5 A                                     |
| **Max Common Terminal Current**  | 10 A                                    |
| **Short-Term Current Overload**  | 5 A                                     |
| **Mechanical Lifespan**          | 5,000,000 cycles                        |
| **Electrical Lifespan**          | Up to 100,000 cycles                    |
| **Operate/Release Time**         | 10 ms                                   |
| **Designed Load Type**           | Resistive                               |
| **External Protection Required** | RC circuit, varistor, diode, thermistor |
| **Short Circuit Protection**     | No                                      |
| **Overvoltage Protection**       | No                                      |
| **Galvanic Isolation**           | Yes                                     |
| **Insulation Voltage**           | 4,000 V                                 |
