"""Regression checks for memory retrieval, calendar import, and bounded routines."""
import tempfile
import unittest
import sqlite3
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from jarvis import memory
from jarvis.calendar_import import import_events
from jarvis.routines import validate_routine
from jarvis.reminders import parse_reminder_request
from jarvis.reply_worker import ReplyWorker
from jarvis.voice_worker import VoiceActivationWorker
from jarvis import updater


class NewFeatureTests(unittest.TestCase):
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
        worker = ReplyWorker("olá")
        events = []
        worker.partial_text.connect(lambda value: events.append(("part", value)))
        worker.finished_text.connect(lambda value: events.append(("done", value)))
        with patch("jarvis.reply_worker.stream_assistant", return_value=iter(["Olá", " mundo"])):
            worker.run()
        self.assertEqual(events, [("part", "Olá"), ("part", " mundo"),
                                  ("done", "__STREAM_DONE__Olá mundo")])

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
