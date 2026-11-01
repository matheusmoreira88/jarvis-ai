"""Small dialogs and background jobs used by optional desktop integrations.

Keeping these pieces outside the main window makes it easier to maintain Gmail,
WhatsApp, media downloads, and the Windows application catalog independently.
"""
from __future__ import annotations

from PySide6.QtCore import QStandardPaths, Qt, QThread, QUrl, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEnginePermission, QWebEngineProfile
from PySide6.QtWebEngineWidgets import QWebEngineView


class DownloadWorker(QThread):
    """Download audio without freezing animations or voice feedback."""

    completed = Signal(str)
    failed = Signal(str)

    def __init__(self, url: str, folder: str):
        super().__init__()
        self.url = url
        self.folder = folder

    def run(self):
        try:
            from .media import download_audio

            self.completed.emit(download_audio(self.url, self.folder))
        except Exception as exc:
            self.failed.emit(str(exc))


class GmailWorker(QThread):
    """Send a previously reviewed email away from the interface thread."""

    completed = Signal(str)
    failed = Signal(str)

    def __init__(self, to: str, subject: str, body: str):
        super().__init__()
        self.to = to
        self.subject = subject
        self.body = body

    def run(self):
        try:
            from .gmail import send_email

            send_email(self.to, self.subject, self.body)
            self.completed.emit("E-mail enviado.")
        except Exception as exc:
            self.failed.emit(str(exc))


class WhatsAppWebDialog(QDialog):
    """Show the official WhatsApp Web page inside a dedicated HUD window."""

    def __init__(self, url: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("WhatsApp · JARVIS HUD")
        self.resize(1080, 760)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Revise a conversa e pressione Enviar no WhatsApp Web."))
        self.web = QWebEngineView(self)
        profile = QWebEngineProfile("jarvis-whatsapp", self)
        storage = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
        profile.setPersistentStoragePath(storage + "/whatsapp-profile")
        profile.setPersistentCookiesPolicy(
            QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies
        )
        page = QWebEnginePage(profile, self.web)
        page.permissionRequested.connect(self._handle_web_permission)
        self.web.setPage(page)
        self.web.setUrl(QUrl(url))
        layout.addWidget(self.web, 1)

    def _handle_web_permission(self, permission):
        """Grant media only to the official WhatsApp host and deny everything else."""
        allowed_hosts = {"web.whatsapp.com", "www.whatsapp.com"}
        permission_types = QWebEnginePermission.PermissionType
        media_types = {
            permission_types.MediaAudioCapture,
            permission_types.MediaVideoCapture,
            permission_types.MediaAudioVideoCapture,
        }
        if (
            not permission.isValid()
            or permission.origin().host().lower() not in allowed_hosts
            or permission.permissionType() not in media_types
        ):
            permission.deny()
            return
        permission.grant()


class ContactsDialog(QDialog):
    """Edit the local allowlist used when preparing WhatsApp messages."""

    def __init__(self, parent=None):
        super().__init__(parent)
        from .whatsapp import contacts

        self.setWindowTitle("Contatos permitidos · WhatsApp")
        self.items = contacts()
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            "Somente estes contatos podem receber mensagens preparadas pelo JARVIS."
        ))
        self.listing = QComboBox()
        layout.addWidget(self.listing)
        row = QHBoxLayout()
        self.name = QLineEdit()
        self.name.setPlaceholderText("Nome")
        self.phone = QLineEdit()
        self.phone.setPlaceholderText("Telefone internacional com DDI")
        add = QPushButton("Adicionar")
        remove = QPushButton("Remover selecionado")
        add.clicked.connect(self.add_contact)
        remove.clicked.connect(self.remove_contact)
        row.addWidget(self.name)
        row.addWidget(self.phone)
        row.addWidget(add)
        row.addWidget(remove)
        layout.addLayout(row)
        self.refresh()

    def refresh(self):
        self.listing.clear()
        for contact in self.items:
            self.listing.addItem(f"{contact['name']} · +{contact['phone']}")
        if not self.items:
            self.listing.addItem("Lista vazia")

    def add_contact(self):
        name = self.name.text().strip()
        phone = "".join(character for character in self.phone.text() if character.isdigit())
        if not name or len(phone) < 8:
            QMessageBox.warning(self, "Contato", "Informe nome e telefone com DDI.")
            return
        self.items.append({"name": name, "phone": phone})
        from .whatsapp import save_contacts

        save_contacts(self.items)
        self.name.clear()
        self.phone.clear()
        self.refresh()

    def remove_contact(self):
        if not self.items:
            return
        index = self.listing.currentIndex()
        if index < 0 or index >= len(self.items):
            return
        self.items.pop(index)
        from .whatsapp import save_contacts

        save_contacts(self.items)
        self.refresh()


class AppCatalogWorker(QThread):
    """Enumerate installed Windows applications without blocking the interface."""

    loaded = Signal(list)
    failed = Signal(str)

    def run(self):
        try:
            from .computer import list_installed_apps

            self.loaded.emit(list_installed_apps())
        except Exception as exc:
            self.failed.emit(f"Não foi possível listar os aplicativos: {exc}")


class InstalledAppsDialog(QDialog):
    """Search installed apps without starting anything until the user chooses one."""

    def __init__(self, apps: list[dict[str, str]], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Aplicativos instalados")
        self.resize(620, 680)
        self.apps = apps
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            f"{len(apps)} aplicativos encontrados no menu Iniciar e nos registros do Windows. "
            "Escolha um item e selecione Abrir para iniciar."
        ))
        self.search = QLineEdit()
        self.search.setPlaceholderText("Buscar aplicativo pelo nome…")
        self.search.textChanged.connect(self._filter)
        layout.addWidget(self.search)
        self.listing = QListWidget()
        self.listing.itemDoubleClicked.connect(lambda *_: self.accept())
        layout.addWidget(self.listing, 1)
        self._items: list[QListWidgetItem] = []
        for app in apps:
            item = QListWidgetItem(app["name"])
            item.setData(Qt.ItemDataRole.UserRole, app)
            self.listing.addItem(item)
            self._items.append(item)
        if self._items:
            self.listing.setCurrentItem(self._items[0])
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Open,
            parent=self,
        )
        buttons.button(QDialogButtonBox.StandardButton.Open).setText("Abrir aplicativo")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _filter(self, text: str):
        query = text.casefold().strip()
        first_visible = None
        for item in self._items:
            visible = query in item.text().casefold()
            item.setHidden(not visible)
            if visible and first_visible is None:
                first_visible = item
        if self.listing.currentItem() is None or self.listing.currentItem().isHidden():
            self.listing.setCurrentItem(first_visible)

    @property
    def selected_app(self) -> dict[str, str] | None:
        item = self.listing.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else None


class WhatsAppComposeDialog(QDialog):
    """Collect a recipient and message before the existing review step."""

    def __init__(self, parent=None):
        super().__init__(parent)
        from .whatsapp import contacts

        self.items = contacts()
        self.setWindowTitle("Preparar mensagem WhatsApp")
        layout = QFormLayout(self)
        self.recipient = QComboBox()
        self.message = QTextEdit()
        for contact in self.items:
            self.recipient.addItem(contact["name"], contact["phone"])
        layout.addRow("Contato permitido", self.recipient)
        layout.addRow("Mensagem", self.message)
        button = QPushButton("Revisar mensagem")
        button.clicked.connect(self.accept)
        layout.addRow(button)

    @property
    def phone(self) -> str:
        return str(self.recipient.currentData() or "")

    @property
    def message_text(self) -> str:
        return self.message.toPlainText().strip()
