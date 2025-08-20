import unittest
import os
import tempfile
import time
from unittest.mock import patch
from syncmover import hardlink_file, process_folder, cleanup_folder_async, should_ignore

class TestSyncMover(unittest.TestCase):

    def test_hardlink_success(self):
        with tempfile.TemporaryDirectory() as src_dir, tempfile.TemporaryDirectory() as dst_dir:
            src_file = os.path.join(src_dir, "file.txt")
            dst_file = os.path.join(dst_dir, "file.txt")
            with open(src_file, "w", encoding="utf-8") as f:
                f.write("hello")

            # Use negative grace_cutoff to bypass grace period in test
            result = hardlink_file(src_file, dst_file, grace_cutoff=-1)
            self.assertTrue(result)
            with open(dst_file, "r", encoding="utf-8") as f:
                self.assertEqual(f.read(), "hello")

    def test_hardlink_file_fallback_copy_logs(self):
        with tempfile.TemporaryDirectory() as src_dir, tempfile.TemporaryDirectory() as dst_dir:
            src_file = os.path.join(src_dir, "fail.txt")
            dst_file = os.path.join(dst_dir, "fail.txt")
            with open(src_file, "w", encoding="utf-8") as f:
                f.write("copy content")

            # Force os.link to raise OSError to test fallback copy
            with patch("os.link", side_effect=OSError("forced fallback")):
                import logging
                logger = logging.getLogger("SyncMover")
                logger.setLevel(logging.WARNING)

                with self.assertLogs("SyncMover", level="WARNING") as cm:
                    result = hardlink_file(src_file, dst_file, grace_cutoff=-1)

                self.assertTrue(result)
                with open(dst_file, "r", encoding="utf-8") as f:
                    self.assertEqual(f.read(), "copy content")
                self.assertTrue(any("Copied" in msg for msg in cm.output))

    def test_should_ignore_patterns(self):
        self.assertTrue(should_ignore(".stfolder"))
        self.assertTrue(should_ignore("test.tmp"))
        self.assertFalse(should_ignore("keep.txt"))

    def test_cleanup_folder_async_deletes_files(self):
        with tempfile.TemporaryDirectory() as dirpath:
            old_file = os.path.join(dirpath, "old.txt")
            recent_file = os.path.join(dirpath, "recent.txt")
            with open(old_file, "w", encoding="utf-8") as f:
                f.write("old")
            with open(recent_file, "w", encoding="utf-8") as f:
                f.write("recent")

            # Set old file mtime far in past, recent file current
            os.utime(old_file, (0, 0))
            os.utime(recent_file, None)

            # Use keep_recent_override=0 to force deletion of old file
            t = cleanup_folder_async(dirpath, dry_run=False, keep_recent_override=0)
            t.join(timeout=5)

            self.assertFalse(os.path.exists(old_file))
            self.assertTrue(os.path.exists(recent_file))

if __name__ == "__main__":
    unittest.main()