"""USB access: mode switching and BCCMD (CSR) commands over the service-mode interface."""
import struct
import time

import usb.core
import usb.util

VID = 0x1F6F
PID_HID, PID_SERVICE, PID_DFU = 0x0043, 0x8000, 0x0044

GETREQ, GETRESP, SETREQ = 0x0000, 0x0001, 0x0002
VARID_PS_SIZE, VARID_PS = 0x3006, 0x7003
VARID_BUILDID, VARID_CHIPVER, VARID_CHIPREV = 0x2819, 0x281A, 0x281B
STORE = 0x0080  # the PS store Jawbone Updater 2.2.5 reads and writes
STATUS = {0: "OK", 1: "NO_SUCH_VARID", 2: "TOO_BIG", 3: "NO_VALUE", 4: "BAD_REQ", 5: "NO_ACCESS",
          6: "READ_ONLY", 7: "WRITE_ONLY", 8: "ERROR", 9: "PERMISSION_DENIED"}


class JamboxError(Exception):
    pass


def find(pid):
    return usb.core.find(idVendor=VID, idProduct=pid)


def mode():
    """Current USB personality: 'normal', 'service', 'bootloader' or None."""
    for name, pid in (("service", PID_SERVICE), ("bootloader", PID_DFU), ("normal", PID_HID)):
        if find(pid) is not None:
            return name
    return None


def wait_for(pid, timeout=10.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        dev = find(pid)
        if dev is not None:
            return dev
        time.sleep(0.2)
    return None


def to_service_mode():
    """Normal mode (HID) -> service mode via the HID report 'AT+JBDFU', as the updater does."""
    if find(PID_SERVICE) is not None:
        return
    if find(PID_DFU) is not None:
        raise JamboxError("speaker is in its bootloader; run `jambox leave` or unplug/replug it")
    dev = find(PID_HID)
    if dev is None:
        raise JamboxError("no Big Jambox found. Switch the speaker OFF and connect it by USB.")
    if dev.is_kernel_driver_active(0):
        dev.detach_kernel_driver(0)
    try:  # HID SET_REPORT, output report 0, interface 0
        dev.ctrl_transfer(0x21, 0x09, 0x0200, 0, b"AT+JBDFU".ljust(35, b"\0"), timeout=2000)
    except usb.core.USBError:
        pass  # the device drops off the bus immediately — expected
    if wait_for(PID_SERVICE) is None:
        raise JamboxError("speaker did not enter service mode (1f6f:8000)")


class Bccmd:
    """BCCMD in HCI vendor command 0xFC00 (channel 0xC2) on interface 0 of service mode."""

    def __init__(self):
        to_service_mode()
        self.dev = find(PID_SERVICE)
        for intf in (0, 1):
            try:
                if self.dev.is_kernel_driver_active(intf):
                    self.dev.detach_kernel_driver(intf)
            except usb.core.USBError:
                pass
        usb.util.claim_interface(self.dev, 0)
        self.seq = 0x7000

    def close(self):
        usb.util.release_interface(self.dev, 0)
        usb.util.dispose_resources(self.dev)

    def _event(self):
        buf = b""
        while len(buf) < 2 or len(buf) < 2 + buf[1]:
            buf += bytes(self.dev.read(0x81, 16, timeout=2000))
        return buf

    def _exchange(self, typ, varid, payload):
        self.seq = (self.seq + 1) & 0xFFFF
        words = [typ, 5 + len(payload), self.seq, varid, 0] + list(payload)
        msg = b"\xC2" + struct.pack(f"<{len(words)}H", *words)
        self.dev.ctrl_transfer(0x20, 0x00, 0, 0, struct.pack("<HB", 0xFC00, len(msg)) + msg, timeout=2000)
        for _ in range(10):
            ev = self._event()
            if ev[0] == 0xFF and ev[2] == 0xC2:
                n = (len(ev) - 3) // 2
                w = struct.unpack(f"<{n}H", ev[3:3 + 2 * n])
                if w[2] == self.seq:
                    return w[4], list(w[5:])
        raise JamboxError("no BCCMD response")

    def get(self, varid, payload):
        return self._exchange(GETREQ, varid, payload)

    def set(self, varid, payload):
        return self._exchange(SETREQ, varid, payload)[0]

    def uint16(self, varid):
        st, w = self.get(varid, [0, 0, 0, 0])
        return w[0] if st == 0 and w else None

    def ps_read(self, key):
        """Return the words of a PS key, or None if it does not exist."""
        st, w = self.get(VARID_PS_SIZE, [key, 0, 0, 0])
        if st != 0 or len(w) < 2 or w[1] == 0:
            return None
        n = w[1]
        st, w = self.get(VARID_PS, [key, n, STORE] + [0] * n)
        return w[3:3 + n] if st == 0 else None

    def ps_write(self, key, words):
        """Write a PS key exactly as Jawbone Updater 2.2.5 does, then verify by reading back."""
        st = self.set(VARID_PS, [key, len(words), STORE] + list(words))
        if st != 0:
            raise JamboxError(f"write of PS 0x{key:04X} failed: {STATUS.get(st, st)}")
        back = self.ps_read(key)
        if back != list(words):
            raise JamboxError(f"verify of PS 0x{key:04X} failed: wrote {words}, read {back}")
