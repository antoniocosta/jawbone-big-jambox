"""Offline tests (no speaker needed): python3 -m unittest discover -s tests"""
import glob
import os
import tempfile
import unittest

from jambox import dfu, settings
from jambox.device import JamboxError

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Images(unittest.TestCase):
    def test_all_archived_firmware_is_valid(self):
        files = sorted(glob.glob(os.path.join(ROOT, "firmware", "*", "*.dfu")))
        self.assertEqual(len(files), 19)
        for f in files:
            body = dfu.load_image(f)
            self.assertEqual(len(body), os.path.getsize(f) - 16)

    def test_truncated_image_is_refused(self):
        src = os.path.join(ROOT, "firmware", "voices", "bigjambox_original_v2.dfu")
        with tempfile.NamedTemporaryFile(suffix=".dfu") as t:
            with open(src, "rb") as f:
                t.write(f.read()[:1_000_000])
            t.flush()
            with self.assertRaises(JamboxError):
                dfu.load_image(t.name)


class Settings(unittest.TestCase):
    # Values read from the owner's unit (1.x as found, then 2.0); XML from Jawbone Updater -saveSettings.
    ONE_X = {0x225B: [0xE01E], 0x2260: [0x0D01], 0x02A8: [0x0001], 0x02AC: [0x4459],
             0x0299: [0x9350, 0x3091, 0x1167, 0xE477, 0x3000, 0x5600]}

    def test_decode_matches_updater_xml(self):
        d = settings.decode(self.ONE_X)
        self.assertEqual((d["voice_tones"], d["announce_caller_id"], d["spp"], d["live_audio"],
                          d["multipoint"], d["volume_sync"], d["aac"]), (1, 1, 1, 1, 1, 0, 0))

    def test_decode_2_0(self):
        d = settings.decode({0x02AC: [0x5459], 0x0299: [0x9350, 0x3091, 0x1167, 0xE477, 0x3000, 0xE640],
                             0x2260: [0x16D1]})
        self.assertEqual((d["volume_sync"], d["aac"], d["live_audio"]), (1, 1, 1))

    def test_with_bit_touches_only_one_bit(self):
        w = [0x9350, 0x3091, 0x1167, 0xE477, 0x3000, 0xE640]
        off = settings.with_bit(w, "aac", False)
        self.assertEqual(off, [0x9350, 0x3091, 0x1167, 0xE477, 0x3000, 0xE600])
        self.assertEqual(settings.with_bit(off, "aac", True), w)
        self.assertEqual(settings.with_bit([0x16D1], "live_audio", False), [0x16D0])
        self.assertEqual(settings.with_bit([0x5459], "volume_sync", False), [0x4459])
        self.assertEqual(settings.with_bit([0xE01E], "voice_tones", False), [0x601E])

    def test_name_roundtrip(self):
        w = [0x4942, 0x2047, 0x414A, 0x424D, 0x584F, 0x6220, 0x2079, 0x614A, 0x6277, 0x6E6F, 0x0065]
        self.assertEqual(settings.words_to_name(w), "BIG JAMBOX by Jawbone")
        self.assertEqual(settings.name_to_words("BIG JAMBOX by Jawbone"), w)

    def test_fw_version(self):
        self.assertEqual(settings.fw_version([0x8105, 0x8000, 0x0315, 0x1203, 0x2312, 0])["build"],
                         "2012-03-15 03:23:12")
        v2 = settings.fw_version([0x8105, 0x8200, 0x0115, 0x1302, 0x0813, 0])
        self.assertEqual((v2["label"], v2["build"]), ("2.x", "2013-01-15 02:08:13"))


if __name__ == "__main__":
    unittest.main()
