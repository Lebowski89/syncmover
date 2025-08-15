import unittest
import os
import tempfile
import time
from syncmover import (
    should_ignore,
    hardlink_file,
    process_folder,
    cleanup_folder_async,
    build_folder_labels_from_env
)

class TestSyncMover(unittest.TestCase):

    def setUp(self):
        # Create temporary directories for source and destination
        self.src_dir = tempfile.TemporaryDirectory()
        self.dst_dir = tempfile.TemporaryDirectory()

        # Create test files
        self.test_file1 = os.path.join(self.src_dir.name, "file1.txt")
        self.test_file2 = os.path.join(self.src_dir.name, "file2.tmp")
        with open(self.test_file1, "w") as f:
            f.write("test content 1")
        with open(self.test_file2, "w") as f:
            f.write("test content 2")

        # Grace period cutoff for linking
        self.grace_cutoff = time.time() - 60  # 1 minute ago

        # Backup environment variables
        self.env_backup = os.environ.copy()

    def tearDown(self):
        self.src_dir.cleanup()
        self.dst_dir.cleanup()
        os.environ.clear()
        os.environ.update(self.env_backup)

    # ---------- Basic unit tests ----------
    def test_should_ignore(self):
        self.assertTrue(should_ignore(".stfolder"))
        self.assertTrue(should_ignore("file2.tmp"))
        self.assertFalse(should_ignore("file1.txt"))

    def test_hardlink_file(self):
        # Link a valid file
        dst_file = os.path.join(self.dst_dir.name, "file1.txt")
        result = hardlink_file(self.test_file1, dst_file, self.grace_cutoff)
        self.assertTrue(result)
        self.assertTrue(os.path.exists(dst_file))

        # Attempt to link ignored file
        dst_file2 = os.path.join(self.dst_dir.name, "file2.tmp")
        result = hardlink_file(self.test_file2, dst_file2, self.grace_cutoff)
        self.assertFalse(result)
        self.assertFalse(os.path.exists(dst_file2))

    def test_process_folder(self):
        process_folder(self.src_dir.name, self.dst_dir.name)
        self.assertTrue(os.path.exists(os.path.join(self.dst_dir.name, "file1.txt")))
        self.assertFalse(os.path.exists(os.path.join(self.dst_dir.name, "file2.tmp")))

    def test_cleanup_folder_async(self):
        # Create old file in destination
        old_file = os.path.join(self.dst_dir.name, "old.txt")
        with open(old_file, "w") as f:
            f.write("old content")
        # Set its mtime to past cutoff
        os.utime(old_file, (time.time() - 3600*24*2, time.time() - 3600*24*2))  # 2 days old
        # Run cleanup in dry-run
        cleanup_folder_async(self.dst_dir.name, dry_run=True)
        time.sleep(1)
        self.assertTrue(os.path.exists(old_file))

    # ---------- Environment & dynamic folder label tests ----------
    def test_build_folder_labels_from_env_single(self):
        os.environ["MYAPP_0_FOLDER_LABEL"] = "LABEL_0"
        os.environ["MYAPP_0_SYNCFOLDER_PATH"] = self.src_dir.name
        os.environ["MYAPP_0_SYNCMOVER_PATH"] = self.dst_dir.name

        labels = build_folder_labels_from_env()
        self.assertIn("LABEL_0", labels)
        self.assertEqual(labels["LABEL_0"][0], self.src_dir.name)
        self.assertEqual(labels["LABEL_0"][1], self.dst_dir.name)

    def test_build_folder_labels_from_env_multiple(self):
        # Instance 0
        os.environ["APP_0_FOLDER_LABEL"] = "LABEL_A"
        os.environ["APP_0_SYNCFOLDER_PATH"] = self.src_dir.name
        os.environ["APP_0_SYNCMOVER_PATH"] = self.dst_dir.name
        # Instance 1
        dst_dir2 = tempfile.TemporaryDirectory()
        os.environ["APP_1_FOLDER_LABEL"] = "LABEL_B"
        os.environ["APP_1_SYNCFOLDER_PATH"] = self.src_dir.name
        os.environ["APP_1_SYNCMOVER_PATH"] = dst_dir2.name

        labels = build_folder_labels_from_env()
        self.assertIn("LABEL_A", labels)
        self.assertIn("LABEL_B", labels)
        self.assertEqual(labels["LABEL_A"][1], self.dst_dir.name)
        self.assertEqual(labels["LABEL_B"][1], dst_dir2.name)

        dst_dir2.cleanup()

if __name__ == "__main__":
    unittest.main()