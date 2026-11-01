"""Windows application catalog and explicit executable selection dialogs."""
from __future__ import annotations

from PySide6.QtWidgets import QDialog, QFileDialog, QMessageBox

from .integration_ui import AppCatalogWorker, InstalledAppsDialog


class AppCatalogControllerMixin:
    """Keep installed-app discovery out of the main window implementation."""

    def select_and_open_executable(self):
        """Abre o .exe que a pessoa escolheu explicitamente no seletor do Windows."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Escolher aplicativo", "", "Aplicativos Windows (*.exe)")
        if not path:
            return
        try:
            from .computer import open_user_selected_executable
            self._record_private_control_action(
                f"abrir exe: {path}", open_user_selected_executable(path))
        except Exception as exc:
            self.error(str(exc))

    def open_installed_apps(self):
        """Abre a lista do sistema em segundo plano para não congelar o HUD."""
        if self.installed_apps_cache is not None:
            self._show_installed_apps(self.installed_apps_cache)
            return
        if getattr(self, "app_catalog_worker", None) and self.app_catalog_worker.isRunning():
            self.status.setText("Carregando os aplicativos instalados…")
            return
        self.status.setText("Carregando os aplicativos instalados…")
        self.app_catalog_worker = AppCatalogWorker()
        self.app_catalog_worker.loaded.connect(self._show_installed_apps)
        self.app_catalog_worker.failed.connect(self.error)
        self.app_catalog_worker.finished.connect(lambda: self.status.setText("Pronto"))
        self._track_worker(self.app_catalog_worker)
        self.app_catalog_worker.start()

    def _show_installed_apps(self, apps: list[dict[str, str]]):
        self.installed_apps_cache = apps
        if not apps:
            QMessageBox.information(self, "Aplicativos instalados", "Não encontrei aplicativos inicializáveis.")
            return
        dialog = InstalledAppsDialog(apps, self)
        if dialog.exec() != QDialog.DialogCode.Accepted or not dialog.selected_app:
            return
        selected = dialog.selected_app
        try:
            from .computer import launch_installed_app
            result = launch_installed_app(selected)
            self._record_control_action(f"abrir aplicativo: {selected['name']}", result)
        except Exception as exc:
            self.error(f"Não foi possível abrir o aplicativo: {exc}")

    def _launch_installed_by_name(self, requested: str, prompt: str):
        """Busca no catálogo em segundo plano; usa o cache nas próximas chamadas."""
        requested = requested.strip()
        if not requested:
            QMessageBox.information(self, "Abrir aplicativo", "Informe o nome do aplicativo.")
            return
        if self.installed_apps_cache is None:
            self.pending_app_launch = (requested, prompt)
            if getattr(self, "app_catalog_worker", None) and self.app_catalog_worker.isRunning():
                return
            self.status.setText("Procurando o aplicativo instalado…")
            self.app_catalog_worker = AppCatalogWorker()
            self.app_catalog_worker.loaded.connect(self._complete_pending_app_launch)
            self.app_catalog_worker.failed.connect(self.error)
            self.app_catalog_worker.finished.connect(lambda: self.status.setText("Pronto"))
            self._track_worker(self.app_catalog_worker)
            self.app_catalog_worker.start()
            return
        self._complete_pending_app_launch(self.installed_apps_cache, (requested, prompt))

    def _complete_pending_app_launch(self, apps: list[dict[str, str]], request=None):
        """Resolve uma busca pendente pelo nome depois de carregar o catálogo."""
        self.installed_apps_cache = apps
        if request is None:
            request = getattr(self, "pending_app_launch", None)
        self.pending_app_launch = None
        if not request:
            return
        requested, prompt = request
        try:
            from .computer import launch_installed_app
            exact = [app for app in apps if app["name"].casefold() == requested.casefold()]
            matches = exact or [app for app in apps if requested.casefold() in app["name"].casefold()]
            if not matches:
                self.error(f"Não encontrei um aplicativo instalado chamado ‘{requested}’.")
                return
            selected = matches[0] if len(matches) == 1 else self._choose_installed_app(matches, requested)
            if selected:
                self._record_control_action(prompt, launch_installed_app(selected))
        except Exception as exc:
            self.error(f"Não foi possível abrir o aplicativo: {exc}")

    def _choose_installed_app(self, apps: list[dict[str, str]], query: str):
        """Quando um nome tem mais de uma correspondência, deixa a pessoa escolher."""
        dialog = InstalledAppsDialog(apps, self)
        dialog.search.setText(query)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        return dialog.selected_app

