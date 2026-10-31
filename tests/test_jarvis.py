"""Core regression checks for activation, reminders and permission gates."""
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWebEngineCore import QWebEnginePermission
from PySide6.QtWidgets import QMessageBox
from jarvis import memory
from jarvis.app import JarvisWindow, WhatsAppWebDialog
from jarvis.reminders import parse_reminder_request
from jarvis.voice import strip_jarvis_prefix


class JarvisRegressionTests(unittest.TestCase):
    def test_jarvis_prefix_and_unrelated_speech(self):
        self.assertEqual(strip_jarvis_prefix("Jarvis, abra o navegador"), "abra o navegador")
        self.assertEqual(strip_jarvis_prefix("jarvis"), "")
        self.assertIsNone(strip_jarvis_prefix("abra o navegador"))
        self.assertIsNone(strip_jarvis_prefix("Jarvisinho abra"))

    def test_reminder_survives_sqlite_reopen_and_alerts_one_day_before(self):
        now = datetime(2026, 10, 31, 10, tzinfo=timezone(timedelta(hours=-3)))
        parsed = parse_reminder_request(
            "Jarvis, me lembra 1 dia antes de entregar trabalho dia 18/11/2027", now=now)
        self.assertIsNotNone(parsed)
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(memory, "DB_FILE", Path(folder) / "memory.sqlite3"):
                memory.save_reminder(parsed["title"], parsed["due_at"], parsed["remind_at"])
                self.assertEqual(memory.pending_reminder_count(), 1)
                alert = datetime.fromisoformat(parsed["remind_at"]).astimezone(timezone.utc)
                due = memory.due_reminders(alert.isoformat(timespec="seconds"))
                self.assertEqual(len(due), 1)
                memory.mark_reminders_notified([due[0][0]])
                self.assertEqual(memory.due_reminders(alert.isoformat(timespec="seconds")), [])

    def test_screen_action_sends_capture_without_extra_notice(self):
        class Window:
            def _handle_media_command(self, prompt): return False
            def _start(self, prompt, mode): self.started = (prompt, mode)
        window = Window()
        with patch("jarvis.app.load_settings", return_value={}), \
             patch("jarvis.app.get_secret", return_value="key"), \
             patch.object(QMessageBox, "warning", side_effect=AssertionError("extra notice")):
            self.assertTrue(JarvisWindow._dispatch_computer_command(window, "agir: clique no Salvar"))
        self.assertEqual(window.started, ("clique no Salvar", "plan"))

    def test_click_still_requires_confirmation(self):
        class Window:
            def _handle_media_command(self, prompt): return False
            def _record_control_action(self, *args): raise AssertionError("clicked")
        with patch("jarvis.app.load_settings", return_value={}), \
             patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.No):
            self.assertTrue(JarvisWindow._dispatch_computer_command(Window(), "clicar"))

    def test_whatsapp_media_permission_restricted_to_official_host(self):
        class Origin:
            def __init__(self, host): self._host = host
            def host(self): return self._host
        class Permission:
            def __init__(self, host): self._origin = Origin(host); self.result = None
            def isValid(self): return True
            def origin(self): return self._origin
            def permissionType(self): return QWebEnginePermission.PermissionType.MediaAudioCapture
            def grant(self): self.result = "granted"
            def deny(self): self.result = "denied"
        trusted = Permission("web.whatsapp.com")
        untrusted = Permission("web.whatsapp.com.evil.example")
        WhatsAppWebDialog._handle_web_permission(None, trusted)
        WhatsAppWebDialog._handle_web_permission(None, untrusted)
        self.assertEqual(trusted.result, "granted")
        self.assertEqual(untrusted.result, "denied")


if __name__ == "__main__":
    unittest.main()
