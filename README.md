# FPGA-Insight

An AI-driven desktop application for real-time FPGA register monitoring and anomaly detection.

---

## Overview

FPGA-Insight provides a graphical interface for observing, controlling, and diagnosing the internal state of an FPGA peripheral. It simulates a register-mapped FPGA device and runs a machine learning model in the background to detect abnormal behaviour automatically - without any labelled fault data required.

The project demonstrates skills in GUI development, embedded systems concepts, AI integration, and Python software engineering.

---

## Features

- Register Map: A 12-entry editable register map with read-only protection, hex and decimal views, and CSV export.
- Signal Monitor: A live four-channel oscilloscope showing CLK, GPIO, ADC, and VOLTAGE signals, refreshing every 250 ms.
- AI Diagnostics: An Isolation Forest model that trains on normal operation, then detects and scores anomalies in real time.
- NLP Command Interface: A plain-English command bar for controlling the device without touching the register table.
- Alert Log: A timestamped log of WARNING and CRITICAL events with colour-coded severity.
- Fault Injection: A one-click button to simulate an FPGA fault and demonstrate AI detection live.

---

## Project Structure

```
fpga_insight/
- main.py
- README.md
- core/
  - fpga_sim.py
  - ai_engine.py
  - nlp_parser.py
- ui/
  - app.py
```

- core/fpga_sim.py: Hardware simulator: register map, signal generation, sensor ticking.
- core/ai_engine.py: Isolation Forest anomaly detector with online scoring.
- core/nlp_parser.py: Regex-based natural language command parser.
- ui/app.py: Tkinter GUI: status bar, three-tab notebook, NLP command bar, console.

---

## How It Works

### FPGA Simulation

The simulator maintains a 12-register memory map modelled after a real register-mapped peripheral. Registers include a control register, GPIO direction and output latches, a clock divider, interrupt mask, temperature and voltage sensors, and a power management register.

Writing to the clock divider register changes the simulated clock frequency. Writing 0 to the power management register puts the device into sleep mode. Read-only registers reject writes.

Four signal channels are generated on every refresh frame using NumPy. When fault injection is active, noise scales up and the clock frequency shifts, replicating glitch behaviour.

### AI Anomaly Detection

The detector uses scikit-learn's Isolation Forest - an unsupervised algorithm well-suited to this problem because labelled fault data is rarely available in real embedded deployments.

A seven-dimensional feature vector is extracted from each signal frame:

- Standard deviation of CLK: jitter indicator.
- Mean absolute value of GPIO: signal activity level.
- Standard deviation of GPIO: noise and glitch metric.
- Standard deviation of ADC: analogue noise level.
- Mean VOLTAGE rail value: supply stability.
- Standard deviation of VOLTAGE: supply fluctuation.
- Temperature register value: thermal drift indicator.

The model collects 300 frames of normal operation before fitting. A StandardScaler normalises features prior to training. Scores below -0.25 raise a WARNING. Scores below -0.45 raise a CRITICAL alert.

### NLP Command Parser

The parser uses Python's re module to match plain-English commands against a set of named patterns. Register addresses are resolved by either hex address or register name. Values accept both decimal and hexadecimal input.

---

## NLP Commands

```
set <register> to <value>    Write a register by name or hex address.
                             Example: set GPIO_OUT to 0xFF
                             Example: set 0x02 to 8

read <register>              Read a register value.
                             Example: read CTRL_REG

reset all                    Reset all writable registers to power-on defaults.
inject anomaly               Start fault simulation to demo AI detection.
clear anomaly                Stop fault simulation and restore normal operation.
show status                  Print device telemetry: clock, temperature, voltage, power.
run diagnostic               Quick self-test on key registers with pass or fail results.
export config                Save the full register map to fpga_config_export.csv.
help                         List all available commands.
```

---

## Register Map

```
Address    Name          R-W    Description
0x00       CTRL_REG      R-W    Main control register.
0x01       STATUS_REG    R-O    Device status, read-only.
0x02       CLK_DIV       R-W    Clock divider. Frequency equals 400 divided by divisor MHz.
0x03       GPIO_DIR      R-W    GPIO direction mask. 1 is output, 0 is input.
0x04       GPIO_OUT      R-W    GPIO output latch.
0x05       GPIO_IN       R-O    GPIO input sample, read-only.
0x06       INT_MASK      R-W    Interrupt enable mask.
0x07       TEMP_SENS     R-O    On-chip temperature in degrees Celsius, read-only.
0x08       VOLT_MON      R-O    Supply voltage monitor. Value times 0.05 equals volts, read-only.
0x09       FREQ_CNT      R-W    Frequency counter trigger.
0x0A       PWR_MGMT      R-W    Power management. 0 is sleep, 1 is active.
0x0B       DEBUG_REG     R-W    Debug and scratch register.
```

---

## Demo Walkthrough

1. Launch the app with python main.py.
2. On the Register Map tab, double-click GPIO-OUT and set it to 0xFF.
3. Type set CLK-DIV to 50 in the command bar. The clock frequency in the status bar updates.
4. Switch to the Signal Monitor tab and observe the four live channels.
5. Wait about 75 seconds for AI training to complete.
6. Click Inject Fault. Signals become noisy, temperature climbs, and WARNING and CRITICAL alerts appear.
7. Switch to the AI Diagnostics tab and watch the anomaly score chart drop below the threshold lines.
8. Click Clear Fault. The AI confirms recovery in the alert log.
9. Type run diagnostic to see a register-level health check.
10. Type export config to save the full register map to a CSV file.

---
