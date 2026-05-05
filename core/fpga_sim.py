import numpy as np
import random
import time
from copy import deepcopy
_REG_DEFS = [
    ("0x00", "CTRL_REG",   0x01, True,  "Main control register"),
    ("0x01", "STATUS_REG", 0x0F, False, "Device status (read-only)"),
    ("0x02", "CLK_DIV",    0x04, True,  "Clock divider ratio (1–255)"),
    ("0x03", "GPIO_DIR",   0xFF, True,  "GPIO direction mask (1=output)"),
    ("0x04", "GPIO_OUT",   0xAA, True,  "GPIO output latch"),
    ("0x05", "GPIO_IN",    0x55, False, "GPIO input sample (read-only)"),
    ("0x06", "INT_MASK",   0x00, True,  "Interrupt enable mask"),
    ("0x07", "TEMP_SENS",  0x1A, False, "On-chip temperature (°C × 1, read-only)"),
    ("0x08", "VOLT_MON",   0x64, False, "Supply voltage monitor ×0.05 V (read-only)"),
    ("0x09", "FREQ_CNT",   0x00, True,  "Frequency counter trigger"),
    ("0x0A", "PWR_MGMT",   0x01, True,  "Power management (0=sleep, 1=active)"),
    ("0x0B", "DEBUG_REG",  0x00, True,  "Debug / scratch register"),
]

class FPGASimulator:

    def __init__(self):
        self.regs = {
            addr: {"name": name, "value": val, "writable": wr, "desc": desc}
            for addr, name, val, wr, desc in _REG_DEFS
        }
        self._tick = 0
        self.anomaly_mode = False
        self._anomaly_start = 0
        self.clk_freq_mhz = 100.0
        self.temperature_c = 25.0
        self.voltage_v = 3.30
        self.power_w = 1.20
    def read_register(self, addr: str) -> int:
        return self.regs.get(addr, {}).get("value", 0)

    def write_register(self, addr: str, value: int) -> tuple[bool, str]:
        if addr not in self.regs:
            return False, f"Address {addr} does not exist."
        if not self.regs[addr]["writable"]:
            return False, f"{self.regs[addr]['name']} is read-only."
        self.regs[addr]["value"] = int(value) & 0xFF
        self._apply_side_effects(addr, self.regs[addr]["value"])
        return True, f"✔  {self.regs[addr]['name']} ← 0x{value & 0xFF:02X}"

    def reset_registers(self):
        for addr, name, val, wr, desc in _REG_DEFS:
            if wr:
                self.regs[addr]["value"] = val
        self.anomaly_mode = False
        return "All writable registers reset to defaults."

    def _apply_side_effects(self, addr, value):
        if addr == "0x02": 
            divisor = max(1, value)
            self.clk_freq_mhz = round(400.0 / divisor, 2)
        elif addr == "0x0A": 
            if value == 0:
                self.power_w = 0.05
            else:
                self.power_w = 1.20
    def get_signals(self, n_samples: int = 120) -> dict:
        t = np.linspace(self._tick, self._tick + 2 * np.pi, n_samples)
        self._tick += 2 * np.pi

        if self.anomaly_mode:
            drift = min(5.0, (time.time() - self._anomaly_start) * 0.3)
            noise = 0.6 + drift * 0.1
            freq_mult = 2.5 + drift * 0.4
        else:
            noise = 0.04
            freq_mult = 1.0
        clk_freq = self.clk_freq_mhz / 100.0 * freq_mult
        clk = np.sign(np.sin(clk_freq * t))
        gpio_raw = np.sign(np.sin(0.5 * freq_mult * t))
        gpio = gpio_raw + np.random.normal(0, noise, n_samples)
        gpio = np.clip(gpio, -1.5, 1.5)
        adc = 0.5 * np.sin(0.25 * t) + 0.5 + np.random.normal(0, noise * 0.5, n_samples)
        if self.anomaly_mode:
            adc += 0.4 * np.sin(drift * t[:n_samples])
        nominal = self.voltage_v
        v_noise = noise * 0.2 if not self.anomaly_mode else 0.35
        voltage = nominal + np.random.normal(0, v_noise, n_samples)
        if self.anomaly_mode:
            voltage += 0.15 * np.sin(0.8 * t) * drift

        return {
            "time": t,
            "CLK": clk,
            "GPIO": gpio,
            "ADC": adc,
            "VOLTAGE": voltage,
        }
    def get_feature_vector(self) -> list:
        sigs = self.get_signals(60)
        return [
            float(np.std(sigs["CLK"])),
            float(np.mean(np.abs(sigs["GPIO"]))),
            float(np.std(sigs["GPIO"])),
            float(np.std(sigs["ADC"])),
            float(np.mean(sigs["VOLTAGE"])),
            float(np.std(sigs["VOLTAGE"])),
            float(self.regs["0x07"]["value"]),
        ]
    def tick_sensors(self):
        if self.anomaly_mode:
            self.regs["0x07"]["value"] = min(
                0xFF, self.regs["0x07"]["value"] + random.randint(0, 2)
            )
            self.regs["0x08"]["value"] = max(
                0x30, self.regs["0x08"]["value"] - random.randint(0, 2)
            )
        else:
            self.regs["0x07"]["value"] = max(
                0x18, min(0x28, self.regs["0x07"]["value"] + random.randint(-1, 1))
            )
            self.regs["0x08"]["value"] = max(
                0x62, min(0x68, self.regs["0x08"]["value"] + random.randint(-1, 1))
            )

        self.temperature_c = round(self.regs["0x07"]["value"], 1)
        self.voltage_v = round(self.regs["0x08"]["value"] * 0.05, 2)
    def inject_anomaly(self):
        self.anomaly_mode = True
        self._anomaly_start = time.time()

    def clear_anomaly(self):
        self.anomaly_mode = False
        self.reset_registers()
