import os
import tempfile
import time
import shutil
import pytest
import syncmover
from unittest.mock import patch


@pytest.fixture
def temp_dirs():
    src_dir = tempfile.mkdtemp()
    dst_dir = tempfile.mkdtemp()
    yield src_dir, dst_dir
    shutil.rmtree(src_dir, ignore_errors=True)
    shutil.rmtree(dst_dir, ignore_errors=True)


def create_test_file(path, content="test", mtime=None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(content)
    if mtime is not None:
        os.utime(path, (mtime, mtime))


def test_hardlink_file_links_or_copies(temp_dirs):
    src_dir, dst_dir = temp_dirs
    src_file = os.path.join(src_dir, "file.txt")
    dst_file = os.path.join(dst_dir, "file.txt")

    # mtime older than grace period
    old_time = time.time() - (syncmover.GRACE_PERIOD_MINUTES * 60) - 60
    create_test_file(src_file, "hello", mtime=old_time)

    grace_cutoff = time.time() - syncmover.GRACE_PERIOD_MINUTES * 60
    result = syncmover.hardlink_file(src_file, dst_file, grace_cutoff)

    assert result is True
    assert os.path.exists(dst_file)
    assert open(dst_file).read() == "hello"

    # Should either be a hardlink or a copy depending on FS permissions
    if hasattr(os, "link"):
        if os.stat(src_file).st_ino == os.stat(dst_file).st_ino:
            assert True  # hardlink
        else:
            assert os.stat(src_file).st_ino != os.stat(dst_file).st_ino  # copy


def test_hardlink_file_respects_grace_period(temp_dirs):
    src_dir, dst_dir = temp_dirs
    src_file = os.path.join(src_dir, "recent.txt")

    # File modified just now (within grace period)
    create_test_file(src_file, "recent content", mtime=time.time())

    grace_cutoff = time.time() - syncmover.GRACE_PERIOD_MINUTES * 60
    result = syncmover.hardlink_file(src_file, os.path.join(dst_dir, "recent.txt"), grace_cutoff)
    assert result is False  # should skip due to grace period


def test_hardlink_file_fallback_copy_logs(temp_dirs, caplog):
    """Force hardlink to fail so we test copy fallback and log message."""
    src_dir, dst_dir = temp_dirs
    src_file = os.path.join(src_dir, "fail.txt")
    dst_file = os.path.join(dst_dir, "fail.txt")

    old_time = time.time() - (syncmover.GRACE_PERIOD_MINUTES * 60) - 60
    create_test_file(src_file, "copy content", mtime=old_time)

    grace_cutoff = time.time() - syncmover.GRACE_PERIOD_MINUTES * 60

    with patch("os.link", side_effect=OSError("Operation not permitted")):
        result = syncmover.hardlink_file(src_file, dst_file, grace_cutoff)

    assert result is True  # still succeeded via copy
    assert os.path.exists(dst_file)
    assert open(dst_file).read() == "copy content"
    assert any("copied instead" in msg for msg in caplog.text)


def test_process_folder_moves_files(temp_dirs):
    src_dir, dst_dir = temp_dirs
    old_time = time.time() - (syncmover.GRACE_PERIOD_MINUTES * 60) - 60

    create_test_file(os.path.join(src_dir, "a.txt"), "A", mtime=old_time)
    create_test_file(os.path.join(src_dir, "b.txt"), "B", mtime=old_time)
    create_test_file(os.path.join(src_dir, ".stfolder"), "", mtime=old_time)  # ignored

    syncmover.process_folder(src_dir, dst_dir)

    assert os.path.exists(os.path.join(dst_dir, "a.txt"))
    assert os.path.exists(os.path.join(dst_dir, "b.txt"))
    assert not os.path.exists(os.path.join(dst_dir, ".stfolder"))


def test_cleanup_folder_async_deletes_old_files(temp_dirs):
    src_dir, _ = temp_dirs
    now = time.time()
    old_time = now - (syncmover.CLEANUP_AFTER_HOURS * 3600) - 60

    # Create old files
    for i in range(3):
        create_test_file(os.path.join(src_dir, f"old_{i}.txt"), mtime=old_time)

    # Create recent files
    for i in range(2):
        create_test_file(os.path.join(src_dir, f"recent_{i}.txt"), mtime=now)

    syncmover.CLEANUP_BATCH_SIZE = 10
    syncmover.KEEP_RECENT_FILES = 0
    syncmover.cleanup_folder_async(src_dir, dry_run=False)

    time.sleep(1)  # allow async thread to finish

    remaining_files = os.listdir(src_dir)
    assert all("recent" in f for f in remaining_files)


def test_should_ignore_patterns_and_files():
    syncmover.IGNORE_FILES = {".stfolder"}
    syncmover.IGNORE_PATTERNS = (".syncthing.", ".tmp")

    assert syncmover.should_ignore(".stfolder")
    assert syncmover.should_ignore("file.syncthing.tmp")
    assert not syncmover.should_ignore("normalfile.txt")