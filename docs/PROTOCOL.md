# BIG JAMBOX USB protocol

Reverse-engineered in October 2026 from Jawbone Updater 2.2.5, by static
analysis and USB captures of the updater running in a Windows XP VM, and
verified on a real speaker (model J2011, CSR BlueCore5). Everything here is
implemented in `jambox/`.

## 1. USB personalities

| Mode | VID:PID | Interfaces | Reached by |
|---|---|---|---|
| **Normal** | `1f6f:0043` | 1 × HID: EP 0x81 interrupt IN (64 B), 35-byte in/out report, no report IDs. Usage page `0x0B00`, usage 5. | power-on default |
| **Service** ("Jawbone Updating") | `1f6f:8000` | **IF0** vendor class FF/01/01: EP 0x81 interrupt IN (16 B), EP 0x02 bulk OUT, EP 0x82 bulk IN (64 B) · **IF1** Bluetooth E0/01/01, alt settings 0–5, isochronous EP 0x03/0x83 · **IF2** DFU (class FE/01, protocol 0) | `AT+JBDFU` (§2) |
| **Bootloader** | `1f6f:0044` | 1 × DFU (FE/01/00) | `DFU_DETACH` + USB reset from service mode (§5) |

- **Only appears when off.** The speaker presents itself on USB only while
  switched off. When on, the port charges and nothing else.
- **Device descriptor:** `bcdDevice` = `0x7724` (= CSR firmware build 7724).
  The serial is `Jawbone_<Bluetooth address>`.
- **Resets end service mode.** Any USB bus reset in service mode reboots the
  speaker into normal mode. A VM passthrough must not forward guest resets
  (QEMU `usb-host,guest-reset=off`).
- **Keep `btusb` off service mode.** On Linux it binds IF0/IF1 and sends an
  HCI Reset that never completes, because the chip runs an on-chip stack and
  ignores plain HCI. The udev rule `tools/udev/70-jawbone.rules` unbinds
  `btusb` from vendor `1f6f`.
- **Jawbone's driver table** (`JBLibUSB.inf`, libusb-win32): Big Jambox
  `0043`/`0044`; "Jawbone Updating" `8000`; Jambox `0023`/`0040`/`0041`;
  Mini Jambox `004F`/`0050`; ERA `0013`/`004B`/`004C`; ICON `0003`; The NERD
  `0033` (interface 4).

## 2. Normal → service mode

A HID SET_REPORT on EP0:

```
bmRequestType 0x21  bRequest 0x09  wValue 0x0200 (output report 0)  wIndex 0  wLength 35
data: "AT+JBDFU" followed by 27 × 0x00
```

The device drops off the bus at once (the status stage fails) and
re-enumerates as `1f6f:8000`. The updater binary also contains `AT+JBSF_DFU`
(serial-flash DFU, for other models).

## 3. BCCMD in service mode

CSR BCCMD inside HCI vendor command `0xFC00`, channel byte `0xC2` (BCCMD,
single fragment):

```
OUT  control  bmRequestType 0x20 bRequest 0 wValue 0 wIndex 0
     00 fc <plen> c2 <words LE: type, length, seq, varid, status, payload...>
IN   EP 0x81 interrupt, 16-byte chunks, reassembled:
     ff <len> c2 <same layout, type = GETRESP>
```

| type | meaning |
|---|---|
| `0x0000` | GETREQ |
| `0x0001` | GETRESP |
| `0x0002` | SETREQ |

| varid | use | request payload |
|---|---|---|
| `0x3006` | PS size | `key, 0, 0, 0` → response word 1 = length in words |
| `0x7003` | PS read / write | `key, length, store, data[length]` (store `0x0080`, as the updater uses) |
| `0x2819` | CSR build id | → `7724` |
| `0x281A` / `0x281B` | chip version / revision | → `5` / `0x00E1` |

Status values: 0 OK, 1 NO_SUCH_VARID, 2 TOO_BIG, 3 NO_VALUE, 4 BAD_REQ,
5 NO_ACCESS, 6 READ_ONLY, 7 WRITE_ONLY, 8 ERROR, 9 PERMISSION_DENIED.

**Writes** use the same `0x7003` message as SETREQ. The updater does this in
`UsbApiWritePSKeyBytes` and retries up to 10 times. `jambox` reads every
write back to verify it.

## 4. PS keys and settings

PS words are 16-bit; for bit tests they are taken **high byte first**
(`e01e` → byte0 `e0`, byte1 `1e`). Jawbone's `CSRConfig` index table, for the
Big Jambox family:

| Key | Content |
|---|---|
| `0x0108` | Bluetooth name: ASCII, NUL-terminated, the two bytes of each word swapped |
| `0x225B` | flags: byte0 bit7 = voice tones, bit6 = announce caller ID |
| `0x225C` | 48 words of pairs: button/event → action map (presumed) |
| `0x2260` | byte1 bit0 = **LiveAudio** (persists the + / − button toggle), byte1 bit1 = Sound Clarity; byte0 bits 3–5 are headset motion features (not used by the speaker) |
| `0x226C` | hardware version (`0B5C 0020 0030 0000`) |
| `0x0292` | **firmware version**: word1 = `0x80` \| major in the high byte; words 2–4 = `MMDD YYHH MMSS` build time |
| `0x0299` | byte 11 bit 6 = **AAC** |
| `0x02A8` | byte1 bits 0–1 = SPP mode (1 = on) |
| `0x02AB` | per-device values (8 words) |
| `0x02AC` | byte0 bit4 = **AVRCP volume sync**, bit3 = button mode (0 = noise-shield toggle), bit2 = LiveAudio supported; byte1 bit0 = multipoint |
| `0x02B3` | paired-device priority order |
| `0x02B4`–`0x02BB` | 8 paired-device records (43 words: address + link key + profile state) — private |
| `0x0269` | `vm.app` (on-chip application) |
| `0x02BE`/`0x02BF`/`0x02CB` | USB VID `1f6f` / PID `0043` / PID `0044` |

**Verified on the speaker's behaviour (2026-10-12):** clearing `0x0299`
byte 11 bit 6 (`jambox set aac off`) removes the AAC A2DP endpoint; setting
it again brings the endpoint back after a power cycle. The LiveAudio bit
follows the + / − toggle. The name write changes the advertised Bluetooth
name.

Also known to the updater, not yet decoded: `0x225E`, `0x2273`, `0x2276`,
`0x028A`, `0x028B`, `0x0291`, `0x029A`, `0x02AD`, `0x02AE`, `0x02AF`.

| | 1.x (2012-03-15) | 2.0 (2013-01-15) |
|---|---|---|
| `0x0292` | `8105 8000 0315 1203 2312 0000` | `8105 8200 0115 1302 0813 0000` |
| `0x02AC` | `4459` (volume sync off) | `5459` (volume sync on) |
| `0x0299` word 5 | `5600` (AAC off) | `e640` (AAC on) |

## 5. Firmware: DFU 1.0 on the bootloader

- **Enter:** in service mode, `DFU_DETACH` (`0x21`/0, wValue = timeout,
  wIndex 2), then USB reset → `1f6f:0044`, `dfuIDLE`. The device has
  bitWillDetach = 0, so the host must reset.
- **Functional descriptor:** attributes `0x07` (download, upload,
  manifestation-tolerant), detach timeout 5000 ms, **transfer size 1023**.
- **Upload (read):** `DFU_UPLOAD` blocks of 1023 until a short block.
  3.75–3.91 MB in about 28 s. The result is the image in the format of §6,
  without the DFU suffix, and **includes the live PS store** (pairings).
- **Download (write):** send the `.dfu` file **minus its 16-byte DFU suffix**
  as `DFU_DNLOAD` blocks of 1023 bytes, waiting for `dfuDNLOAD-IDLE` after
  each block. Then send a zero-length `DFU_DNLOAD`.
  - **Manifestation:** the bootloader does not answer GETSTATUS **for about
    2–3 minutes** while it writes flash. Never reset or unplug during this
    time. Afterwards it reports `status 0`, `dfuIDLE`.
  - **Boot:** a USB reset boots the new firmware into service mode.
- **Leave without writing:** `DFU_ABORT` + reset.
- **Flash result:** the user/settings section is replaced by the image's
  defaults, so pairings are gone. `jambox flash` backs these up first and
  writes them back afterwards. Verified 2026-10-12: after restoring
  `0x0108`, `0x02AB`, `0x02B3` and `0x02B4`–`0x02BB`, a paired host connects
  without re-pairing. The speaker did not auto-reconnect on its first boot
  after the flash, but did on every power cycle after that.

## 6. Image format (`CSR-dfu2`)

```
0x00  "CSR-dfu2", u16 version (3), u32 length, ...
0x10  64-byte description (spaces, or "LOADER=..., STACK=..." in read-backs)
0x78  u32 CSR firmware segment length = 0x094DAC
      "CSRbcfw1"  CSR loader + Bluetooth stack, 0x094DAC bytes (build 7724, 2011-03-17)
      settings section: records [0002][key][len][data...]  (v2 header 0000 0083; device ffff 0001 0045)
      "fsr_dfu1"  file system: vm.app, DSP .kap codecs, voice prompts; ends "iFel" + data
      u32 CRC32 over everything before it
.dfu files only: 16-byte USB DFU suffix (bcdDevice 7724, VID/PID ffff, "UFD", CRC32)
```

- **The CSR segment is identical** in factory 1.x and in all 2.0 files.
  Only the settings section and the file system differ.
- **Per-unit factory data** (Bluetooth address `0x0001`, crystal trim
  `0x01F6`, …) is in neither image, so a DFU flash leaves it untouched.
- **Codecs:** 2.0 adds `aac_decoder_44100` and `aac_decoder_48000` to the
  DSP apps (`aac_decoder`, `sbc_decoder`, `mp3_decoder`, `faststream_sink`,
  `cvc_*`, `jawbone_usb_streaming`, …).
- **Original Jambox** (codename `eames`) images look similar but identify as
  `JAMBOX by Jawbone` and brick a Big Jambox. `jambox check` refuses them.

## 7. Bluetooth (for reference)

| | 1.x | 2.0 |
|---|---|---|
| A2DP endpoints | SBC | SBC + AAC (MPEG-2/4 AAC-LC, 8–48 kHz) |
| AVRCP | controller 1.0 | controller + target 1.4 (absolute volume) |
| PnP Device ID | — | `v008A p000B d005C` |
| HFP / HSP / SPP | 1.5 / 1.2 / yes | unchanged |

Class `0x240404`, Secure Simple Pairing, Bluetooth address OUI `00:21:3C`
(AliphCom).

## 8. Jawbone Updater 2.2.5 internals (for reference)

- **Build:** wxWidgets 2.8.10, libcurl + OpenSSL 0.9.8zb, Boost 1.54,
  mongoose, libusb-win32 1.2.6 (0.1 API only). Built 1 May 2015.
- **CLI:** `-listDevices`, `-saveDevices`, `-psrDump FILE`, `-psrLoad`,
  `-psrValidate`, `-saveSettings`/`-loadSettings`, `-savePhonebook`,
  `-update FILE`, `-requiredDeviceLocation`, `-nobrowser`, `-noNet`,
  `-noTaskbarMenu`, `-noSingleInst`, `-autoHciQuit`, `-stdout`, `-version`.
  Results appear in message boxes.
- **Local web API** (how MyTALK drove it): `http://127.0.0.1:48081/aliph/`
  with commands `jsonIsConnected`, `jsonUpdate`, `jsonUpdateStatus`,
  `jsonSyncSettings`, …
- **Hidden developer menu:** app setting `enableDevMenu` (PS dump/load,
  "update without restoring settings", test loops).
- **Classes (RTTI):** `CSRConfig` (CSR speakers; vtable `0x75DADC`, AAC
  getter/setter at `+0x70`/`+0x74`), `ADK2Config` (newer ADK devices),
  `JBUSBConnection`, `JBDevicePSKeyRW`.
- **Windows XP note:** the unsigned "Jawbone Updating" driver is refused in
  background installs; the interactive *Found New Hardware* wizard accepts
  it.
