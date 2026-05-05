import re
from datetime import datetime
def _resolve_addr(token: str, regs: dict) -> str | None:
    token = token.strip().upper()
    hex_match = re.fullmatch(r"0X([0-9A-F]{1,2})", token)
    if hex_match:
        addr = "0x{:02X}".format(int(hex_match.group(1), 16)).lower()
        addr = "0x{:02x}".format(int(hex_match.group(1), 16))
        for k in regs:
            if k.lower() == addr:
                return k
        return None
    for k, v in regs.items():
        if v["name"].upper() == token:
            return k
    return None

def _resolve_value(token: str) -> int | None:
    token = token.strip()
    try:
        if token.lower().startswith("0x"):
            return int(token, 16)
        return int(token)
    except ValueError:
        return None
class NLPParser:

    COMMANDS = [
        ("set",        r"set\s+(.+?)\s+to\s+(.+)"),
        ("read",       r"read\s+(.+)"),
        ("reset",      r"reset\s+all"),
        ("inject",     r"inject\s+anomaly"),
        ("clear",      r"clear\s+anomaly"),
        ("status",     r"show\s+status"),
        ("diagnostic", r"run\s+diag(?:nostic)?"),
        ("export",     r"export\s+config"),
        ("help",       r"help"),
    ]

    def __init__(self, fpga):
        self.fpga = fpga
        self.history: list[tuple] = []

    def parse(self, raw: str) -> dict:
        text = raw.strip().lower()
        timestamp = datetime.now().strftime("%H:%M:%S")
        result = self._dispatch(text)
        self.history.append((timestamp, raw, result))
        return result

    def _dispatch(self, text: str) -> dict:
        for cmd, pattern in self.COMMANDS:
            m = re.fullmatch(pattern, text, re.IGNORECASE)
            if m:
                return getattr(self, f"_cmd_{cmd}")(m)
        return {"cmd": "unknown", "success": False,
                "message": f"Unknown command. Type 'help' to see available commands."}
    def _cmd_set(self, m):
        addr = _resolve_addr(m.group(1), self.fpga.regs)
        if addr is None:
            return {"cmd": "set", "success": False,
                    "message": f"Register '{m.group(1)}' not found."}
        val = _resolve_value(m.group(2))
        if val is None:
            return {"cmd": "set", "success": False,
                    "message": f"Invalid value '{m.group(2)}'."}
        ok, msg = self.fpga.write_register(addr, val)
        return {"cmd": "set", "success": ok, "message": msg, "addr": addr, "value": val}

    def _cmd_read(self, m):
        addr = _resolve_addr(m.group(1), self.fpga.regs)
        if addr is None:
            return {"cmd": "read", "success": False,
                    "message": f"Register '{m.group(1)}' not found."}
        val = self.fpga.read_register(addr)
        name = self.fpga.regs[addr]["name"]
        return {"cmd": "read", "success": True,
                "message": f"{name} ({addr}) = 0x{val:02X}  ({val} dec)",
                "addr": addr, "value": val}

    def _cmd_reset(self, m):
        msg = self.fpga.reset_registers()
        return {"cmd": "reset", "success": True, "message": msg}

    def _cmd_inject(self, m):
        self.fpga.inject_anomaly()
        return {"cmd": "inject", "success": True,
                "message": "⚠  Anomaly injected — watch the AI Monitor tab."}

    def _cmd_clear(self, m):
        self.fpga.clear_anomaly()
        return {"cmd": "clear", "success": True,
                "message": "✔  Anomaly cleared. Returning to normal operation."}

    def _cmd_status(self, m):
        lines = [
            f"  Clock freq : {self.fpga.clk_freq_mhz} MHz",
            f"  Temperature: {self.fpga.temperature_c} °C",
            f"  Voltage    : {self.fpga.voltage_v} V",
            f"  Power      : {self.fpga.power_w} W",
            f"  Anomaly    : {'ACTIVE' if self.fpga.anomaly_mode else 'None'}",
        ]
        return {"cmd": "status", "success": True, "message": "\n".join(lines)}

    def _cmd_diagnostic(self, m):
        results = []
        temp = self.fpga.regs["0x07"]["value"]
        volt = self.fpga.regs["0x08"]["value"]
        ctrl = self.fpga.regs["0x00"]["value"]
        results.append(f"  CTRL_REG   : 0x{ctrl:02X}  {'OK' if ctrl & 0x01 else 'WARN: device may be disabled'}")
        results.append(f"  TEMP_SENS  : {temp}°C   {'OK' if temp < 70 else 'WARN: high temperature'}")
        results.append(f"  VOLT_MON   : {volt * 0.05:.2f}V   {'OK' if 0x60 <= volt <= 0x70 else 'WARN: out of range'}")
        results.append(f"  CLK_FREQ   : {self.fpga.clk_freq_mhz} MHz  OK")
        return {"cmd": "diagnostic", "success": True,
                "message": "Diagnostic complete:\n" + "\n".join(results)}

    def _cmd_export(self, m):
        return {"cmd": "export", "success": True,
                "message": "Exporting configuration... (see saved file in project folder)"}

    def _cmd_help(self, m):
        cmds = [
            "  set <reg> to <value>   — Write register  (e.g. 'set GPIO_OUT to 0xFF')",
            "  read <reg>             — Read register   (e.g. 'read 0x02')",
            "  reset all              — Reset writable registers to defaults",
            "  inject anomaly         — Simulate an FPGA fault condition",
            "  clear anomaly          — Restore normal operation",
            "  show status            — Print device summary",
            "  run diagnostic         — Quick self-test",
            "  export config          — Save register map to CSV",
            "  help                   — Show this message",
        ]
        return {"cmd": "help", "success": True, "message": "\n".join(cmds)}
