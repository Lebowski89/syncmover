import os
import tempfile
import time
import shutil
import unittest
from unittest.mock import patch
import syncmover


def create_test_file(path, content="test", mtime=None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(content)
    if mtime is not None:
        os.utime(path, (mtime, mtime))


class TestSyncMover(unittest.TestCase):

    def setUp(self):
        self.src_dir = tempfile.mkdtemp()
        self.dst_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.src_dir, ignore_errors=True)
        shutil.rmtree(self.dst_dir, ignore_errors=True)

    def test_hardlink_file_links_or_copies(self):
        src_file = os.path.join(self.src_dir, "file.txt")
        dst_file = os.path.join(self.dst_dir, "file.txt")

        old_time = time.time() - (syncmover.GRACE_PERIOD_MINUTES * 60) - 60
        create_test_file(src_file, "hello", mtime=old_time)

        grace_cutoff = time.time() - syncmover.GRACE_PERIOD_MINUTES * 60
        result = syncmover.hardlink_file(src_file, dst_file, grace_cutoff)

        self.assertTrue(result)
        self.assertTrue(os.path.exists(dst_file))
        self.assertEqual(open(dst_file).read(), "hello")

        if hasattr(os, "link"):
            if os.stat(src_file).st_ino == os.stat(dst_file).st_ino:
                self.assertTrue(True)  # hardlink
            else:
                self.assertNotEqual(os.stat(src_file).st_ino, os.stat(dst_file).st_ino)  # copy

    def test_hardlink_file_respects_grace_period(self):
        src_file = os.path.join(self.src_dir, "recent.txt")
        create_test_file(src_file, "recent content", mtime=time.time())

        grace_cutoff = time.time() - syncmover.GRACE_PERIOD_MINUTES * 60
        result = syncmover.hardlink_file(src_file, os.path.join(self.dst_dir, "recent.txt"), grace_cutoff)
        self.assertFalse(result)

    def test_hardlink_file_fallback_copy_logs(self):
        src_file = os.path.join(self.src_dir, "fail.txt")
        dst_file = os.path.join(self.dst_dir, "fail.txt")

        old_time = time.time() - (syncmover.GRACE_PERIOD_MINUTES * 60) - 60
        create_test_file(src_file, "copy content", mtime=old_time)

        grace_cutoff = time.time() - syncmover.GRACE_PERIOD_MINUTES * 60

        with patch("os.link", side_effect=OSError("Operation not permitted")):
            with self.assertLogs(level="WARNING") as cm:
                result = syncmover.hardlink_file(src_file, dst_file, grace_cutoff)

        self.assertTrue(result)
        self.assertTrue(os.path.exists(dst_file))
        self.assertEqual(open(dst_file).read(), "copy content")
        self.assertTrue(any("copied instead" in msg for msg in cm.output))

    def test_process_folder_moves_files(self):
        old_time = time.time() - (syncmover.GRACE_PERIOD_MINUTES * 60) - 60
        create_test_file(os.path.join(self.src_dir, "a.txt"), "A", mtime=old_time)
        create_test_file(os.path.join(self.src_dir, "b.txt"), "B", mtime=old_time)
        create_test_file(os.path.join(self.src_dir, ".stfolder"), "", mtime=old_time)  # ignored

        syncmover.process_folder(self.src_dir, self.dst_dir)

        self.assertTrue(os.path.exists(os.path.join(self.dst_dir, "a.txt")))
        self.assertTrue(os.path.exists(os.path.join(self.dst_dir, "b.txt")))
        self.assertFalse(os.path.exists(os.path.join(self.dst_dir, ".stfolder")))

    def test_cleanup_folder_async_deletes_old_files(self):
        now = time.time()
        old_time = now - (syncmover.CLEANUP_AFTER_HOURS * 3600) - 60

        for i in range(3):
            create_test_file(os.path.join(self.src_dir, f"old_{i}.txt"), mtime=old_time)

        for i in range(2):
            create_test_file(os.path.join(self.src_dir, f"recent_{i}.txt"), mtime=now)

        syncmover.CLEANUP_BATCH_SIZE = 10
        syncmover.KEEP_RECENT_FILES = 0
        syncmover.cleanup_folder_async(self.src_dir, dry_run=False)

        time.sleep(1)  # allow async thread to finish

        remaining_files = os.listdir(self.src_dir)
        self.assertTrue(all("recent" in f for f in remaining_files))

    def test_should_ignore_patterns_and_files(self):
        syncmover.IGNORE_FILES = {".stfolder"}
        syncmover.IGNORE_PATTERNS = (".syncthing.", ".tmp")

        self.assertTrue(syncmover.should_ignore(".stfolder"))
        self.assertTrue(syncmover.should_ignore("file.syncthing.tmp"))
        self.assertFalse(syncmover.should_ignore("normalfile.txt"))


if __name__ == "__main__":
    unittest.main()