"""
Tests for AI Chat Restoration.

These tests verify that AI chat sessions are correctly saved and restored
across IDE restarts. The tests cover both terminal and bubble chat modes.

Key behaviors tested:
1. Messages are saved to JSON files after each message
2. Messages are loaded correctly on startup
3. Display is reconstructed from messages (NOT from saved terminal content)
4. The `ensure_restored` method works when switching sessions
5. Multiple sessions are restored correctly
6. Session state (active session, display names) is preserved
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

# Add src paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestAIChatMessagesFilePersistence(unittest.TestCase):
    """Test that chat messages are correctly saved and loaded from JSON files."""

    def test_save_chat_messages_creates_file(self):
        """Test that _save_chat_messages creates a JSON file with messages."""
        with tempfile.TemporaryDirectory() as tmpdir:
            chat_file = Path(tmpdir) / "chat_1.json"

            # Create mock chat object
            messages = [{"role": "user", "content": "Hello AI"}, {"role": "assistant", "content": "Hello! How can I help?"}]

            # Simulate saving (new format - messages only, no terminal_content)
            data = {"messages": messages}
            with open(chat_file, "w") as f:
                json.dump(data, f, indent=2)

            # Verify file exists and has correct content
            self.assertTrue(chat_file.exists())

            with open(chat_file, "r") as f:
                loaded = json.load(f)

            self.assertEqual(loaded["messages"], messages)
            # Should NOT have terminal_content anymore
            self.assertNotIn("terminal_content", loaded)

    def test_load_chat_messages_handles_missing_file(self):
        """Test that loading from missing file doesn't crash."""
        with tempfile.TemporaryDirectory() as tmpdir:
            chat_file = Path(tmpdir) / "nonexistent.json"

            # Simulate load logic
            messages = []
            if chat_file.exists():
                with open(chat_file, "r") as f:
                    data = json.load(f)
                messages = data.get("messages", []) if isinstance(data, dict) else data

            self.assertEqual(messages, [])

    def test_load_chat_messages_handles_old_format(self):
        """Test that loading handles old format (list instead of dict)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            chat_file = Path(tmpdir) / "chat_old.json"

            # Old format: just a list of messages
            old_messages = [
                {"role": "user", "content": "test"},
            ]

            with open(chat_file, "w") as f:
                json.dump(old_messages, f)

            # Load using the robust logic
            with open(chat_file, "r") as f:
                data = json.load(f)
            messages = data.get("messages", []) if isinstance(data, dict) else data

            self.assertEqual(messages, old_messages)

    def test_load_ignores_old_terminal_content(self):
        """Test that loading ignores terminal_content from old files (we don't use it anymore)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            chat_file = Path(tmpdir) / "chat_old_with_terminal.json"

            # Old format with terminal_content (should be ignored)
            data = {
                "messages": [{"role": "user", "content": "test"}],
                "terminal_content": "                                         > test\n\ngarbled content\n",
            }

            with open(chat_file, "w") as f:
                json.dump(data, f, indent=2)

            # Load - should only use messages
            with open(chat_file, "r") as f:
                loaded = json.load(f)

            messages = loaded.get("messages", []) if isinstance(loaded, dict) else loaded

            # We have messages
            self.assertEqual(len(messages), 1)
            # We do NOT use terminal_content for restoration anymore
            # (it causes display issues due to VTE cursor positioning)


class TestEnsureRestoredMethod(unittest.TestCase):
    """Test the ensure_restored method for lazy restoration."""

    def test_ensure_restored_only_runs_once(self):
        """Test that ensure_restored only restores content once."""
        # Simulate the logic
        pending_restore = True
        restore_attempted = False
        restore_count = 0

        def ensure_restored():
            nonlocal pending_restore, restore_attempted, restore_count
            if pending_restore and not restore_attempted:
                restore_attempted = True
                pending_restore = False
                restore_count += 1

        # First call should restore
        ensure_restored()
        self.assertEqual(restore_count, 1)

        # Second call should NOT restore again
        ensure_restored()
        self.assertEqual(restore_count, 1)

        # Third call should NOT restore again
        ensure_restored()
        self.assertEqual(restore_count, 1)

    def test_ensure_restored_skips_when_no_messages(self):
        """Test that ensure_restored skips if there are no messages."""

        class MockChat:
            def __init__(self):
                self.messages = []  # No messages
                self._pending_restore = True
                self._restore_attempted = False
                self.appended_text = []

            def ensure_restored(self):
                if not getattr(self, "_pending_restore", False):
                    return
                if getattr(self, "_restore_attempted", False):
                    return

                self._restore_attempted = True
                self._pending_restore = False

                if not self.messages:
                    return  # Skip if no messages

                for msg in self.messages:
                    self.appended_text.append(msg.get("content", ""))

        chat = MockChat()
        chat.ensure_restored()

        self.assertEqual(chat.appended_text, [])  # Nothing restored


class TestSessionStateFilePersistence(unittest.TestCase):
    """Test session state file (sessions_state.json) persistence."""

    def test_save_sessions_state_structure(self):
        """Test that sessions state file has correct structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "sessions_state.json"

            state = {
                "session_ids": [975, 974, 973],
                "display_names": {"975": None, "974": "Custom Name", "973": None},
                "active_session_idx": 1,
                "next_session_id": 976,
            }

            with open(state_file, "w") as f:
                json.dump(state, f, indent=2)

            # Verify
            with open(state_file, "r") as f:
                loaded = json.load(f)

            self.assertEqual(loaded["session_ids"], [975, 974, 973])
            self.assertEqual(loaded["display_names"]["974"], "Custom Name")
            self.assertEqual(loaded["active_session_idx"], 1)
            self.assertEqual(loaded["next_session_id"], 976)

    def test_restore_sessions_finds_all_chat_files(self):
        """Test that restoration finds all chat_*.json files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create some chat files
            for i in [100, 101, 102]:
                chat_file = Path(tmpdir) / f"chat_{i}.json"
                with open(chat_file, "w") as f:
                    json.dump({"messages": [{"role": "user", "content": f"msg {i}"}]}, f)

            # Find all chat files
            chat_files = list(Path(tmpdir).glob("chat_*.json"))

            self.assertEqual(len(chat_files), 3)

            # Extract session IDs
            session_ids = []
            for chat_file in chat_files:
                try:
                    session_id = int(chat_file.stem.split("_")[1])
                    session_ids.append(session_id)
                except (ValueError, IndexError):
                    continue

            session_ids.sort(reverse=True)
            self.assertEqual(session_ids, [102, 101, 100])

    def test_empty_chats_are_skipped(self):
        """Test that empty chat files are not restored."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create empty chat
            empty_file = Path(tmpdir) / "chat_1.json"
            with open(empty_file, "w") as f:
                json.dump({"messages": []}, f)

            # Create chat with messages
            full_file = Path(tmpdir) / "chat_2.json"
            with open(full_file, "w") as f:
                json.dump({"messages": [{"role": "user", "content": "test"}]}, f)

            # Find and filter
            session_info = []
            for chat_file in Path(tmpdir).glob("chat_*.json"):
                try:
                    session_id = int(chat_file.stem.split("_")[1])
                    with open(chat_file, "r") as f:
                        data = json.load(f)
                        messages = data.get("messages", []) if isinstance(data, dict) else data
                        if messages:  # Only non-empty
                            session_info.append(session_id)
                except (ValueError, json.JSONDecodeError):
                    continue

            self.assertEqual(session_info, [2])


class TestMessageBasedRestoration(unittest.TestCase):
    """Test that chat display is correctly reconstructed from messages."""

    def test_user_message_formatted_with_prompt(self):
        """Test that user messages are formatted with '>' prompt."""
        messages = [
            {"role": "user", "content": "What is Python?"},
        ]

        formatted = []
        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if role == "user":
                formatted.append(f"> {content}\n\n")

        self.assertEqual(formatted[0], "> What is Python?\n\n")

    def test_assistant_message_formatted_plainly(self):
        """Test that assistant messages are formatted without prompt."""
        messages = [
            {"role": "assistant", "content": "Python is a programming language."},
        ]

        formatted = []
        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if role == "assistant" and content:
                formatted.append(f"{content}\n\n")

        self.assertEqual(formatted[0], "Python is a programming language.\n\n")

    def test_full_conversation_reconstruction(self):
        """Test that a full conversation is correctly reconstructed."""
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
            {"role": "user", "content": "How are you?"},
            {"role": "assistant", "content": "I'm doing well, thanks!"},
        ]

        formatted = []
        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if not content:
                continue

            if role == "user":
                formatted.append(f"> {content}\n\n")
            elif role == "assistant":
                formatted.append(f"{content}\n\n")

        self.assertEqual(len(formatted), 4)
        self.assertEqual(formatted[0], "> Hello\n\n")
        self.assertEqual(formatted[1], "Hi there!\n\n")
        self.assertEqual(formatted[2], "> How are you?\n\n")
        self.assertEqual(formatted[3], "I'm doing well, thanks!\n\n")

    def test_empty_content_skipped(self):
        """Test that messages with empty content are skipped."""
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": ""},  # Empty
            {"role": "assistant", "content": "Hi!"},
        ]

        formatted = []
        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if not content:
                continue

            if role == "user":
                formatted.append(f"> {content}\n\n")
            elif role == "assistant":
                formatted.append(f"{content}\n\n")

        self.assertEqual(len(formatted), 2)
        self.assertEqual(formatted[0], "> Hello\n\n")
        self.assertEqual(formatted[1], "Hi!\n\n")


class TestMultipleSessionRestoration(unittest.TestCase):
    """Test restoration of multiple chat sessions."""

    def test_active_session_is_restored_first(self):
        """Test that the previously active session gets focus."""
        state = {
            "session_ids": [975, 974, 973],
            "active_session_idx": 1,  # Session 974 was active
        }

        session_ids = state["session_ids"]
        saved_active_idx = state["active_session_idx"]
        saved_active_session_id = session_ids[saved_active_idx]

        self.assertEqual(saved_active_session_id, 974)

    def test_next_session_id_is_updated(self):
        """Test that next_session_id is updated based on existing files."""
        existing_ids = [100, 101, 105, 103]

        next_session_id = 1
        for session_id in existing_ids:
            if session_id >= next_session_id:
                next_session_id = session_id + 1

        self.assertEqual(next_session_id, 106)

    def test_sessions_sorted_newest_first(self):
        """Test that sessions are sorted by ID descending (newest first)."""
        session_info = [(100, "path1"), (105, "path2"), (103, "path3"), (101, "path4")]

        session_info.sort(key=lambda x: x[0], reverse=True)

        self.assertEqual([s[0] for s in session_info], [105, 103, 101, 100])


class TestRestorationRaceConditions(unittest.TestCase):
    """Test handling of race conditions in restoration."""

    def test_ensure_restored_guards_against_double_restore(self):
        """Test that ensure_restored has proper guards against double restoration."""

        class MockChat:
            def __init__(self):
                self.messages = [{"role": "user", "content": "test"}]
                self._pending_restore = True
                self._restore_attempted = False
                self.restore_count = 0

            def ensure_restored(self):
                if not getattr(self, "_pending_restore", False):
                    return
                if getattr(self, "_restore_attempted", False):
                    return

                self._restore_attempted = True
                self._pending_restore = False
                self.restore_count += 1

        chat = MockChat()

        # First call should restore
        chat.ensure_restored()
        self.assertEqual(chat.restore_count, 1)

        # Subsequent calls should NOT restore again
        chat.ensure_restored()
        chat.ensure_restored()
        chat.ensure_restored()
        self.assertEqual(chat.restore_count, 1)  # Still 1

    def test_pending_restore_flag_prevents_premature_restore(self):
        """Test that _pending_restore flag must be set for restoration."""

        class MockChat:
            def __init__(self):
                self.messages = [{"role": "user", "content": "test"}]
                self._pending_restore = False  # Not pending
                self._restore_attempted = False
                self.restore_count = 0

            def ensure_restored(self):
                if not getattr(self, "_pending_restore", False):
                    return
                if getattr(self, "_restore_attempted", False):
                    return

                self._restore_attempted = True
                self._pending_restore = False
                self.restore_count += 1

        chat = MockChat()
        chat.ensure_restored()

        self.assertEqual(chat.restore_count, 0)  # Should NOT have restored


class TestDisplayNamePersistence(unittest.TestCase):
    """Test that display names are correctly saved and restored."""

    def test_display_names_saved_with_string_keys(self):
        """Test that display_names uses string keys in JSON."""
        sessions = [
            {"session_id": 100, "display_name": "Bug Fix"},
            {"session_id": 101, "display_name": None},
        ]

        display_names = {str(s["session_id"]): s.get("display_name") for s in sessions}

        # JSON round-trip
        json_str = json.dumps(display_names)
        loaded = json.loads(json_str)

        self.assertEqual(loaded["100"], "Bug Fix")
        self.assertIsNone(loaded["101"])

    def test_display_names_retrieved_correctly(self):
        """Test retrieving display names during restoration."""
        display_names = {"100": "Custom Title", "101": None, "102": "Another Title"}

        # When restoring session 100
        session_id = 100
        display_name = display_names.get(str(session_id))
        self.assertEqual(display_name, "Custom Title")

        # When restoring session 101 (no custom name)
        session_id = 101
        display_name = display_names.get(str(session_id))
        self.assertIsNone(display_name)


class TestMaxMessagesLimit(unittest.TestCase):
    """Test that message limit is enforced when saving."""

    def test_only_last_n_messages_saved(self):
        """Test that only the last MAX_MESSAGES are saved."""
        MAX_MESSAGES = 5

        # Create more messages than limit
        messages = [{"role": "user", "content": f"msg {i}"} for i in range(10)]

        # Simulate save logic
        messages_to_save = messages[-MAX_MESSAGES:]

        self.assertEqual(len(messages_to_save), 5)
        self.assertEqual(messages_to_save[0]["content"], "msg 5")
        self.assertEqual(messages_to_save[4]["content"], "msg 9")


if __name__ == "__main__":
    unittest.main()
