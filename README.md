# Jawbone BIG JAMBOX — firmware archive & Linux update tool

Keep your **Jawbone BIG JAMBOX** (model J2011, 2012; internal codename
"Jamberry") working, updated and under your own control, long after
Jawbone stopped supporting it. This repo has two parts:

1. **`jambox`, a new open-source Linux tool** that updates the speaker's
   firmware, changes its voice or language, backs it up and restores it,
   and reads and changes its settings, all over USB. It is the first
   replacement for Jawbone's dead Windows/Mac updater, built by
   reverse-engineering that updater. The full protocol is documented in
   [`docs/PROTOCOL.md`](docs/PROTOCOL.md), so it can be ported or rebuilt
   by anyone.
2. **A verified preservation archive**: every surviving firmware image (19
   voices and languages, checksummed), the official Jawbone updaters,
   manuals and voice samples. Only official material is archived.

If you like this or find it useful, support the project by buying me a coffee.

<a href="https://www.buymeacoffee.com/antoniocosta" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" style="height: 40px !important;width: 140px !important;" ></a>

## Why this repo exists

I own a Big Jambox. It still sounds great, but since Jawbone shut down in
2017 there has been no official way to update, recover or even inspect it.
The servers, updater downloads and support pages are gone, and the last
updater no longer runs on modern Windows or macOS. Every owner was left with
a speaker frozen on whatever firmware it happened to have; mine was still on
its 2012 factory firmware. I don't accept that working hardware should
become e-waste, or stay half-featured, because its maker disappeared.

So this repo does two things:

- **It preserves.** The firmware, tools and documentation are scattered
  across one personal mirror, the Wayback Machine and old forum threads.
  Here they are in one durable, checksummed place, before more of it
  disappears.
- **It puts the tools back in owners' hands.** The `jambox` updater is free,
  open and runs on today's Linux, so any owner can update their speaker
  to the final 2.0 firmware (AAC streaming, volume sync, longer battery
  life), change its voice, back it up, rename it and keep it running. They
  don't need Jawbone's servers, a 2012-era operating system or anyone's
  permission. The protocol write-up is there so others can extend it, for
  example to macOS or to other Jambox models.

It is a small act of **right to repair** and **post-corporate
preservation**, in the spirit of Rebble (Pebble) and LineageOS/postmarketOS
(phones): community efforts that keep abandoned devices alive and out of
landfills, against planned obsolescence.

## Quick start (Linux)

```sh
tools/install.sh        # installs ~/.local/bin/jambox + a udev rule (asks for sudo once)
```

Switch the speaker **off** and connect it by **micro-USB**. It only appears
on USB while switched off. Then:

```sh
jambox info             # firmware/hardware version, chip, paired devices
jambox settings         # LiveAudio, AAC, volume sync, voice tones, ...
jambox backup           # firmware read-back + all settings/pairings
jambox check firmware/voices/bigjambox_original_v2.dfu
jambox flash firmware/voices/bigjambox_original_v2.dfu
jambox set aac on         # also: live_audio, volume_sync, voice_tones, announce_caller_id, multipoint
jambox rename "My Jambox"
```

`jambox flash` runs these steps: validate the image → back up the firmware
and settings → confirm → flash → verify → write the name, your settings
(AAC, LiveAudio, …) and paired devices back. Use the laptop on mains power, and **don't unplug during the flash**:
after the last block the speaker spends about 2–3 minutes writing flash and
does not respond in that time. The tool waits for it.

Backups go to `~/.local/share/jambox/backups/`. **They contain Bluetooth
pairing keys; keep them private.**

Other commands: `restore DIR` (name, settings and pairings from a backup), `leave`
(return from service/bootloader mode). Offline tests:
`python3 -m unittest discover -s tests`.

**Status:** used on one real unit to go from factory 1.x to 2.0 and then to
change the voice with a full `jambox flash` cycle (backup → flash → verify →
pairings restored; the speaker reconnected without re-pairing). Every write
is verified by reading back. It is open-source software
for an unsupported device: use it at your own risk.

## Firmware

All 19 images are the same final firmware (**2.0**, built 2013-01-15). They
differ only in the voice that speaks prompts. Pick a voice; flashing any
of them *is* the update.

| Voice / language | `firmware/…` | `voice-samples/…` |
|---|---|---|
| The Original (default) | `voices/bigjambox_original_v2.dfu` | `voices/original.mp3` |
| The Thinker | `voices/bigjambox_thinker_v2.dfu` | `voices/thinker.mp3` |
| The Rogue | `voices/bigjambox_rogue_v2.dfu` | `voices/rogue.mp3` |
| The Hero | `voices/bigjambox_hero_v2.dfu` | `voices/hero.mp3` |
| The Bombshell | `voices/bigjambox_bombshell_v2.dfu` | `voices/bombshell.mp3` |
| The Ace | `voices/bigjambox_ace_v2.dfu` | `voices/ace.mp3` |
| The Catch | `voices/bigjambox_catch_v2.dfu` | `voices/catch.mp3` |
| Baseball | `voices/bigjambox_baseball_v2.dfu` | `voices/baseball.mp3` |
| Mobster | `voices/bigjambox_mobster_v2.dfu` | `voices/mobster.mp3` |
| Arcade | `voices/bigjambox_arcade_v2.dfu` | `voices/arcade.mp3` |
| French | `languages/bigjambox_french_v2.dfu` | `languages/french.mp3` |
| German | `languages/bigjambox_german_v2.dfu` | `languages/german.mp3` |
| Spanish | `languages/bigjambox_spanish_v2.dfu` | `languages/spanish.mp3` |
| Italian | `languages/bigjambox_italian_v2.dfu` | `languages/italian.mp3` |
| Portuguese | `languages/bigjambox_portuguese_v2.dfu` | `languages/portuguese.mp3` |
| Japanese | `languages/bigjambox_japanese_v2.dfu` | `languages/japanese.mp3` |
| Korean | `languages/bigjambox_korean_v2.dfu` | `languages/korean.mp3` |
| Mandarin | `languages/bigjambox_mandarin_v2.dfu` | `languages/mandarin.mp3` |
| Cantonese | `languages/bigjambox_cantonese_v2.dfu` | `languages/cantonese.mp3` |

Verify with `(cd firmware && md5sum -c MD5SUMS && sha256sum -c SHA256SUMS)`.
- **Checksums:** all files match the MD5s published by Hawdon, except
  Baseball. His page lists Bombshell's MD5 for it, which is evidently a
  copy-paste error. Our Baseball file has a valid internal CRC (MD5
  `263cacf82ea3d9701666f3aab11c4cdd`).
- **Voice samples:** previews published alongside the firmware (Jawbone's
  file names, renamed here to match the voices).
- **Wrong-model files:** never flash original-Jambox firmware (`eames-*.dfu`,
  identifies as "JAMBOX by Jawbone") to a Big Jambox. `jambox check`
  refuses it.

## What firmware 2.0 brings

Jawbone's April 2013 changelog: AAC streaming, fewer dropouts at a distance,
about 2 h more battery (17 h total), volume sync with the phone, a silent
mode (no prompts/tones), better LED response and PS Vita support.
Measured on a real unit going from factory 1.x to 2.0:

| | Factory 1.x (2012-03-15) | 2.0 (2013-01-15) |
|---|---|---|
| Audio codecs | SBC | **SBC + AAC** |
| Remote control | AVRCP 1.0 controller | **AVRCP 1.4 controller + target** (volume sync) |
| Device ID record | — | Jawbone `v008A p000B d005C` |
| CSR Bluetooth stack | build 7724 | build 7724 (identical) |

- **Linux codecs:** Linux plays SBC unless your PipeWire has an AAC encoder.
  Apple devices use AAC.
- **LiveAudio:** not new. Every Big Jambox shipped with LiveAudio (BACCH 3D)
  built in.
- **Older firmware:** no other firmware than 2.0 is known to survive, except
  the factory 1.x image read back from the owner's unit (kept private: it
  contains pairing data).

## Buttons

From the 2012 quick-start guide (`docs/manuals/`):

| Action | Control |
|---|---|
| Power on/off (without sound) | Hold POWER (hold MINUS, then POWER) |
| Pairing mode | Hold PAIRING until the LED flashes red/white (PIN `0000`) |
| LiveAudio on/off | Hold PLUS and MINUS (the speaker remembers it) |
| Battery status / reconnect | Press TALK |
| Play audio demo | Hold TALK, PLUS and MINUS |
| Answer/end call · redial · mute mic | TALK · TALK 2× · PLAY/PAUSE |

- **Charging:** use the 14 V+ DC adapter. USB charges only slowly. A full
  charge takes about 2.5 h.
- **Reset** (from Jawbone support): hold TALK while connecting power.
- **LiveAudio placement** (BACCH): speaker at eye level, 0.25–0.75 m away.
  Binaural recordings show the effect best.

## Repair and hardware notes

- **Construction:** held together with screws, with a digital amplifier and
  passive radiators front and back.
- **Bass mod:** about 2 × 2 €0.50 coins taped to the passive radiators deepens
  the bass. It's reversible, but at your own risk.
- **Hiss:** a background hiss reported after 2.0 may be a hardware fault, not
  firmware (<https://www.youtube.com/watch?v=nd5nF2hSFHw>).
- **Inside:** CSR BlueCore5 (chip version 5, revision 0xE1). Per-unit
  calibration and the Bluetooth address are not part of firmware images,
  so flashing keeps them.

## Troubleshooting

- **Not detected on USB:** the speaker must be **switched off**. Some laptops
  also put the USB controller to sleep (seen with TLP on a 2012 MacBook Air).
  Keep it awake until reboot with
  `echo on | sudo tee /sys/bus/pci/devices/<xhci>/power/control`.
- **Permission denied:** run `tools/install.sh` (udev rule `tools/udev/70-jawbone.rules`).
- **Bootloader:** if the speaker is stuck in the bootloader (`1f6f:0044`), run
  `jambox leave`, or flash again. Your backup contains the previous firmware.
- **After flashing:** `jambox flash` restores your pairings, so devices
  connect without re-pairing. On the very first boot after a flash, the
  speaker may not reconnect by itself. Connect once from the phone/laptop,
  or switch the speaker off and on; after that it reconnects automatically.
  If pairings were not restored (e.g. `--no-restore`), remove the old
  Bluetooth entry on the phone/laptop and pair again.

## Official Jawbone Updater (Windows)

Also archived in `updater/`:
- **2.2.5** for Windows; the macOS build is 32-bit and won't run on Catalina
  or later.
- **1.6.2**, reported to recover bricked units.

How to use 2.2.5:
1. Install it, power the speaker off and connect it by USB.
2. Choose tray icon → Big Jambox → *Update from local DFU package*.

Command line:
`JawboneUpdater -nobrowser -noNet -update file.dfu -requiredDeviceLocation <port>`.

## Layout

```
README.md
jambox/              the jambox tool (Python; pyproject.toml)
tests/               offline tests
tools/install.sh     installer;  tools/udev/70-jawbone.rules
firmware/            19 Big Jambox images (voices/, languages/) + MD5SUMS, SHA256SUMS
updater/             official Jawbone Updater 2.2.5 (Windows, macOS), 1.6.2 (Windows)
voice-samples/       MP3 preview of each voice
docs/PROTOCOL.md     the reverse-engineered USB protocol, PS keys, image format
docs/manuals/        Big Jambox quick-start guides (PDF)
docs/private/        (gitignored) your own backups and dumps
```

## Legal

- **This repo's own work:** the `jambox` tool, tests, install script, udev
  rule and documentation (`docs/PROTOCOL.md`, this README) are original work,
  licensed under the **GNU General Public License v3.0 or later** (see
  [`LICENSE`](LICENSE)). They were written to let owners maintain hardware
  they own, through interoperability with a discontinued product. The GPL
  keeps every modified or ported version open to owners too.
- **Jawbone's material:** the firmware images, the official updaters, the
  manuals and the voice samples are **not** covered by the GPL. They remain
  the copyright of Jawbone (AliphCom). They are archived here only to
  preserve an abandoned product for its owners, unmodified and with their
  original checksums. If you are a rights holder and object to their
  inclusion, please open an issue and they will be removed.
- **No warranty:** use the tool at your own risk. Flashing firmware always
  carries some risk; `jambox` backs up the speaker before every update to
  keep that risk as low as possible.

## Credits

This archive exists only because other people kept these files and this
knowledge alive. Thank you to all of them. Usernames are as they appear on
each site.

### Firmware and updater maintainers

- **Robert Ian Hawdon** — hosts the only surviving mirror of the Big Jambox
  firmware (all 19 voice/language images), Jawbone Updater 2.2.5
  (Windows/macOS) and 1.6.2, the voice samples and the published MD5 sums.
  Every binary in `firmware/`, `updater/` and `voice-samples/` comes from his
  archive. <https://robert.hawdon.net/jambox/>
- **DerDaku** (Reddit / XDA) — tracked down Jawbone's last firmware files
  (for the original Jambox) on its AWS servers. This is the find Hawdon
  credits for starting his Jambox mirrors.
- **Jawbone (AliphCom)** — original authors of the hardware, firmware,
  updater, manuals and support articles. **CSR (Cambridge Silicon Radio)**
  made the BlueCore5 platform; **BACCH Labs / Princeton University** created
  the BACCH 3D technology behind LiveAudio.

### XDA — "[Q] Big Jambox Firmware" (2013–2016)

<https://xdaforums.com/t/q-big-jambox-firmware.2578223/>

- **staile** — started the thread; found that `-requiredDeviceLocation`
  makes the command-line updater work.
- **monomalvado** — analysed the `.dfu` format, documented the command line
  and the 4 %/51 % update phases, and posted the first `Jamberry-…` URL.
- **ozba (Marcos)** — posted the stock `Jamberry-20130212110523-base-base.dfu`
  URL, the working command line and the verbose updater log.
- **ia79** — posted the original-Jambox file URL and reported cross-model
  flashing results.
- **chammerbeck** — described reflashing demo/retail units.
- **grinny11, distrodan, xn3xus, therearenorules, digitalium** — posted
  failure logs and brick symptoms.
- **sevenlies, tttdayjr** — pointed to the Updater 1.6.2 un-brick; sevenlies
  relayed Jawbone support's reset procedure.
- **schemeneo** — reported the hiss after 2.0.

### Other community sources

- **iFixit** — *Firmware update .DFU Jambox Big*: **budfox9**, **tomcos_123**,
  **bjornjackson**, **Dan McGauley**.
- **Jawbone Community forum, BIG JAMBOX board:** **Sparkee, wdfly,
  JawboneJaimie, JawboneAlex, joebryant, dsilverman** (*USB Charging*) and
  **teolinkiat, Music2drown2** (*How to change voice*).
- **Reddit:**
  - **DerDaku**: voice guide, file-name check, Big Jambox brick warning.
  - **RubarbKid**: pointed people to Hawdon and proposed a GitHub repository,
    as this one is.
  - **sminkie, tttdayjr, thefearofgod, JP35000**: Updater 1.6.2 recovery.
  - **faebudo, zhuangboren, leein3d, dayplus, vonvon_en**: early firmware
    links, procedures, Big Jambox specifics.
  - **PriorAmphibian3**: teardown and bass mod.

### Archives and press

- **Internet Archive — Wayback Machine:** Jawbone support pages, knowledge-base
  articles and the quick-start PDFs.
- **Press:** iDownloadBlog / AllThingsD, Ubergizmo and TekRevue, for the 2.0
  changelog.
- **BACCH Labs** — *Jambox Info* (<https://www.bacch.com/jambox-info>).
- **Tools:** the BlueZ project (`bccmd`, `dfutool`), libusb and pyusb, and
  QEMU (USB capture during the reverse engineering).

If you are one of the people above and want a credit changed or removed,
please open an issue.
