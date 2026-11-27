"""Serialize apk add/del and wait for the Alpine apk database lock."""
from __future__ import annotations

import fcntl
import os
import subprocess
import threading
import time

JOB_LOCK = threading.Lock()
LOCK_PATHS = ("/lib/apk/db/lock", "/var/lib/apk/lock")
BUSY_HINTS = (
    "Unable to lock database",
    "Failed to open apk database",
    "Resource temporarily unavailable",
)


def _apk_process_running():
    try:
        out = subprocess.check_output(["pgrep", "-x", "apk"], stderr=subprocess.DEVNULL, text=True)
        pids = [int(p) for p in out.split() if p.strip().isdigit()]
        return any(pid != os.getpid() for pid in pids)
    except (subprocess.CalledProcessError, FileNotFoundError, ValueError, OSError):
        return False


def apk_lock_held():
    if _apk_process_running():
        return True
    for path in LOCK_PATHS:
        if not os.path.exists(path):
            continue
        fd = None
        try:
            fd = os.open(path, os.O_RDWR)
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(fd, fcntl.LOCK_UN)
            return False
        except (BlockingIOError, OSError):
            # If the file exists but we cannot take the lock, treat as busy.
            # Permission errors also mean we should not race apk.
            return True
        finally:
            if fd is not None:
                try:
                    os.close(fd)
                except OSError:
                    pass
    return False


def wait_for_apk(progress=None, timeout=120):
    """Wait up to timeout seconds for the apk lock. Return True if free."""
    deadline = time.time() + max(1, int(timeout))
    delay = 0.4
    announced = False
    while True:
        if not apk_lock_held():
            return True
        if time.time() >= deadline:
            return False
        if progress is not None and not announced:
            progress("Waiting for another install to finish…")
            announced = True
        time.sleep(delay)
        delay = min(delay * 1.6, 3.0)


def is_lock_error(text):
    text = text or ""
    return any(h.lower() in text.lower() for h in BUSY_HINTS)


def run_apk(apk_args, progress=None, timeout=600):
    """
    Run `sudo -n apk --no-progress <apk_args>` once the lock is free.
    Retries with backoff for up to `timeout` seconds if apk still reports a lock error.
    """
    with JOB_LOCK:
        if not wait_for_apk(progress=progress, timeout=min(120, timeout)):
            return 1, "Another install is still running. Try again in a moment."
        cmd = ["sudo", "-n", "apk", "--no-progress"] + list(apk_args)
        deadline = time.time() + max(30, int(timeout))
        delay = 0.8
        log_all = []
        while True:
            remaining = max(5, deadline - time.time())
            try:
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                )
                lines = []
                assert proc.stdout is not None
                for line in proc.stdout:
                    line = line.rstrip("\n")
                    lines.append(line)
                    if progress:
                        progress(line)
                rc = proc.wait(timeout=remaining)
                text = "\n".join(lines)
                log_all.append(text)
                if rc == 0:
                    return 0, text
                if is_lock_error(text) and time.time() + delay < deadline:
                    if progress:
                        progress("Waiting for another install to finish…")
                    time.sleep(delay)
                    delay = min(delay * 1.6, 3.0)
                    if not wait_for_apk(progress=progress, timeout=max(1, deadline - time.time())):
                        return 1, text or "Another install is still running. Try again in a moment."
                    continue
                return rc, text
            except subprocess.TimeoutExpired:
                try:
                    proc.kill()
                except Exception:
                    pass
                return 124, "The package command timed out."
            except OSError as e:
                return 1, str(e)
