import json
import os
import tempfile
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path
from queue import Queue

from codex_pet_companion.core.bridge import CodexBridge


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        (self.home / "sessions").mkdir()
        self.queue = Queue()
        self.bridge = CodexBridge(self.home, {
            "codexAutoPathsEnabled": False, "sessionGlob": "sessions/*.jsonl",
            "bridgeStartFresh": True, "bridgeIgnoreExistingSessionTail": True,
        }, self.queue)
        self.bridge.codex_homes = [self.home]
        self.bridge._last_candidate_scan_at = time.time()
        # Treat initial fixture files as sessions that predate bridge startup.
        self.bridge.started_at = time.time() + 10

    def record(self, kind="task_started", **fields):
        return (json.dumps({"timestamp": datetime.now(timezone.utc).isoformat(),
                            "type": "event_msg", "payload": {"type": kind, **fields}},
                           ensure_ascii=False) + "\n").encode("utf-8")

    def append(self, path, data):
        stamp = path.stat().st_mtime
        with path.open("ab") as f:
            f.write(data)
        # Reproduce a Windows writer whose LastWriteTime does not advance.
        os.utime(path, (stamp, stamp))

    def events(self):
        events = []
        while not self.queue.empty():
            event = self.queue.get_nowait()
            if not event["action"].startswith("__"):
                events.append(event)
        return events

    def baseline(self, *names):
        paths = [self.home / "sessions" / name for name in names]
        for i, p in enumerate(paths):
            p.write_bytes(self.record())
            stamp = time.time() - 7200 + i * 100
            os.utime(p, (stamp, stamp))
        self.bridge.poll_once()
        self.assertEqual(self.events(), [])
        return paths

    def test_growth_with_old_unchanged_mtime(self):
        old, newer = self.baseline("rollout-old.jsonl", "rollout-newer.jsonl")
        self.append(old, self.record())
        self.bridge.poll_once()
        events = self.events()
        self.assertEqual([e["action"] for e in events], ["codex_running"])
        self.assertEqual(events[0]["session_file"], str(old))
        self.assertEqual(self.bridge.active_session_file, str(old))
        self.bridge.poll_once()
        self.assertEqual(self.events(), [])
        self.assertEqual(self.bridge.active_session_file, str(old))

    def test_multiple_sessions_are_not_starved_or_cross_debounced(self):
        a, b = self.baseline("rollout-a.jsonl", "rollout-b.jsonl")
        self.append(a, self.record("user_message", message="Task A"))
        self.append(b, self.record("user_message", message="Task B"))
        self.bridge.poll_once()
        self.assertEqual({e["task_title"] for e in self.events()}, {"Task A", "Task B"})
        self.append(a, self.record("task_complete"))
        self.bridge.poll_once()
        event = self.events()[0]
        self.assertEqual(event["action"], "review_ready")
        self.assertEqual(event["task_title"], "Task A")

    def test_partial_json_and_split_utf8_are_retained(self):
        path, = self.baseline("rollout-partial.jsonl")
        record = self.record("user_message", message="电视机测试")
        cut = record.index("电".encode()) + 1
        offset = self.bridge.offsets[str(path.resolve())]
        self.append(path, record[:cut])
        self.bridge.poll_once()
        self.assertEqual(self.events(), [])
        self.assertEqual(self.bridge.offsets[str(path.resolve())], offset)
        self.append(path, record[cut:])
        self.bridge.poll_once()
        self.assertEqual(self.events()[0]["task_title"], "电视机测试")
        self.bridge.poll_once()
        self.assertEqual(self.events(), [])

    def test_truncated_log_is_read_from_start(self):
        path, = self.baseline("rollout-truncated.jsonl")
        self.append(path, b" " * 500 + b"\n")
        self.bridge.poll_once()
        path.write_bytes(self.record("task_complete"))
        self.bridge.poll_once()
        self.assertEqual(self.events()[0]["action"], "review_ready")

    def test_new_session_is_followed(self):
        self.baseline("rollout-existing.jsonl")
        self.bridge.started_at = time.time() - 1
        path = self.home / "sessions/rollout-new.jsonl"
        path.write_bytes(self.record())
        self.bridge.poll_once()
        self.assertEqual(self.events()[0]["action"], "codex_running")

    def test_old_event_content_is_still_filtered(self):
        path, = self.baseline("rollout-history.jsonl")
        stale = json.loads(self.record())
        stale["timestamp"] = "2000-01-01T00:00:00Z"
        self.append(path, (json.dumps(stale) + "\n").encode())
        self.bridge.poll_once()
        self.assertEqual(self.events(), [])

    def test_start_without_fresh_mode_reads_existing_events(self):
        path = self.home / "sessions/rollout-replay.jsonl"
        path.write_bytes(self.record())
        self.bridge.config["bridgeStartFresh"] = False
        self.bridge.poll_once()
        self.assertEqual(self.events()[0]["action"], "codex_running")

    def test_missing_file_does_not_block_other_sessions(self):
        a, b = self.baseline("rollout-a.jsonl", "rollout-b.jsonl")
        self.append(b, self.record())
        a.unlink()
        self.bridge.poll_once()
        self.assertEqual(self.events()[0]["session_file"], str(b))


if __name__ == "__main__":
    unittest.main()
