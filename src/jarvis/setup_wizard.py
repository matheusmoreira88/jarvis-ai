"""First-run setup flow, independent from the main command-center window."""
from __future__ import annotations

from PySide6.QtWidgets import (QCheckBox, QLabel, QLineEdit, QMessageBox,
                               QVBoxLayout, QWizard, QWizardPage)

from .hud_theme import HUD_STYLE
from .settings import load_settings, save_secret, save_settings


class PrivacyWizardPage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.accept_box = QCheckBox(
            "Li o resumo e quero concluir a configuração neste computador")
        self.accept_box.toggled.connect(lambda _checked: self.completeChanged.emit())

    def isComplete(self):
        return self.accept_box.isChecked()


class SetupDialog(QWizard):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Primeira configuração do JARVIS")
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)
        self.setOption(QWizard.WizardOption.NoBackButtonOnStartPage)
        self.setMinimumSize(660, 470)
        self.setStyleSheet(HUD_STYLE)

        welcome = QWizardPage()
        welcome.setTitle("Bem-vindo ao JARVIS")
        welcome.setSubTitle("Seu command center pessoal, com voz, visão e memória local.")
        welcome_layout = QVBoxLayout(welcome)
        welcome_text = QLabel(
            "Esta configuração leva menos de um minuto. Você precisará de uma chave "
            "Gemini para conversa, transcrição de voz e análise da tela. O histórico e "
            "as lembranças permanecem no banco SQLite deste computador.")
        welcome_text.setWordWrap(True)
        welcome_text.setObjectName("setupBody")
        welcome_layout.addWidget(welcome_text)
        welcome_layout.addStretch(1)
        self.addPage(welcome)

        api_page = QWizardPage()
        api_page.setTitle("Conectar ao Gemini")
        api_page.setSubTitle("Uma única chave atende os recursos de inteligência do JARVIS.")
        api_layout = QVBoxLayout(api_page)
        api_help = QLabel(
            '<a href="https://aistudio.google.com/app/api-keys">Google AI Studio</a> '
            "permite criar a chave. Ela será salva no cofre de credenciais do sistema, "
            "nunca no repositório.")
        api_help.setOpenExternalLinks(True)
        api_help.setWordWrap(True)
        api_help.setObjectName("setupBody")
        api_layout.addWidget(api_help)
        self.gemini = QLineEdit()
        self.gemini.setEchoMode(QLineEdit.EchoMode.Password)
        self.gemini.setPlaceholderText("Cole sua chave Gemini")
        api_layout.addWidget(self.gemini)
        show_key = QCheckBox("Mostrar chave enquanto digito")
        show_key.toggled.connect(lambda visible: self.gemini.setEchoMode(
            QLineEdit.EchoMode.Normal if visible else QLineEdit.EchoMode.Password))
        api_layout.addWidget(show_key)
        api_layout.addStretch(1)
        self.addPage(api_page)

        privacy = PrivacyWizardPage()
        privacy.setTitle("Privacidade e controle")
        privacy.setSubTitle("Confira o que será enviado antes de concluir.")
        privacy_layout = QVBoxLayout(privacy)
        privacy_text = QLabel(
            "• Comandos de voz passam primeiro pelo detector local de ‘Jarvis’.\n"
            "• O áudio reconhecido é enviado ao Gemini para transcrição.\n"
            "• A visão envia imagens somente enquanto estiver ativada.\n"
            "• Conversas, lembranças e lembretes ficam no SQLite local.\n"
            "• O botão INTERROMPER desliga microfone, visão e controle imediatamente.\n\n"
            '<a href="https://github.com/matheusmoreira88/jarvis-ai/blob/main/PRIVACY.txt">'
            "Leia as informações completas de privacidade</a>.")
        privacy_text.setOpenExternalLinks(True)
        privacy_text.setWordWrap(True)
        privacy_text.setObjectName("setupBody")
        privacy_layout.addWidget(privacy_text)
        self.privacy_accept = privacy.accept_box
        privacy_layout.addWidget(self.privacy_accept)
        privacy_layout.addStretch(1)
        self.addPage(privacy)

        self.setButtonText(QWizard.WizardButton.NextButton, "Continuar")
        self.setButtonText(QWizard.WizardButton.BackButton, "Voltar")
        self.setButtonText(QWizard.WizardButton.FinishButton, "Concluir configuração")
        self.setButtonText(QWizard.WizardButton.CancelButton, "Cancelar")

    def accept(self):
        if not self.gemini.text().strip():
            QMessageBox.warning(self, "Chave necessária", "Cole uma chave Gemini para continuar.")
            self.setCurrentId(self.pageIds()[1])
            return
        try:
            save_secret("gemini", self.gemini.text())
            settings = load_settings()
            settings.pop("provider", None)
            save_settings({**settings, "setup_completed": True})
            super().accept()
        except Exception as exc:
            QMessageBox.warning(
                self, "Configurações não salvas",
                f"Não foi possível acessar o cofre de credenciais do sistema: {exc}")
