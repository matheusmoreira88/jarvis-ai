"""HUD desktop independente: conversa textual, setup local e histórico."""
from __future__ import annotations

import sys
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (QApplication, QDialog, QFormLayout, QLineEdit, QLabel,
                               QMainWindow, QPushButton, QTextEdit, QVBoxLayout, QWidget)

from . import memory
from .providers import ask_gemini
from .settings import get_secret, save_secret


class ReplyWorker(QThread):
    finished_text = Signal(str)
    failed = Signal(str)

    def __init__(self, prompt: str):
        super().__init__()
        self.prompt = prompt

    def run(self):
        try:
            self.finished_text.emit(ask_gemini(self.prompt, memory.recent()))
        except Exception as exc:
            self.failed.emit(str(exc))


class SetupDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Configurar JARVIS")
        form = QFormLayout(self)
        self.gemini = QLineEdit(); self.gemini.setEchoMode(QLineEdit.EchoMode.Password)
        self.groq = QLineEdit(); self.groq.setEchoMode(QLineEdit.EchoMode.Password)
        self.email = QLineEdit(); self.phone = QLineEdit()
        form.addRow("Chave Gemini", self.gemini)
        form.addRow("Chave Groq (opcional)", self.groq)
        form.addRow("E-mail (opcional, local)", self.email)
        form.addRow("Telefone (opcional, local)", self.phone)
        save = QPushButton("Salvar neste computador")
        save.clicked.connect(self._save)
        form.addRow(save)

    def _save(self):
        try:
            save_secret("gemini", self.gemini.text())
            save_secret("groq", self.groq.text())
            save_secret("user_email", self.email.text())
            save_secret("user_phone", self.phone.text())
            self.accept()
        except Exception as exc:
            QLabel(f"Não foi possível acessar o cofre do sistema: {exc}", self).show()


class JarvisWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("JARVIS · Assistente desktop")
        self.resize(1100, 760)
        self.setStyleSheet("QWidget{background:#0b1020;color:#e7ebf5;font-family:'Segoe UI';font-size:14px} QTextEdit,QLineEdit{background:#141d30;border:1px solid #34415e;border-radius:8px;padding:10px} QPushButton{background:#627cf0;border:0;border-radius:8px;padding:10px 18px;font-weight:600} QPushButton:hover{background:#7890ff}")
        central = QWidget(); self.setCentralWidget(central); layout = QVBoxLayout(central)
        head = QLabel("JARVIS  /  ASSISTENTE PESSOAL")
        head.setStyleSheet("font-size:22px;font-weight:700;color:#9fb2ff;padding:8px")
        layout.addWidget(head)
        self.chat = QTextEdit(); self.chat.setReadOnly(True); layout.addWidget(self.chat, 1)
        row = QVBoxLayout(); self.input = QLineEdit(); self.input.setPlaceholderText("Escreva um comando…")
        self.input.returnPressed.connect(self.send); row.addWidget(self.input)
        send = QPushButton("Enviar"); send.clicked.connect(self.send); row.addWidget(send)
        layout.addLayout(row)
        settings = QPushButton("Configurações"); settings.clicked.connect(self.setup); layout.addWidget(settings)
        for role, body in memory.recent(30): self._append(role, body)

    def _append(self, role: str, body: str):
        label = "Você" if role == "user" else "JARVIS"
        self.chat.append(f"<b>{label}</b><br>{body.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')}<br>")

    def send(self):
        prompt = self.input.text().strip()
        if not prompt: return
        self.input.clear(); self._append("user", prompt); memory.add("user", prompt)
        self.input.setEnabled(False)
        self.worker = ReplyWorker(prompt)
        self.worker.finished_text.connect(self.reply); self.worker.failed.connect(self.error)
        self.worker.start()

    def reply(self, text: str):
        memory.add("assistant", text); self._append("assistant", text); self.input.setEnabled(True); self.input.setFocus()

    def error(self, text: str):
        self.chat.append(f"<span style='color:#ff8998'>Falha: {text}</span>")
        self.input.setEnabled(True)

    def setup(self):
        dialog = SetupDialog()
        dialog.email.setText(get_secret("user_email") or "")
        dialog.phone.setText(get_secret("user_phone") or "")
        dialog.exec()


def main():
    app = QApplication(sys.argv)
    if not get_secret("gemini"):
        dialog = SetupDialog()
        if dialog.exec() != QDialog.DialogCode.Accepted: return
    window = JarvisWindow(); window.show(); sys.exit(app.exec())
