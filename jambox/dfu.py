"""USB DFU (1.0) on the Big Jambox bootloader 1f6f:0044: image checks, upload, download."""
import struct
import time
import zlib

import usb.core
import usb.util

from .device import PID_DFU, PID_SERVICE, VID, JamboxError, find, to_service_mode, wait_for

DETACH, DNLOAD, UPLOAD, GETSTATUS, CLRSTATUS, GETSTATE, ABORT = range(7)
STATES = ["appIDLE", "appDETACH", "dfuIDLE", "dfuDNLOAD-SYNC", "dfuDNBUSY", "dfuDNLOAD-IDLE",
          "dfuMANIFEST-SYNC", "dfuMANIFEST", "dfuMANIFEST-WAIT-RESET", "dfuUPLOAD-IDLE", "dfuERROR"]
XFER = 1023
CSR_FW_SEGMENT = 0x094DAC  # loader+stack segment length shared by all Big Jambox images (build 7724)


def load_image(path):
    """Bytes to download: a .dfu minus its 16-byte suffix, or a raw read-back. Raises on anything
    that is not an intact Big Jambox CSR-dfu2 image."""
    with open(path, "rb") as f:
        raw = f.read()
    body = raw
    if raw[-8:-5] == b"UFD" and raw[-5] == 16:
        if (zlib.crc32(raw[:-4]) ^ 0xFFFFFFFF) != struct.unpack("<I", raw[-4:])[0]:
            raise JamboxError("DFU suffix CRC mismatch")
        body = raw[:-16]
    if body[:8] != b"CSR-dfu2":
        raise JamboxError("not a CSR-dfu2 firmware image")
    if (zlib.crc32(body[:-4]) ^ 0xFFFFFFFF) != struct.unpack("<I", body[-4:])[0]:
        raise JamboxError("image CRC mismatch (corrupt or truncated)")
    if b"JAMBOX by Jawbone" in body and b"BIG JAMBOX by Jawbone" not in body:
        raise JamboxError("this is ORIGINAL-Jambox firmware, not Big Jambox — it would brick the speaker")
    if struct.unpack("<I", body[0x78:0x7C])[0] != CSR_FW_SEGMENT:
        raise JamboxError("unexpected CSR firmware segment; not a Big Jambox image")
    return body


def describe(body):
    """Human-readable facts about a validated image: product name, CSR build, DSP codec apps."""
    import re
    text = {m.group(0).decode("utf-16le") for m in re.finditer(rb"(?:[\x20-\x7e]\x00){6,}", body)}
    text |= {m.group(0).decode() for m in re.finditer(rb"[\x20-\x7e]{6,}", body)}
    build = sorted(s for s in text if s.startswith("elv_"))
    kaps = sorted({k for s in text for k in re.findall(r"([A-Za-z0-9_]+)\.kap$", s)})
    return {
        "product": "BIG JAMBOX by Jawbone" if b"BIG JAMBOX by Jawbone" in body else "(name not in image)",
        "csr_build": build[0] if build else None,
        "aac_2_0_modules": "aac_decoder_44100" in kaps,
        "dsp_apps": kaps,
    }


def _dfu_interface(dev):
    for cfg in dev:
        for intf in cfg:
            if intf.bInterfaceClass == 0xFE and intf.bInterfaceSubClass == 0x01:
                return intf.bInterfaceNumber
    raise JamboxError("no DFU interface")


def _getstatus(dev, ifn):
    r = bytes(dev.ctrl_transfer(0xA1, GETSTATUS, 0, ifn, 6, timeout=20000))
    return r[0], r[4], r[1] | (r[2] << 8) | (r[3] << 16)


def enter_bootloader(log=print):
    """Service mode -> DFU bootloader. Writes nothing."""
    if find(PID_DFU) is not None:
        return find(PID_DFU)
    to_service_mode()
    dev = find(PID_SERVICE)
    ifn = _dfu_interface(dev)
    for i in range(3):
        try:
            if dev.is_kernel_driver_active(i):
                dev.detach_kernel_driver(i)
        except usb.core.USBError:
            pass
    usb.util.claim_interface(dev, ifn)
    dev.ctrl_transfer(0x21, DETACH, 1000, ifn, None, timeout=5000)
    usb.util.release_interface(dev, ifn)
    time.sleep(0.1)
    try:
        dev.reset()
    except usb.core.USBError:
        pass
    usb.util.dispose_resources(dev)
    dfu = wait_for(PID_DFU)
    if dfu is None:
        raise JamboxError("speaker did not enter its bootloader (1f6f:0044)")
    if dfu.bcdDevice != 0x7724:
        raise JamboxError(f"unexpected bootloader bcdDevice {dfu.bcdDevice:04x} (expected 7724)")
    log("bootloader 1f6f:0044 ready")
    return dfu


def leave_bootloader(log=print):
    """Bootloader -> application (DFU_ABORT + reset). Writes nothing."""
    dfu = find(PID_DFU)
    if dfu is None:
        return
    ifn = _dfu_interface(dfu)
    try:
        dfu.ctrl_transfer(0x21, ABORT, 0, ifn, None, timeout=5000)
    except usb.core.USBError:
        pass
    try:
        dfu.reset()
    except usb.core.USBError:
        pass
    usb.util.dispose_resources(dfu)
    if wait_for(PID_SERVICE, 15) is None and wait_for(0x0043, 5) is None:
        raise JamboxError("speaker did not come back after leaving the bootloader")
    log("speaker back in application mode")


def upload(log=print):
    """Read the complete firmware image (read-only). Returns bytes; leaves the bootloader."""
    dfu = enter_bootloader(log)
    ifn = _dfu_interface(dfu)
    usb.util.claim_interface(dfu, ifn)
    status, state, _ = _getstatus(dfu, ifn)
    if state != 2 or status != 0:
        raise JamboxError(f"bootloader not idle ({STATES[state]}, status {status})")
    data, block, t0 = bytearray(), 0, time.time()
    while True:
        chunk = bytes(dfu.ctrl_transfer(0xA1, UPLOAD, block, ifn, XFER, timeout=10000))
        data += chunk
        block += 1
        if block % 512 == 0:
            log(f"  read {len(data) // 1024} KiB")
        if len(chunk) < XFER:
            break
        if len(data) > 32 << 20:
            raise JamboxError("upload larger than 32 MiB")
    log(f"read {len(data)} bytes in {time.time() - t0:.0f} s")
    usb.util.release_interface(dfu, ifn)
    leave_bootloader(log)
    if (zlib.crc32(bytes(data[:-4])) ^ 0xFFFFFFFF) != struct.unpack("<I", data[-4:])[0]:
        raise JamboxError("read-back image CRC invalid")
    return bytes(data)


def _wait(dev, ifn, want, limit, what, log):
    t0, last = time.time(), None
    while True:
        try:
            status, state, poll = _getstatus(dev, ifn)
        except usb.core.USBTimeoutError:
            # During manifestation the bootloader writes flash for ~2-3 minutes and does not
            # answer at all. Keep waiting; never reset or unplug in this phase.
            if time.time() - t0 > limit:
                raise
            if last != "busy":
                log(f"  {what}: speaker busy writing flash — waiting (do not unplug)")
                last = "busy"
            continue
        if state == 10 or status != 0:
            raise JamboxError(f"{what}: bootloader error status={status} state={STATES[state]}")
        if state in want:
            return state
        if time.time() - t0 > limit:
            raise JamboxError(f"{what}: still {STATES[state]} after {limit} s")
        time.sleep(max(poll, 50) / 1000)


def download(body, log=print, progress=None):
    """WRITE an image (from load_image) to the speaker and boot it."""
    nblocks = -(-len(body) // XFER)
    dfu = enter_bootloader(log)
    ifn = _dfu_interface(dfu)
    usb.util.claim_interface(dfu, ifn)
    status, state, _ = _getstatus(dfu, ifn)
    if state != 2 or status != 0:
        raise JamboxError(f"bootloader not idle ({STATES[state]}, status {status})")
    t0 = time.time()
    for n in range(nblocks):
        dfu.ctrl_transfer(0x21, DNLOAD, n & 0xFFFF, ifn, body[n * XFER:(n + 1) * XFER], timeout=30000)
        _wait(dfu, ifn, (5,), 600, f"block {n}", log)
        if progress:
            progress(n + 1, nblocks)
    log(f"all {nblocks} blocks sent in {time.time() - t0:.0f} s; writing flash (~2-3 min, do not unplug)")
    dfu.ctrl_transfer(0x21, DNLOAD, nblocks & 0xFFFF, ifn, None, timeout=30000)
    end = _wait(dfu, ifn, (2, 8), 900, "manifestation", log)
    log(f"flash write complete ({STATES[end]}) after {time.time() - t0:.0f} s")
    usb.util.release_interface(dfu, ifn)
    try:
        dfu.reset()
    except usb.core.USBError:
        pass
    usb.util.dispose_resources(dfu)
    if wait_for(PID_SERVICE, 20) is None and wait_for(0x0043, 5) is None:
        raise JamboxError("speaker did not boot after flashing — do NOT unplug; run `jambox info` to check")
    log("new firmware booted")
