"""PS-key map and Jawbone settings decoding (from Jawbone Updater 2.2.5's CSRConfig)."""

PS_NAME = 0x0108
PS_FW_VERSION = 0x0292
PS_HW_VERSION = 0x226C

# Every PS key the updater knows for the Big Jambox family (CSRConfig index table 0x47302C).
KNOWN_KEYS = [0x0108, 0x225B, 0x225C, 0x225E, 0x2260, 0x226C, 0x2273, 0x2276, 0x028A, 0x028B,
              0x0291, 0x0292, 0x0299, 0x029A, 0x02A8, 0x02AB, 0x02AC, 0x02AD, 0x02AE, 0x02AF,
              0x02B3] + list(range(0x02B4, 0x02BC))

PAIRING_KEYS = [0x02AB, 0x02B3] + list(range(0x02B4, 0x02BC))  # per-device data, order, 8 records
# Keys `jambox restore` may write back after a flash: user data only, never firmware-generation
# feature words (0x02AC, 0x0299, 0x0292 ...), which would undo 2.0 features.
RESTORABLE = [PS_NAME] + PAIRING_KEYS

# (name, key, byte, mask, note) — PS words are read high byte first.
SETTINGS = [
    ("voice_tones",        0x225B, 0,  0x80, ""),
    ("announce_caller_id", 0x225B, 0,  0x40, ""),
    ("spp",                0x02A8, 1,  0x03, "serial port profile (app link)"),
    ("live_audio",         0x2260, 1,  0x01, "BACCH 3D; also toggled with + and - buttons"),
    ("multipoint",         0x02AC, 1,  0x01, ""),
    ("volume_sync",        0x02AC, 0,  0x10, "AVRCP absolute volume (2.0)"),
    ("aac",                0x0299, 11, 0x40, "AAC codec (2.0)"),
    ("button_volume_mode", 0x02AC, 0,  0x08, "0 = noise-shield toggle"),
    ("live_audio_capable", 0x02AC, 0,  0x04, "capability flag"),
]


# Settings `jambox set` may change: plain on/off bits whose meaning is confirmed against the
# updater's settings XML and/or the speaker's behaviour. Capability flags and modes stay read-only.
SETTABLE = ["live_audio", "aac", "volume_sync", "voice_tones", "announce_caller_id", "multipoint"]


def words_to_bytes(words):
    return b"".join(w.to_bytes(2, "big") for w in words)


def bytes_to_words(raw):
    return [int.from_bytes(raw[i:i + 2], "big") for i in range(0, len(raw), 2)]


def with_bit(words, name, on):
    """Return a copy of the key's words with setting `name` switched on/off; other bits untouched."""
    _, key, byte, mask, _ = next(s for s in SETTINGS if s[0] == name)
    raw = bytearray(words_to_bytes(words))
    if len(raw) <= byte:
        raise ValueError(f"PS 0x{key:04X} too short for {name}")
    raw[byte] = (raw[byte] | mask) if on else (raw[byte] & ~mask & 0xFF)
    return bytes_to_words(bytes(raw))


def decode(keys):
    """keys: {pskey: [words] or None} -> {setting: int or None}."""
    out = {}
    for name, key, byte, mask, _ in SETTINGS:
        w = keys.get(key)
        if not w or len(w) * 2 <= byte:
            out[name] = None
            continue
        v = words_to_bytes(w)[byte] & mask
        out[name] = v if mask == 0x03 else v >> ((mask & -mask).bit_length() - 1)
    return out


def name_to_words(text):
    """CSR PS string: bytes swapped within each 16-bit word, NUL-terminated, word-padded."""
    if not (1 <= len(text) <= 39) or not text.isascii():
        raise ValueError("name must be 1-39 ASCII characters")
    raw = text.encode("ascii") + b"\0"
    if len(raw) % 2:
        raw += b"\0"
    return [raw[i] | (raw[i + 1] << 8) for i in range(0, len(raw), 2)]


def words_to_name(words):
    raw = b"".join(bytes([w & 0xFF, w >> 8]) for w in words)
    return raw.split(b"\0")[0].decode("ascii", errors="replace")


def fw_version(words):
    """Decode PS 0x0292: word1 high byte 0x80|major; words 2-4 = MMDD YYHH MMSS build time."""
    if not words or len(words) < 5:
        return None
    major = (words[1] >> 8) & 0x7F
    s = "".join(f"{w:04x}" for w in words[2:5])  # MMDDYYHHMMSS
    mm, dd, yy, hh, mi, ss = (s[i:i + 2] for i in range(0, 12, 2))
    return {"major": major, "build": f"20{yy}-{mm}-{dd} {hh}:{mi}:{ss}",
            "label": {1: "1.x", 2: "2.x"}.get(major, f"{major}.x")}
