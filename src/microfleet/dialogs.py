from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
)

from .models import Microservice, Server


class ServerDialog(QDialog):
    def __init__(self, server: Server | None = None, parent=None) -> None:
        super().__init__(parent)
        self.server = server or Server()
        self.setWindowTitle("Параметры сервера")
        self.setMinimumWidth(480)
        self.setModal(True)

        self.name = QLineEdit(self.server.name)
        self.name.setPlaceholderText("Production 01")
        self.group = QLineEdit(self.server.group_name)
        self.group.setPlaceholderText("production / mirror-a")
        self.host = QLineEdit(self.server.host)
        self.host.setPlaceholderText("10.20.0.15 или hostname")
        self.port = QSpinBox()
        self.port.setRange(1, 65535)
        self.port.setValue(self.server.port)
        self.ssh_user = QLineEdit(self.server.ssh_user)
        self.ssh_user.setPlaceholderText("deploy")
        self.run_as_user = QLineEdit(self.server.run_as_user)
        self.run_as_user.setPlaceholderText("appuser (необязательно)")
        self.management_script = QLineEdit(self.server.management_script_path)
        self.management_script.setPlaceholderText("/opt/apps/manage-services.sh")
        self.auth_type = QComboBox()
        self.auth_type.addItem("SSH-ключ / ssh-agent", "key")
        self.auth_type.addItem("Пароль", "password")
        self.auth_type.setCurrentIndex(0 if self.server.auth_type == "key" else 1)
        self.key_path = QLineEdit(self.server.key_path)
        self.key_path.setPlaceholderText("Пусто — использовать ssh-agent и стандартные ключи")
        browse = QPushButton("Обзор…")
        browse.clicked.connect(self._browse_key)
        key_row = QHBoxLayout()
        key_row.setContentsMargins(0, 0, 0, 0)
        key_row.addWidget(self.key_path, 1)
        key_row.addWidget(browse)
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password.setPlaceholderText("Не сохраняется; только для текущего запуска")
        self.notes = QTextEdit(self.server.notes)
        self.notes.setMaximumHeight(70)

        form = QFormLayout()
        form.setSpacing(11)
        form.addRow("Название *", self.name)
        form.addRow("Группа / зеркало", self.group)
        form.addRow("Адрес *", self.host)
        form.addRow("SSH-порт", self.port)
        form.addRow("SSH-пользователь *", self.ssh_user)
        form.addRow("Выполнять от", self.run_as_user)
        form.addRow("Общий скрипт", self.management_script)
        form.addRow("Авторизация", self.auth_type)
        form.addRow("Приватный ключ", key_row)
        form.addRow("SSH-пароль", self.password)
        form.addRow("Заметки", self.notes)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Сохранить")
        buttons.button(QDialogButtonBox.StandardButton.Save).setObjectName("primary")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Отмена")
        buttons.accepted.connect(self._validate)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 22, 22, 18)
        layout.addLayout(form)
        layout.addSpacing(8)
        layout.addWidget(buttons)
        self.auth_type.currentIndexChanged.connect(self._sync_auth_fields)
        self._sync_auth_fields()

    def _sync_auth_fields(self) -> None:
        is_key = self.auth_type.currentData() == "key"
        self.key_path.setEnabled(is_key)
        self.password.setEnabled(not is_key)

    def _browse_key(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Выберите приватный SSH-ключ")
        if path:
            self.key_path.setText(path)

    def _validate(self) -> None:
        if not all((self.name.text().strip(), self.host.text().strip(), self.ssh_user.text().strip())):
            QMessageBox.warning(self, "Не все поля заполнены", "Укажите название, адрес и SSH-пользователя.")
            return
        self.accept()

    def result_data(self) -> tuple[Server, str]:
        self.server.name = self.name.text().strip()
        self.server.group_name = self.group.text().strip()
        self.server.host = self.host.text().strip()
        self.server.port = self.port.value()
        self.server.ssh_user = self.ssh_user.text().strip()
        self.server.run_as_user = self.run_as_user.text().strip()
        self.server.management_script_path = self.management_script.text().strip()
        self.server.auth_type = str(self.auth_type.currentData())
        self.server.key_path = self.key_path.text().strip()
        self.server.notes = self.notes.toPlainText().strip()
        return self.server, self.password.text()


class ServiceDialog(QDialog):
    def __init__(self, server_id: int, service: Microservice | None = None, parent=None) -> None:
        super().__init__(parent)
        self.service = service or Microservice(server_id=server_id)
        self.setWindowTitle("Параметры микросервиса")
        self.setMinimumWidth(450)
        self.name = QLineEdit(self.service.name)
        self.name.setPlaceholderText("billing-api")
        self.description = QLineEdit(self.service.description)
        self.description.setPlaceholderText("Краткое назначение сервиса")
        self.order = QSpinBox()
        self.order.setRange(0, 9999)
        self.order.setValue(self.service.sort_order)

        form = QFormLayout()
        form.setSpacing(11)
        form.addRow("Имя для скрипта *", self.name)
        form.addRow("Описание", self.description)
        form.addRow("Порядок", self.order)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Сохранить")
        buttons.button(QDialogButtonBox.StandardButton.Save).setObjectName("primary")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Отмена")
        buttons.accepted.connect(self._validate)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 22, 22, 18)
        layout.addLayout(form)
        layout.addSpacing(8)
        layout.addWidget(buttons)

    def _validate(self) -> None:
        if not self.name.text().strip():
            QMessageBox.warning(self, "Не все поля заполнены", "Укажите имя микросервиса.")
            return
        if self.name.text().strip() == "all":
            QMessageBox.warning(self, "Зарезервированное имя", "Имя «all» используется для управления всеми сервисами.")
            return
        self.accept()

    def result_data(self) -> Microservice:
        self.service.name = self.name.text().strip()
        self.service.description = self.description.text().strip()
        self.service.sort_order = self.order.value()
        return self.service
