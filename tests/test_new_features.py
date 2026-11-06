"""Regression checks for memory retrieval, calendar import, and bounded routines."""
import tempfile
import unittest
import sqlite3
import hashlib
import json
import re
import subprocess
import sys
import tomllib
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

from jarvis import memory, __version__
from jarvis.calendar_import import import_events
from jarvis.routines import validate_routine
from jarvis.reminders import parse_reminder_request
from jarvis.reply_worker import ReplyWorker
from jarvis.reply_controller import ReplyControllerMixin
from jarvis.voice_worker import VoiceActivationWorker
from jarvis.media_commands import parse_media_command
from jarvis import updater
from jarvis import diagnostics
from jarvis.extensions import load_extensions
from jarvis import providers, tts
from jarvis import usage
from jarvis.app import JarvisWindow


class NewFeatureTests(unittest.TestCase):
    def test_release_version_is_consistent_across_project_files(self):
        root = Path(__file__).resolve().parents[1]
        package = tomllib.loads(
            (root / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
        installer = (root / "installer" / "JarvisAI.iss").read_text(encoding="utf-8")
        release_notes = (root / "RELEASE_NOTES.md").read_text(encoding="utf-8")
        metadata = (root / "version_info.txt").read_text(encoding="utf-8")
        installer_version = re.search(r'#define AppVersion "([^"]+)"', installer).group(1)

        self.assertEqual(package, __version__)
        self.assertEqual(installer_version, __version__)
        self.assertTrue(release_notes.startswith(f"# JARVIS AI {__version__}"))
        self.assertIn(f"FileVersion', '{__version__}.0'", metadata)
        self.assertTrue((root / "assets" / "jarvis-ai-icon.png").is_file())
        self.assertTrue((root / "assets" / "jarvis-ai-icon.ico").is_file())

    def test_saved_message_markup_escapes_user_html(self):
        markup = JarvisWindow._message_markup(None, "user", "<script>alert(1)</script>")
        self.assertNotIn("<script>", markup)
        self.assertIn("&lt;script&gt;", markup)

    def test_streamed_answer_is_mirrored_in_both_conversations(self):
        class Window(ReplyControllerMixin):
            pass
        window = Window()
        window.core_orb = MagicMock()
        window.answer_preview = MagicMock()
        window.answer_preview.text.return_value = ""
        window.chat = MagicMock()
        window.dashboard_chat = MagicMock()
        main_cursor = MagicMock()
        dashboard_cursor = MagicMock()
        window.chat.textCursor.return_value = main_cursor
        window.dashboard_chat.textCursor.return_value = dashboard_cursor

        window._stream_reply_part("Olá, Matheus.")

        main_cursor.insertText.assert_called_once_with("Olá, Matheus.")
        dashboard_cursor.insertText.assert_called_once_with("Olá, Matheus.")
        self.assertTrue(window._stream_reply_started)
        self.assertTrue(window._dashboard_stream_reply_started)

    def test_declarative_extensions_accept_only_safe_commands(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "safe.json").write_text(json.dumps({
                "name": "Atalhos",
                "actions": [{"phrase": "meu navegador", "command": "abrir aplicativo: navegador"}],
            }), encoding="utf-8")
            (root / "unsafe.json").write_text(json.dumps({
                "name": "Perigoso",
                "actions": [{"phrase": "executar", "command": "abrir exe: C:\\\\malware.exe"}],
            }), encoding="utf-8")
            actions, errors = load_extensions(root)
        self.assertEqual(actions[0]["phrase"], "meu navegador")
        self.assertEqual(len(actions), 1)
        self.assertEqual(len(errors), 1)

    def test_neural_voice_falls_back_to_system_voice(self):
        with patch("jarvis.tts.load_settings", return_value={"tts_engine": "piper"}), \
             patch("jarvis.tts._piper_speak", side_effect=RuntimeError("modelo ausente")), \
             patch("jarvis.tts._system_speak") as system_voice:
            tts.speak_text("Olá")
        system_voice.assert_called_once_with("Olá")

    def test_windows_voice_initializes_com_in_each_speech_thread(self):
        windows_com = MagicMock()
        with patch.object(tts.os, "name", "nt"), \
             patch.dict(sys.modules, {"pythoncom": windows_com}):
            with tts._speech_thread_context():
                pass
        windows_com.CoInitialize.assert_called_once_with()
        windows_com.CoUninitialize.assert_called_once_with()

    def test_regular_app_import_does_not_start_webengine(self):
        check = (
            "import sys; import jarvis.app; "
            "assert not any(name.startswith('PySide6.QtWebEngine') for name in sys.modules)"
        )
        result = subprocess.run(
            [sys.executable, "-c", check],
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_media_commands_preserve_query_and_window_intent(self):
        command = parse_media_command("toca música de Daft Punk em janela")
        self.assertIsNotNone(command)
        self.assertEqual(command.action, "search")
        self.assertEqual(command.query, "Daft Punk")
        self.assertTrue(command.window)

        self.assertEqual(parse_media_command("pausar música").action, "pause")
        self.assertEqual(parse_media_command("próxima da fila").action, "next")
        self.assertIsNone(parse_media_command("qual é a previsão do tempo"))

    def test_api_usage_counter_is_local_and_grouped(self):
        with tempfile.TemporaryDirectory() as folder, \
             patch.object(usage, "USAGE_FILE", Path(folder) / "usage.json"):
            usage.record("chat")
            usage.record("transcription", 2)
            result = usage.today()
        self.assertEqual(result["total"], 3)
        self.assertEqual(result["categories"], {"chat": 1, "transcription": 2})

    def test_diagnostics_never_exports_secret_values(self):
        secret = "super-secret-api-key"
        with patch("jarvis.diagnostics.get_secret", return_value=secret), \
             patch("jarvis.diagnostics.load_settings", return_value={
                 "hands_free_enabled": True,
                 "quick_actions": [{"phrase": "informação privada"}],
                 "unknown_private_value": secret,
             }):
            serialized = str(diagnostics.build_report())
        self.assertNotIn(secret, serialized)
        self.assertNotIn("informação privada", serialized)
        self.assertIn("'gemini_key': True", serialized)

    def test_memory_export_and_import_round_trip(self):
        with tempfile.TemporaryDirectory() as folder:
            database = Path(folder) / "memory.sqlite3"
            exported = Path(folder) / "exported.sqlite3"
            with patch.object(memory, "DB_FILE", database):
                memory.save_memory("Primeira", "lembrança preservada")
                memory.export_database(exported)
                memory.save_memory("Segunda", "não deve sobreviver à restauração")
                backup = memory.import_database(exported)
                restored = " ".join(memory.context_for_ai("lembrança preservada"))
                removed = " ".join(memory.context_for_ai("não deve sobreviver"))
                self.assertIn("lembrança preservada", restored)
                self.assertNotIn("não deve sobreviver", removed)
                self.assertTrue(backup and backup.is_file())

    def test_update_installer_requires_matching_sha256(self):
        payload = b"signed release payload"
        checksum = hashlib.sha256(payload).hexdigest().encode("ascii")
        with tempfile.TemporaryDirectory() as folder, \
             patch.object(updater, "UPDATE_DIR", Path(folder)), \
             patch.object(updater, "HISTORY_FILE", Path(folder) / "verified-installers.json"), \
             patch.object(updater, "_read_url", side_effect=[checksum, payload]):
            result = updater.download_verified_installer(
                "https://github.com/example/setup.exe",
                "https://github.com/example/setup.exe.sha256", "setup.exe")
            self.assertEqual(result.read_bytes(), payload)

    def test_update_installer_discards_hash_mismatch(self):
        with tempfile.TemporaryDirectory() as folder, \
             patch.object(updater, "UPDATE_DIR", Path(folder)), \
             patch.object(updater, "_read_url", side_effect=[b"0" * 64, b"changed"]):
            with self.assertRaises(RuntimeError):
                updater.download_verified_installer(
                    "https://github.com/example/setup.exe",
                    "https://github.com/example/setup.exe.sha256", "setup.exe")
            self.assertEqual(list(Path(folder).iterdir()), [])

    def test_update_history_returns_only_verified_previous_installer(self):
        with tempfile.TemporaryDirectory() as folder, \
             patch.object(updater, "UPDATE_DIR", Path(folder)), \
             patch.object(updater, "HISTORY_FILE", Path(folder) / "verified-installers.json"):
            first = Path(folder) / "JARVIS-AI-Setup-1.0.0.exe"
            second = Path(folder) / "JARVIS-AI-Setup-2.0.0.exe"
            first.write_bytes(b"first")
            second.write_bytes(b"second")
            updater._record_verified_installer(first, hashlib.sha256(b"first").hexdigest())
            updater._record_verified_installer(second, hashlib.sha256(b"second").hexdigest())
            self.assertEqual(updater.previous_verified_installer(), first)
            first.write_bytes(b"tampered")
            self.assertIsNone(updater.previous_verified_installer())

    def test_existing_database_is_migrated_without_losing_memories(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "memory.sqlite3"
            with sqlite3.connect(path) as db:
                db.execute("CREATE TABLE long_term_memory (id INTEGER PRIMARY KEY, title TEXT NOT NULL, body TEXT NOT NULL, created_at TEXT NOT NULL)")
                db.execute("CREATE TABLE reminders (id INTEGER PRIMARY KEY, title TEXT NOT NULL, due_at TEXT NOT NULL, notify_at TEXT NOT NULL, notified_at TEXT, created_at TEXT NOT NULL)")
                db.execute("INSERT INTO long_term_memory(title, body, created_at) VALUES ('Plano antigo', 'matemática', '2021-01-01')")
            db.close()
            with patch.object(memory, "DB_FILE", path):
                self.assertIn("matemática", " ".join(memory.context_for_ai("plano antigo")))
                self.assertEqual(memory.long_term_count(), 1)
                with sqlite3.connect(path) as db:
                    self.assertIn("repeat_rule", {row[1] for row in db.execute("PRAGMA table_info(reminders)")})
                db.close()

    def test_old_relevant_memory_is_retrieved_and_deleted_from_search(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(memory, "DB_FILE", Path(folder) / "memory.sqlite3"):
                old_id = memory.save_memory("Planejamento escolar", "trabalho de matemática em novembro")
                for index in range(20):
                    memory.save_memory(f"Nota {index}", "assunto diferente")
                self.assertIn("matemática", " ".join(memory.context_for_ai("planejamento escolar")))
                memory.delete_saved_item("memory", old_id)
                self.assertNotIn("matemática", " ".join(memory.context_for_ai("planejamento escolar")))

    def test_calendar_import_schedules_previous_day_and_skips_old_event(self):
        now = datetime(2026, 10, 31, 10, tzinfo=timezone.utc)
        sample = ("BEGIN:VCALENDAR\nBEGIN:VEVENT\nSUMMARY:Prova de matemática\n"
                  "DTSTART:20271118T090000Z\nEND:VEVENT\nBEGIN:VEVENT\n"
                  "SUMMARY:Evento antigo\nDTSTART:20250101T090000Z\n"
                  "END:VEVENT\nEND:VCALENDAR\n")
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "school.ics"
            path.write_text(sample, encoding="utf-8")
            events, skipped = import_events(str(path), now=now)
        self.assertEqual((len(events), skipped), (1, 1))
        self.assertEqual(events[0]["remind_at"], "2027-11-17T09:00:00+00:00")

    def test_daily_reminder_creates_next_occurrence_after_delivery(self):
        now = datetime(2026, 10, 31, 10, tzinfo=timezone.utc)
        parsed = parse_reminder_request("me lembra de revisar todo dia às 9", now=now)
        self.assertEqual(parsed["repeat_rule"], "daily")
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(memory, "DB_FILE", Path(folder) / "memory.sqlite3"):
                memory.save_reminder(parsed["title"], parsed["due_at"],
                                     parsed["remind_at"], parsed["repeat_rule"])
                due = memory.due_reminders("2026-11-01T09:00:00+00:00")
                self.assertEqual(len(due), 1)
                memory.mark_reminders_notified(
                    [due[0][0]], now="2026-11-01T09:00:00+00:00")
                next_due = memory.due_reminders("2026-11-02T09:00:00+00:00")
                self.assertEqual(len(next_due), 1)
                self.assertNotEqual(next_due[0][0], due[0][0])

    def test_routine_rejects_unrelated_or_unbounded_commands(self):
        routine = validate_routine("Estudo", "modo estudo",
                                   ["abrir aplicativo: Calculadora", "toca música para estudar"])
        self.assertEqual(len(routine["commands"]), 2)
        with self.assertRaises(ValueError):
            validate_routine("X", "x", ["enviar mensagem para alguém"])
        with self.assertRaises(ValueError):
            validate_routine("X", "x", ["abrir painel"] * 9)

    def test_reply_emits_partial_text_before_final_result(self):
        worker = ReplyWorker("explique algo")
        events = []
        worker.partial_text.connect(lambda value: events.append(("part", value)))
        worker.finished_text.connect(lambda value: events.append(("done", value)))
        with patch("jarvis.reply_worker.stream_assistant", return_value=iter(["Olá", " mundo"])):
            worker.run()
        self.assertEqual(events, [("part", "Olá"), ("part", " mundo"),
                                  ("done", "__STREAM_DONE__Olá mundo")])

    def test_greetings_reply_locally_without_calling_gemini(self):
        worker = ReplyWorker("Alô, Jarvis?")
        events = []
        worker.partial_text.connect(lambda value: events.append(("part", value)))
        worker.finished_text.connect(lambda value: events.append(("done", value)))
        with patch("jarvis.reply_worker.stream_assistant") as cloud:
            worker.run()
        cloud.assert_not_called()
        self.assertEqual(events[0], ("part", "Olá! Estou ouvindo. Como posso ajudar?"))
        self.assertTrue(events[1][1].startswith("__STREAM_DONE__"))

    def test_gemini_requests_use_low_thinking_and_short_timeout(self):
        config = providers._config()
        self.assertEqual(config.thinking_config.thinking_level.value, "LOW")
        self.assertEqual(providers.REQUEST_TIMEOUT_MS, 15_000)
        error = providers._network_error(TimeoutError("The read operation timed out"))
        self.assertIn("15 segundos", str(error))

    def test_local_wake_filter_skips_cloud_transcription_for_other_speech(self):
        worker = VoiceActivationWorker("jarvis_local")
        def detect_once(*args, **kwargs):
            worker._stop_event.set()
            return b"wav"
        with patch("jarvis.local_wake.LocalJarvisFilter") as detector, \
             patch("jarvis.voice_worker.wait_for_spoken_utterance", side_effect=detect_once), \
             patch("jarvis.voice_worker.transcribe_gemini") as transcribe:
            detector.return_value.heard_jarvis.return_value = False
            worker._listen_loop(stream=object())
        transcribe.assert_not_called()

    def test_local_wake_accepts_command_when_cloud_omits_jarvis(self):
        worker = VoiceActivationWorker("jarvis_local")
        heard = []
        worker.phrase.connect(heard.append)
        class Stream:
            def stop(self):
                pass
        def detect_once(*args, **kwargs):
            worker._stop_event.set()
            return b"wav"
        with patch("jarvis.local_wake.LocalJarvisFilter") as detector, \
             patch("jarvis.voice_worker.wait_for_spoken_utterance", side_effect=detect_once), \
             patch("jarvis.voice_worker.transcribe_gemini", return_value="Abra o navegador"):
            detector.return_value.heard_jarvis.return_value = True
            worker._listen_loop(stream=Stream())
        self.assertEqual(heard, ["Abra o navegador"])


if __name__ == "__main__":
    unittest.main()
