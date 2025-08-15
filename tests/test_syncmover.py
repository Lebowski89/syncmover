import unittest
import os
import tempfile
from syncmover import hardlink_file, process_folder, cleanup_folder_async, should_ignore

class TestSyncMover(unittest.TestCase):

    def test_hardlink_success(self):
        with tempfile.TemporaryDirectory() as src_dir, tempfile.TemporaryDirectory() as dst_dir:
            src_file = os.path.join(src_dir, "file.txt")
            dst_file = os.path.join(dst_dir, "file.txt")
            with open(src_file, "w", encoding="utf-8") as f:
                f.write("hello")

            result = hardlink_file(src_file, dst_file, grace_cutoff=0)
            self.assertTrue(result)
            with open(dst_file, "r", encoding="utf-8") as f:
                self.assertEqual(f.read(), "hello")

    def test_hardlink_file_fallback_copy_logs(self):
        with tempfile.TemporaryDirectory() as src_dir, tempfile.TemporaryDirectory() as dst_dir:
            src_file = os.path.join(src_dir, "fail.txt")
            dst_file = os.path.join(dst_dir, "fail.txt")
            with open(src_file, "w", encoding="utf-8") as f:
                f.write("copy content")

            original_link = os.link
            os.link = lambda s, d: (_ for _ in ()).throw(OSError("forced fallback"))

            try:
                import logging
                logger = logging.getLogger("SyncMover")
                logger.setLevel(logging.WARNING)

                with self.assertLogs(logger, level="WARNING") as cm:
                    result = hardlink_file(src_file, dst_file, grace_cutoff=0)

                self.assertTrue(result)
                with open(dst_file, "r", encoding="utf-8") as f:
                    self.assertEqual(f.read(), "copy content")
                self.assertTrue(any("Copied" in msg for msg in cm.output))
            finally:
                os.link = original_link

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

            # Set old file mtime far in past
            os.utime(old_file, (0, 0))
            cleanup_folder_async(dirpath)
            # wait briefly for async thread
            import time; time.sleep(0.2)
            self.assertFalse(os.path.exists(old_file))
            self.assertTrue(os.path.exists(recent_file))

if __name__ == "__main__":
    unittest.main()