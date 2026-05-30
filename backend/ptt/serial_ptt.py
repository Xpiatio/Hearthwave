from backend.ptt.base import PTT


class SerialPTT(PTT):
    """USB-serial RTS or DTR drives an external transistor on the radio's PTT line.
    Lead-in/tail give the TX chain time to settle on both sides of the audio."""
    lead_in_seconds = 0.05
    tail_seconds = 0.05

    def __init__(self, port, line="RTS"):
        import serial
        self.line = (line or "RTS").upper()
        self.port = serial.Serial(port)
        self.port.rts = False
        self.port.dtr = False

    def key(self):
        if self.line == "DTR":
            self.port.dtr = True
        else:
            self.port.rts = True

    def unkey(self):
        if self.line == "DTR":
            self.port.dtr = False
        else:
            self.port.rts = False

    def close(self):
        try:
            self.unkey()
            self.port.close()
        except Exception:
            pass
