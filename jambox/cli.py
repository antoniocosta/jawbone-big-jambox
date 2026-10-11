"""jambox command line."""
import argparse
import datetime
import json
import os
import sys

import usb.util

from . import __version__, dfu, settings
from .device import (PID_DFU, PID_HID, PID_SERVICE, VARID_BUILDID, VARID_CHIPREV, VARID_CHIPVER,
                     Bccmd, JamboxError, find, mode, to_service_mode)

BACKUP_ROOT = os.path.expanduser("~/.local/share/jambox/backups")


def log(msg):
    print(msg, flush=True)


def serial():
    for pid in (PID_SERVICE, PID_HID, PID_DFU):
        dev = find(pid)
        if dev is not None:
            try:
                return usb.util.get_string(dev, dev.iSerialNumber)
            except Exception:
                return None
    return None


def read_state(b):
    keys = {k: b.ps_read(k) for k in settings.KNOWN_KEYS}
    return {
        "fw_version": settings.fw_version(keys.get(settings.PS_FW_VERSION)),
        "fw_version_raw": keys.get(settings.PS_FW_VERSION),
        "hw_version_raw": keys.get(settings.PS_HW_VERSION),
        "csr_build": b.uint16(VARID_BUILDID),
        "chip_version": b.uint16(VARID_CHIPVER),
        "chip_revision": b.uint16(VARID_CHIPREV),
        "name": settings.words_to_name(keys[settings.PS_NAME]) if keys.get(settings.PS_NAME) else None,
        "settings": settings.decode(keys),
        "pskeys": {f"0x{k:04x}": v for k, v in keys.items() if v is not None},
    }


def cmd_info(a):
    b = Bccmd()
    st = read_state(b)
    b.close()
    fw = st["fw_version"] or {}
    print(f"Model        : BIG JAMBOX (USB 1f6f, serial {serial()})")
    print(f"Name         : {st['name']}")
    print(f"Firmware     : {fw.get('label', '?')}  (built {fw.get('build', '?')})  "
          f"[PS 0x0292 = {' '.join(f'{w:04X}' for w in st['fw_version_raw'] or [])}]")
    print(f"Hardware     : {' '.join(f'{w:04X}' for w in st['hw_version_raw'] or [])}")
    print(f"CSR chip     : BlueCore version {st['chip_version']}, revision 0x{st['chip_revision']:02X}, "
          f"firmware build {st['csr_build']}")
    paired = sum(1 for k in range(0x02B4, 0x02BC) if f"0x{k:04x}" in st["pskeys"])
    print(f"Paired       : {paired} device(s) remembered")


def cmd_settings(a):
    b = Bccmd()
    st = read_state(b)
    b.close()
    if a.json:
        print(json.dumps({"name": st["name"], **st["settings"]}, indent=2))
        return
    print(f"{'name':20} {st['name']}")
    for name, key, byte, mask, note in settings.SETTINGS:
        v = st["settings"][name]
        shown = "?" if v is None else ("on" if v else "off") if mask != 0x03 else str(v)
        print(f"{name:20} {shown:4}  {note}")


def do_backup(outdir, with_firmware=True):
    os.makedirs(outdir, exist_ok=True)
    os.chmod(outdir, 0o700)
    b = Bccmd()
    st = read_state(b)
    b.close()
    st.update({"serial": serial(), "created": datetime.datetime.now().isoformat(timespec="seconds"),
               "tool": f"jambox {__version__}",
               "warning": "PRIVATE: contains Bluetooth pairing link keys. Do not publish."})
    with open(os.path.join(outdir, "pskeys.json"), "w") as f:
        json.dump(st, f, indent=2)
    log(f"settings and PS keys -> {outdir}/pskeys.json")
    if with_firmware:
        log("reading firmware (about 30 s)...")
        img = dfu.upload(log)
        with open(os.path.join(outdir, "firmware.bin"), "wb") as f:
            f.write(img)
        log(f"firmware ({len(img)} bytes) -> {outdir}/firmware.bin")
    return st


def default_backup_dir():
    sn = (serial() or "jambox").replace(" ", "_")
    return os.path.join(BACKUP_ROOT, f"{sn}-{datetime.datetime.now():%Y%m%d-%H%M%S}")


def cmd_backup(a):
    do_backup(a.dir or default_backup_dir(), with_firmware=not a.no_firmware)


def cmd_check(a):
    body = dfu.load_image(a.file)
    d = dfu.describe(body)
    print(f"OK: valid Big Jambox image, {len(body)} bytes, {-(-len(body) // dfu.XFER)} blocks")
    print(f"  product    : {d['product']}")
    print(f"  CSR build  : {d['csr_build']}")
    print(f"  firmware   : {'2.0 (AAC 44.1/48 kHz modules present)' if d['aac_2_0_modules'] else '1.x (no 2.0 AAC modules)'}")
    print(f"  DSP apps   : {', '.join(d['dsp_apps'])}")


def restore_keys(backup_dir, include_pairings=True, include_settings=True):
    """Write name, pairings and the on/off settings from a backup back to the speaker.
    Settings are restored bit by bit onto the current keys, so firmware-generation bits
    in the same words (2.0 features) are never overwritten with old values."""
    with open(os.path.join(backup_dir, "pskeys.json")) as f:
        backup = json.load(f)
    saved = {int(k, 16): v for k, v in backup["pskeys"].items()}
    keys = [settings.PS_NAME] + (settings.PAIRING_KEYS if include_pairings else [])
    b = Bccmd()
    try:
        for k in keys:
            if k in saved:
                b.ps_write(k, saved[k])
                log(f"  restored PS 0x{k:04X} ({len(saved[k])} words, verified)")
        if include_settings:
            wanted = backup.get("settings", {})
            for name in settings.SETTABLE:
                if wanted.get(name) is None:
                    continue
                key = next(s[1] for s in settings.SETTINGS if s[0] == name)
                cur = b.ps_read(key)
                if cur is None:
                    continue
                new = settings.with_bit(cur, name, bool(wanted[name]))
                if new != cur:
                    b.ps_write(key, new)
                    log(f"  restored setting {name} = {'on' if wanted[name] else 'off'} (verified)")
    finally:
        b.close()


def confirm(a, what):
    if a.yes:
        return
    print(f"\nAbout to {what}.")
    if input("Type FLASH to continue: ").strip() != "FLASH":
        sys.exit("aborted")


def cmd_flash(a):
    body = dfu.load_image(a.file)
    log(f"image OK: {a.file} ({len(body)} bytes)")
    b = Bccmd()
    before = settings.fw_version(b.ps_read(settings.PS_FW_VERSION))
    b.close()
    log(f"speaker firmware now: {before['label'] if before else '?'} ({before['build'] if before else '?'})")
    bdir = a.backup_dir or default_backup_dir()
    if not a.no_backup:
        do_backup(bdir)
    confirm(a, f"WRITE {os.path.basename(a.file)} to the speaker. Keep it connected; do not unplug "
               f"until jambox says it is finished (about 6 minutes)")
    last = [-1]

    def progress(i, n):
        pct = i * 100 // n
        if pct >= last[0] + 5 or i == n:
            last[0] = pct
            print(f"\r  sending {pct:3d}%", end="\n" if i == n else "", flush=True)

    dfu.download(body, log, progress)
    b = Bccmd()
    after = settings.fw_version(b.ps_read(settings.PS_FW_VERSION))
    b.close()
    log(f"speaker firmware now: {after['label'] if after else '?'} ({after['build'] if after else '?'})")
    if not a.no_backup and not a.no_restore:
        log("restoring name, settings" + ("" if a.no_pairings else " and paired devices") + " from the backup...")
        restore_keys(bdir, include_pairings=not a.no_pairings)
    log("done. Unplug the USB cable and switch the speaker on.")


def cmd_restore(a):
    confirm(a, f"write name, settings{'' if a.no_pairings else ' and paired devices'} from {a.dir} to the speaker")
    restore_keys(a.dir, include_pairings=not a.no_pairings)


def cmd_rename(a):
    words = settings.name_to_words(a.name)
    b = Bccmd()
    try:
        old = b.ps_read(settings.PS_NAME)
        b.ps_write(settings.PS_NAME, words)
    finally:
        b.close()
    print(f"renamed {settings.words_to_name(old)!r} -> {a.name!r} (verified). Takes effect at next power-on.")


def cmd_set(a):
    on = a.value == "on"
    key = next(s[1] for s in settings.SETTINGS if s[0] == a.setting)
    b = Bccmd()
    try:
        old = b.ps_read(key)
        if old is None:
            raise JamboxError(f"PS 0x{key:04X} not present on this speaker")
        before = settings.decode({key: old})[a.setting]
        new = settings.with_bit(old, a.setting, on)
        if new == old:
            print(f"{a.setting} is already {a.value}")
            return
        b.ps_write(key, new)  # verifies by reading back
    finally:
        b.close()
    print(f"{a.setting}: {'on' if before else 'off'} -> {a.value}  "
          f"(PS 0x{key:04X} {' '.join(f'{w:04X}' for w in old)} -> {' '.join(f'{w:04X}' for w in new)}, verified)")
    print("Takes effect at next power-on.")


def cmd_leave(a):
    dfu.leave_bootloader(log)
    print(f"mode: {mode()}  — unplug the USB cable to return the speaker to normal use")


def main(argv=None):
    p = argparse.ArgumentParser(prog="jambox", description="Read, back up, configure and update a "
                                "Jawbone BIG JAMBOX over USB. The speaker must be switched OFF and "
                                "connected by USB.")
    p.add_argument("--version", action="version", version=f"jambox {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("info", help="model, firmware/hardware version, chip").set_defaults(fn=cmd_info)
    s = sub.add_parser("settings", help="decoded Jawbone settings")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_settings)
    s = sub.add_parser("backup", help="back up firmware + settings/pairings (read-only)")
    s.add_argument("dir", nargs="?", help=f"output directory (default under {BACKUP_ROOT})")
    s.add_argument("--no-firmware", action="store_true", help="skip the 30 s firmware read-back")
    s.set_defaults(fn=cmd_backup)
    s = sub.add_parser("check", help="validate a firmware file (no device needed)")
    s.add_argument("file")
    s.set_defaults(fn=cmd_check)
    s = sub.add_parser("flash", help="back up, flash a .dfu, verify, restore name, settings + pairings")
    s.add_argument("file")
    s.add_argument("--yes", action="store_true", help="do not ask for confirmation")
    s.add_argument("--backup-dir")
    s.add_argument("--no-backup", action="store_true", help="skip the backup (not recommended)")
    s.add_argument("--no-restore", action="store_true", help="leave name/settings/pairings at firmware defaults")
    s.add_argument("--no-pairings", action="store_true", help="restore the name only")
    s.set_defaults(fn=cmd_flash)
    s = sub.add_parser("restore", help="write name, settings + paired devices back from a backup")
    s.add_argument("dir")
    s.add_argument("--yes", action="store_true")
    s.add_argument("--no-pairings", action="store_true")
    s.set_defaults(fn=cmd_restore)
    s = sub.add_parser("set", help="switch a setting on or off (" + ", ".join(settings.SETTABLE) + ")")
    s.add_argument("setting", choices=settings.SETTABLE)
    s.add_argument("value", choices=["on", "off"])
    s.set_defaults(fn=cmd_set)
    s = sub.add_parser("rename", help="set the Bluetooth name")
    s.add_argument("name")
    s.set_defaults(fn=cmd_rename)
    sub.add_parser("leave", help="return from service/bootloader mode").set_defaults(fn=cmd_leave)
    a = p.parse_args(argv)
    try:
        a.fn(a)
    except JamboxError as e:
        sys.exit(f"jambox: {e}")
    except usb.core.USBError as e:
        if e.errno == 13:
            sys.exit("jambox: permission denied — install the udev rule (tools/install.sh)")
        raise


if __name__ == "__main__":
    main()
