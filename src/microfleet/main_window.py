from __future__ import annotations

import os
from dataclasses import replace
from datetime import datetime
from functools import partial
from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import QStandardPaths, Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .database import Database
from .dialogs import ServerDialog, ServiceDialog
from .models import Microservice, Server
from .ssh import ConnectionSecret, SSHSession, service_command, service_shell_command
from .status import parse_all_statuses, parse_status
from .terminal import AnsiTerminalRenderer


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("MicroFleet — управление микросервисами")
        self.resize(1440, 830)
        self.setMinimumSize(1080, 650)

        custom_db = os.environ.get("MICROFLEET_DB_PATH")
        app_dir = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation))
        self.db = Database(Path(custom_db) if custom_db else app_dir / "microfleet.db")
        self.servers: list[Server] = []
        self.services: list[Microservice] = []
        self.active_server: Server | None = None
        self.console_buffers: dict[int, list[str]] = {}
        self.terminal_renderer = AnsiTerminalRenderer()
        self.server_states: dict[int, str] = {}
        self.service_statuses: dict[int, dict[str, str]] = {}
        self.pending_commands: dict[str, tuple[int, str, str]] = {}
        self.pending_command_output: dict[str, list[str]] = {}
        self.passwords: dict[int, str] = {}
        self.sessions: dict[int, SSHSession] = {}

        self._build_ui()
        self._load_servers()

    def _build_ui(self) -> None:
        root = QWidget(objectName="root")
        self.setCentralWidget(root)
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addWidget(self._build_sidebar())
        root_layout.addWidget(self._build_workspace(), 1)

    def _build_sidebar(self) -> QWidget:
        sidebar = QWidget(objectName="sidebar")
        sidebar.setFixedWidth(255)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(18, 21, 16, 16)
        layout.setSpacing(10)

        brand_row = QHBoxLayout()
        logo = QLabel("◆")
        logo.setStyleSheet("color:#7188ff;font-size:18px")
        brand = QLabel("MicroFleet", objectName="brand")
        brand_row.addWidget(logo)
        brand_row.addWidget(brand)
        brand_row.addStretch()
        layout.addLayout(brand_row)
        subtitle = QLabel("LINUX OPERATIONS", objectName="eyebrow")
        layout.addWidget(subtitle)
        layout.addSpacing(13)

        header = QHBoxLayout()
        header.addWidget(QLabel("СЕРВЕРЫ", objectName="sectionTitle"))
        header.addStretch()
        add = QPushButton("＋", objectName="ghost")
        add.setToolTip("Добавить сервер")
        add.clicked.connect(self._add_server)
        header.addWidget(add)
        layout.addLayout(header)

        self.server_list = QListWidget()
        self.server_list.setSpacing(1)
        self.server_list.currentItemChanged.connect(self._server_selected)
        layout.addWidget(self.server_list, 1)

        self.server_count = QLabel("0 серверов", objectName="muted")
        layout.addWidget(self.server_count)
        return sidebar

    def _build_workspace(self) -> QWidget:
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(28, 24, 26, 22)
        content_layout.setSpacing(16)

        title_row = QHBoxLayout()
        title_box = QVBoxLayout()
        self.page_title = QLabel("Выберите сервер", objectName="pageTitle")
        self.page_meta = QLabel("Добавьте первый сервер, чтобы начать работу", objectName="muted")
        title_box.addWidget(self.page_title)
        title_box.addWidget(self.page_meta)
        title_row.addLayout(title_box)
        title_row.addStretch()
        self.edit_server_btn = QPushButton("Параметры")
        self.edit_server_btn.clicked.connect(self._edit_server)
        self.delete_server_btn = QPushButton("Удалить", objectName="danger")
        self.delete_server_btn.clicked.connect(self._delete_server)
        title_row.addWidget(self.edit_server_btn)
        title_row.addWidget(self.delete_server_btn)
        content_layout.addLayout(title_row)

        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("МИКРОСЕРВИСЫ", objectName="sectionTitle"))
        toolbar.addStretch()
        self.add_service_btn = QPushButton("＋  Добавить микросервис", objectName="primary")
        self.add_service_btn.clicked.connect(self._add_service)
        toolbar.addWidget(self.add_service_btn)
        content_layout.addLayout(toolbar)

        self.management_script_label = QLabel("Общий скрипт не настроен", objectName="muted")
        self.management_script_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        content_layout.addWidget(self.management_script_label)
        all_actions_row = QHBoxLayout()
        all_actions_row.addWidget(QLabel("ВСЕ СЕРВИСЫ", objectName="sectionTitle"))
        all_actions_row.addStretch()
        self.all_action_buttons: list[QPushButton] = []
        for label, action in (
            ("Все: старт", "start"),
            ("Все: стоп", "stop"),
            ("Все: рестарт", "restart"),
            ("Все: статус", "status"),
        ):
            button = QPushButton(label)
            button.setToolTip(f"Выполнить {action} all на текущем сервере")
            button.clicked.connect(partial(self._run_all_action, action))
            all_actions_row.addWidget(button)
            self.all_action_buttons.append(button)
        content_layout.addLayout(all_actions_row)

        self.service_table = QTableWidget(0, 5)
        self.service_table.setHorizontalHeaderLabels(
            ["СЕРВИС", "ОПИСАНИЕ", "СТАТУС", "УПРАВЛЕНИЕ", ""]
        )
        self.service_table.setAlternatingRowColors(True)
        self.service_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.service_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.service_table.verticalHeader().setVisible(False)
        self.service_table.verticalHeader().setDefaultSectionSize(62)
        header = self.service_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        content_layout.addWidget(self.service_table, 1)

        empty_hint = QLabel(
            "Общий скрипт вызывается с аргументами: действие и имя микросервиса "
            "(или all для всех). Вывод отображается в SSH-терминале.",
            objectName="muted",
        )
        empty_hint.setWordWrap(True)
        content_layout.addWidget(empty_hint)

        splitter.addWidget(content)
        splitter.addWidget(self._build_console())
        splitter.setSizes([780, 440])
        return splitter

    def _build_console(self) -> QWidget:
        panel = QWidget(objectName="consolePanel")
        panel.setMinimumWidth(350)
        panel.setMaximumWidth(620)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 23, 18, 18)
        layout.setSpacing(11)

        top = QHBoxLayout()
        labels = QVBoxLayout()
        labels.addWidget(QLabel("SSH OUTPUT", objectName="sectionTitle"))
        self.console_host = QLabel("Нет активного сервера", objectName="muted")
        labels.addWidget(self.console_host)
        top.addLayout(labels)
        top.addStretch()
        self.connect_button = QPushButton("Подключить")
        self.connect_button.setToolTip("Открыть или закрыть интерактивную SSH-сессию")
        self.connect_button.clicked.connect(self._toggle_connection)
        top.addWidget(self.connect_button)
        self.state_label = QLabel("● OFFLINE", objectName="statusOffline")
        top.addWidget(self.state_label)
        layout.addLayout(top)

        self.terminal = QPlainTextEdit(objectName="terminal")
        self.terminal.setReadOnly(True)
        self.terminal.setPlaceholderText("Здесь появится вывод команд активного сервера…")
        self.terminal.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        font = QFont("Cascadia Mono", 10)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.terminal.setFont(font)
        layout.addWidget(self.terminal, 1)

        command_row = QHBoxLayout()
        self.command_input = QLineEdit()
        self.command_input.setPlaceholderText("Команда в shell активного пользователя")
        self.command_input.returnPressed.connect(self._run_custom_command)
        run_button = QPushButton("Выполнить", objectName="primary")
        run_button.clicked.connect(self._run_custom_command)
        clear_button = QPushButton("Очистить", objectName="ghost")
        clear_button.clicked.connect(self._clear_console)
        interrupt_button = QPushButton("Ctrl+C", objectName="ghost")
        interrupt_button.setToolTip("Прервать текущий процесс в SSH-терминале")
        interrupt_button.clicked.connect(self._interrupt_command)
        command_row.addWidget(self.command_input, 1)
        command_row.addWidget(run_button)
        layout.addLayout(command_row)
        terminal_tools = QHBoxLayout()
        terminal_tools.addStretch()
        terminal_tools.addWidget(interrupt_button)
        terminal_tools.addWidget(clear_button)
        layout.addLayout(terminal_tools)
        return panel

    def _load_servers(self, select_id: int | None = None) -> None:
        self.servers = self.db.list_servers()
        previous_id = select_id or (self.active_server.id if self.active_server else None)
        self.server_list.blockSignals(True)
        self.server_list.clear()
        for server in self.servers:
            item = QListWidgetItem()
            group = f"  ·  {server.group_name}" if server.group_name else ""
            item.setText(f"●  {server.name}\n     {server.host}{group}")
            item.setData(Qt.ItemDataRole.UserRole, server.id)
            item.setToolTip(f"{server.ssh_user}@{server.host}:{server.port}")
            self.server_list.addItem(item)
            if server.id == previous_id:
                self.server_list.setCurrentItem(item)
        self.server_list.blockSignals(False)
        self.server_count.setText(self._plural_servers(len(self.servers)))
        if self.server_list.currentItem() is not None:
            self._server_selected(self.server_list.currentItem())
        elif self.server_list.count():
            self.server_list.setCurrentRow(0)
        elif not self.servers:
            self._activate_server(None)

    @staticmethod
    def _plural_servers(count: int) -> str:
        suffix = "сервер" if count % 10 == 1 and count % 100 != 11 else "серверов"
        if count % 10 in (2, 3, 4) and count % 100 not in (12, 13, 14):
            suffix = "сервера"
        return f"{count} {suffix}"

    def _server_selected(self, current: QListWidgetItem | None, _previous=None) -> None:
        server_id = current.data(Qt.ItemDataRole.UserRole) if current else None
        server = next((item for item in self.servers if item.id == server_id), None)
        self._activate_server(server)

    def _activate_server(self, server: Server | None) -> None:
        self.active_server = server
        enabled = server is not None
        for widget in (
            self.edit_server_btn, self.delete_server_btn, self.add_service_btn,
            self.command_input, self.connect_button,
        ):
            widget.setEnabled(enabled)
        for button in self.all_action_buttons:
            button.setEnabled(enabled and bool(server.management_script_path))
        if server is None:
            self.page_title.setText("Выберите сервер")
            self.page_meta.setText("Добавьте первый сервер, чтобы начать работу")
            self.console_host.setText("Нет активного сервера")
            self.management_script_label.setText("Общий скрипт не настроен")
            self.terminal.clear()
            self._set_state_label("offline")
            self.services = []
            self._render_services()
            return
        self.page_title.setText(server.name)
        run_as = server.run_as_user or server.ssh_user
        mirror = f"  •  группа {server.group_name}" if server.group_name else ""
        self.page_meta.setText(f"{server.ssh_user}@{server.host}:{server.port}  •  команды от {run_as}{mirror}")
        self.management_script_label.setText(
            f"Скрипт: {server.management_script_path}"
            if server.management_script_path else "Укажите общий скрипт в параметрах сервера"
        )
        self.management_script_label.setToolTip(server.management_script_path)
        self.console_host.setText(f"{server.ssh_user}@{server.host}")
        self._show_console(server.id or 0)
        self._set_state_label(self.server_states.get(server.id or 0, "offline"))
        self.services = self.db.list_services(server.id or 0)
        self._render_services()
        if server.auth_type != "password" or self.passwords.get(server.id or 0):
            self._connect_server(server, quiet=True)

    def _render_services(self) -> None:
        self.service_table.setRowCount(0)
        for service in self.services:
            row = self.service_table.rowCount()
            self.service_table.insertRow(row)
            name = QTableWidgetItem(service.name)
            if service.description:
                name.setToolTip(service.description)
            description = QTableWidgetItem(service.description)
            description.setForeground(QColor("#8798ad"))
            state = self.service_statuses.get(service.server_id, {}).get(service.name, "unknown")
            status = QTableWidgetItem()
            self._style_status_item(status, state)
            status.setData(Qt.ItemDataRole.UserRole, service.id)
            self.service_table.setItem(row, 0, name)
            self.service_table.setItem(row, 1, description)
            self.service_table.setItem(row, 2, status)

            actions = QWidget()
            actions_layout = QHBoxLayout(actions)
            actions_layout.setContentsMargins(3, 3, 3, 3)
            actions_layout.setSpacing(5)
            for label, action in (("▶", "start"), ("■", "stop"), ("↻", "restart"), ("?", "status")):
                button = QPushButton(label)
                button.setFixedSize(31, 29)
                button.setToolTip({"start": "Запустить", "stop": "Остановить", "restart": "Перезапустить", "status": "Проверить статус"}[action])
                button.clicked.connect(partial(self._run_service_action, service, action, row))
                actions_layout.addWidget(button)
            self.service_table.setCellWidget(row, 3, actions)

            more = QWidget()
            more_layout = QHBoxLayout(more)
            more_layout.setContentsMargins(2, 2, 2, 2)
            edit = QPushButton("✎", objectName="ghost")
            edit.setToolTip("Изменить")
            edit.clicked.connect(partial(self._edit_service, service))
            delete = QPushButton("×", objectName="ghost")
            delete.setToolTip("Удалить")
            delete.clicked.connect(partial(self._delete_service, service))
            more_layout.addWidget(edit)
            more_layout.addWidget(delete)
            self.service_table.setCellWidget(row, 4, more)

    def _add_server(self) -> None:
        dialog = ServerDialog(parent=self)
        if dialog.exec():
            server, password = dialog.result_data()
            try:
                self.db.save_server(server)
            except Exception as exc:
                self._show_db_error(exc)
                return
            if password and server.id:
                self.passwords[server.id] = password
            self._load_servers(server.id)

    def _edit_server(self) -> None:
        if not self.active_server:
            return
        original = self.active_server
        dialog = ServerDialog(replace(original), self)
        if dialog.exec():
            server, password = dialog.result_data()
            try:
                self.db.save_server(server)
            except Exception as exc:
                self._show_db_error(exc)
                return
            connection_fields = ("host", "port", "ssh_user", "run_as_user", "auth_type", "key_path")
            connection_changed = password or any(
                getattr(original, field) != getattr(server, field) for field in connection_fields
            )
            if connection_changed and server.id is not None:
                old_session = self.sessions.pop(server.id, None)
                if old_session is not None:
                    old_session.stop()
                    old_session.wait(9000)
                self.server_states[server.id] = "offline"
            if password and server.id:
                self.passwords[server.id] = password
            self._load_servers(server.id)

    def _delete_server(self) -> None:
        server = self.active_server
        if not server or server.id is None:
            return
        answer = QMessageBox.question(
            self,
            "Удалить сервер?",
            f"Сервер «{server.name}» и все его микросервисы будут удалены из приложения.",
        )
        if answer == QMessageBox.StandardButton.Yes:
            self._stop_session(server.id)
            self.db.delete_server(server.id)
            self.console_buffers.pop(server.id, None)
            self.service_statuses.pop(server.id, None)
            self.pending_command_output = {
                token: output for token, output in self.pending_command_output.items()
                if self.pending_commands.get(token, (None,))[0] != server.id
            }
            self.pending_commands = {
                token: command for token, command in self.pending_commands.items()
                if command[0] != server.id
            }
            self.passwords.pop(server.id, None)
            self.active_server = None
            self._load_servers()

    def _add_service(self) -> None:
        if not self.active_server or self.active_server.id is None:
            return
        dialog = ServiceDialog(self.active_server.id, parent=self)
        if dialog.exec():
            try:
                self.db.save_service(dialog.result_data())
                self._activate_server(self.active_server)
            except Exception as exc:
                self._show_db_error(exc)

    def _edit_service(self, service: Microservice) -> None:
        dialog = ServiceDialog(service.server_id, service, self)
        if dialog.exec():
            try:
                self.db.save_service(dialog.result_data())
                self._activate_server(self.active_server)
            except Exception as exc:
                self._show_db_error(exc)

    def _delete_service(self, service: Microservice) -> None:
        if service.id is None:
            return
        if QMessageBox.question(self, "Удалить микросервис?", f"Удалить «{service.name}» из списка?") == QMessageBox.StandardButton.Yes:
            self.db.delete_service(service.id)
            self._activate_server(self.active_server)

    def _run_service_action(self, service: Microservice, action: str, row: int) -> None:
        server = self.active_server
        if not server:
            return
        if service.name == "all":
            QMessageBox.information(
                self,
                "Зарезервированное имя",
                "Для аргумента «all» используйте кнопки «Все сервисы».",
            )
            return
        script_path = self._management_script_for(server)
        if script_path is None:
            return
        if self._send_managed_command(server, script_path, action, service.name):
            self._set_service_status(server.id or 0, service.name, "checking")

    def _run_all_action(self, action: str) -> None:
        server = self.active_server
        if server is None:
            return
        script_path = self._management_script_for(server)
        if script_path is None:
            return
        if action != "status":
            answer = QMessageBox.question(
                self,
                "Подтвердите действие для всех сервисов",
                f"Выполнить «{action} all» на сервере «{server.name}»?",
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        if self._send_managed_command(server, script_path, action, "all"):
            for service in self.services:
                self._set_service_status(server.id or 0, service.name, "checking")

    def _send_managed_command(
        self, server: Server, script_path: str, action: str, target: str,
        session: SSHSession | None = None,
    ) -> bool:
        session = session or self._session_for_command(server)
        if session is None:
            return False
        token = uuid4().hex
        command = service_command(server, script_path, action, target)
        self.pending_commands[token] = (server.id or 0, action, target)
        self.pending_command_output[token] = []
        if session.send_managed_command(command, token):
            self._append_console(
                server.id or 0,
                f"\n$ {service_shell_command(script_path, action, target)}\n",
            )
            return True
        self.pending_commands.pop(token, None)
        self.pending_command_output.pop(token, None)
        QMessageBox.warning(self, "SSH-сессия закрыта", "Подключитесь к серверу и повторите команду.")
        return False

    def _on_managed_output(self, server_id: int, token: str, text: str) -> None:
        if self.pending_commands.get(token, (None,))[0] != server_id:
            return
        self.pending_command_output[token].append(text)
        self._append_console(server_id, text)

    def _on_managed_finished(self, server_id: int, token: str, exit_code: int) -> None:
        pending = self.pending_commands.pop(token, None)
        output = "".join(self.pending_command_output.pop(token, []))
        if pending is None or pending[0] != server_id:
            return
        _, action, target = pending
        if action == "status":
            if target == "all":
                names = [service.name for service in self.db.list_services(server_id)]
                parsed = parse_all_statuses(output, names)
                for name in names:
                    state = parsed.get(name, "error" if exit_code else "unknown")
                    self._set_service_status(server_id, name, state)
            else:
                state = parse_status(output)
                if state is None:
                    state = "error" if exit_code else "unknown"
                self._set_service_status(server_id, target, state)
            return

        if exit_code:
            self._append_console(
                server_id,
                f"\n[{self._timestamp()}] {action} {target}: код выхода {exit_code}\n",
            )
        session = self.sessions.get(server_id)
        server = next((item for item in self.servers if item.id == server_id), None)
        if server and session and session.isRunning() and server.management_script_path:
            self._send_managed_command(
                server, server.management_script_path, "status", target, session=session
            )
        else:
            names = (
                [service.name for service in self.db.list_services(server_id)]
                if target == "all" else [target]
            )
            for name in names:
                self._set_service_status(server_id, name, "error" if exit_code else "unknown")

    def _set_service_status(self, server_id: int, service_name: str, state: str) -> None:
        self.service_statuses.setdefault(server_id, {})[service_name] = state
        if not self.active_server or self.active_server.id != server_id:
            return
        for row, service in enumerate(self.services):
            if service.name == service_name:
                item = self.service_table.item(row, 2)
                if item:
                    self._style_status_item(item, state)
                break

    @staticmethod
    def _style_status_item(item: QTableWidgetItem, state: str) -> None:
        styles = {
            "running": ("Работает", "#4adea2"),
            "stopped": ("Остановлен", "#ef7187"),
            "failed": ("Сбой", "#ef7187"),
            "checking": ("Проверяется…", "#f7c66b"),
            "error": ("Ошибка проверки", "#ef7187"),
            "unknown": ("Неизвестно", "#718097"),
        }
        label, color = styles.get(state, styles["unknown"])
        item.setText(label)
        item.setForeground(QColor(color))

    def _management_script_for(self, server: Server) -> str | None:
        script_path = server.management_script_path.strip()
        if script_path:
            return script_path
        QMessageBox.information(
            self,
            "Общий скрипт не настроен",
            "Откройте «Параметры» сервера и укажите путь к общему управляющему скрипту.",
        )
        return None

    def _run_custom_command(self) -> None:
        server = self.active_server
        raw = self.command_input.text().strip()
        if not server or not raw:
            return
        self.command_input.clear()
        session = self._session_for_command(server)
        if session is not None:
            session.send_command(raw)

    def _toggle_connection(self) -> None:
        server = self.active_server
        if not server or server.id is None:
            return
        session = self.sessions.get(server.id)
        if session and session.isRunning():
            self._stop_session(server.id)
        else:
            self._connect_server(server)

    def _connect_server(self, server: Server, quiet: bool = False) -> SSHSession | None:
        server_id = int(server.id or 0)
        current = self.sessions.get(server_id)
        if current and current.isRunning():
            return current
        password = self.passwords.get(server_id, "")
        if server.auth_type == "password" and not password:
            if not quiet:
                QMessageBox.information(
                    self,
                    "Требуется пароль",
                    "Откройте «Параметры» сервера и введите SSH-пароль. "
                    "Он останется только в памяти до закрытия приложения.",
                )
            return None
        session = SSHSession(server, ConnectionSecret(password), parent=self)
        session.output.connect(self._append_console)
        session.managed_output.connect(self._on_managed_output)
        session.managed_finished.connect(self._on_managed_finished)
        session.state.connect(self._on_server_state)
        session.session_finished.connect(partial(self._session_finished, session))
        self.sessions[server_id] = session
        self._append_console(
            server_id,
            f"\n[{self._timestamp()}] Подключение к {server.ssh_user}@{server.host}:{server.port}…\n",
        )
        session.start()
        return session

    def _session_for_command(self, server: Server) -> SSHSession | None:
        session = self._connect_server(server)
        if session is None:
            return None
        return session

    def _stop_session(self, server_id: int) -> None:
        session = self.sessions.get(server_id)
        if session is not None:
            session.stop()

    def _session_finished(self, session: SSHSession, server_id: int, reason: str) -> None:
        if self.sessions.get(server_id) is session:
            self.sessions.pop(server_id, None)
            interrupted = [
                (action, target) for sid, action, target in self.pending_commands.values()
                if sid == server_id
            ]
            self.pending_command_output = {
                token: output for token, output in self.pending_command_output.items()
                if self.pending_commands.get(token, (None,))[0] != server_id
            }
            self.pending_commands = {
                token: command for token, command in self.pending_commands.items()
                if command[0] != server_id
            }
            for action, target in interrupted:
                if target == "all":
                    names = [service.name for service in self.db.list_services(server_id)]
                else:
                    names = [target]
                for name in names:
                    self._set_service_status(server_id, name, "unknown")
        self._append_console(server_id, f"\n[{self._timestamp()}] {reason}\n")

    def _on_server_state(self, server_id: int, state: str) -> None:
        self.server_states[server_id] = state
        if self.active_server and self.active_server.id == server_id:
            self._set_state_label(state)
        if state == "online":
            server = next((item for item in self.servers if item.id == server_id), None)
            session = self.sessions.get(server_id)
            if server and session and server.management_script_path:
                if self._send_managed_command(
                    server, server.management_script_path, "status", "all", session=session
                ):
                    for service in self.db.list_services(server_id):
                        self._set_service_status(server_id, service.name, "checking")

    def _set_state_label(self, state: str) -> None:
        mapping = {
            "online": ("● ONLINE", "statusOnline"),
            "connecting": ("● CONNECTING", "statusConnecting"),
            "offline": ("● OFFLINE", "statusOffline"),
        }
        text, object_name = mapping.get(state, mapping["offline"])
        self.state_label.setText(text)
        self.state_label.setObjectName(object_name)
        self.state_label.style().unpolish(self.state_label)
        self.state_label.style().polish(self.state_label)
        self.connect_button.setText("Отключить" if state in {"online", "connecting"} else "Подключить")

    def _append_console(self, server_id: int, text: str) -> None:
        buffer = self.console_buffers.setdefault(server_id, [])
        buffer.append(text)
        if self.active_server and self.active_server.id == server_id:
            self.terminal_renderer.write(self.terminal, text)

    def _show_console(self, server_id: int) -> None:
        self.terminal.clear()
        self.terminal_renderer = AnsiTerminalRenderer()
        self.terminal_renderer.write(
            self.terminal, "".join(self.console_buffers.get(server_id, []))
        )

    def _clear_console(self) -> None:
        if self.active_server and self.active_server.id:
            self.console_buffers[self.active_server.id] = []
        self.terminal.clear()
        self.terminal_renderer = AnsiTerminalRenderer()

    def _interrupt_command(self) -> None:
        if not self.active_server or self.active_server.id is None:
            return
        session = self.sessions.get(self.active_server.id)
        if session and session.isRunning():
            session.send_interrupt()

    @staticmethod
    def _timestamp() -> str:
        return datetime.now().strftime("%H:%M:%S")

    def _show_db_error(self, exc: Exception) -> None:
        text = str(exc)
        if "UNIQUE constraint failed" in text:
            text = "Такая запись уже существует. Измените название или параметры подключения."
        QMessageBox.critical(self, "Не удалось сохранить", text)

    def closeEvent(self, event) -> None:
        sessions = list(self.sessions.values())
        for session in sessions:
            session.stop()
        for session in sessions:
            session.wait(9000)
        event.accept()
