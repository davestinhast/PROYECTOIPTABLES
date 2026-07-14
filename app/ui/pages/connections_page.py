"""
Pantalla — Limite de conexiones simultaneas (connlimit)
Explica la funcionalidad como un limite de accesos al mismo tiempo por dispositivo.
"""

import copy
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QScrollArea, QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QLineEdit, QComboBox, QSpinBox, QDialog,
    QDialogButtonBox, QFormLayout,
)
from PySide6.QtCore import Qt, Signal
from app.constants import DEFAULT_CONN_PROFILES


class AddProfileDialog(QDialog):
    def __init__(self, profile: dict = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Nuevo limite de conexiones")
        self.setMinimumWidth(400)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        title = QLabel("Limitar visitas de un dispositivo")
        title.setObjectName("label_subtitle")
        layout.addWidget(title)

        form = QFormLayout()
        form.setSpacing(10)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("ej: SSH Seguro, Servidor Web")

        self.proto_combo = QComboBox()
        self.proto_combo.addItems(["tcp", "udp"])

        self.port_spin = QSpinBox()
        self.port_spin.setRange(1, 65535)
        self.port_spin.setValue(80)

        self.max_spin = QSpinBox()
        self.max_spin.setRange(1, 1000)
        self.max_spin.setValue(5)
        self.max_spin.setSuffix(" conexiones")

        self.action_combo = QComboBox()
        self.action_combo.addItems(["REJECT", "DROP"])

        if profile:
            self.name_input.setText(profile.get("name", ""))
            idx = self.proto_combo.findText(profile.get("proto", "tcp"))
            if idx >= 0: self.proto_combo.setCurrentIndex(idx)
            self.port_spin.setValue(profile.get("port", 80))
            self.max_spin.setValue(profile.get("max", 5))
            idx2 = self.action_combo.findText(profile.get("action", "REJECT"))
            if idx2 >= 0: self.action_combo.setCurrentIndex(idx2)

        form.addRow("Nombre del perfil:", self.name_input)
        form.addRow("Protocolo (canal):", self.proto_combo)
        form.addRow("Puerto (puerta):", self.port_spin)
        form.addRow("Maximo de visitas simultaneas:", self.max_spin)
        form.addRow("Accion al pasarse del limite:", self.action_combo)
        layout.addLayout(form)

        # Explicacion del dialogo
        hint = QLabel(
            "Esto evitara que una sola IP pueda saturar este puerto "
            "abriendo mas conexiones que el limite permitido."
        )
        hint.setObjectName("label_hint")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_profile(self) -> dict:
        return {
            "name": self.name_input.text().strip() or f"Puerto {self.port_spin.value()}",
            "proto": self.proto_combo.currentText(),
            "port": self.port_spin.value(),
            "max": self.max_spin.value(),
            "action": self.action_combo.currentText(),
            "enabled": True,
        }


class ConnectionsPage(QWidget):
    config_changed = Signal(dict)

    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self._config = config
        if not self._config.get("conn_profiles"):
            self._config["conn_profiles"] = copy.deepcopy(DEFAULT_CONN_PROFILES)
        self._setup_ui()
        self._refresh_table()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        # Titulo
        title = QLabel("Limite de Conexiones por Dispositivo")
        title.setObjectName("label_title")
        layout.addWidget(title)



        # Tabla de perfiles
        layout.addWidget(self._build_profiles_card())

        # Ficha tecnica simplificada
        info_frame = QFrame()
        info_frame.setObjectName("card")
        info_layout = QVBoxLayout(info_frame)
        info_layout.setContentsMargins(20, 14, 20, 14)
        info_layout.setSpacing(6)

        info_title = QLabel("Comando iptables que se ejecuta por detras:")
        info_title.setObjectName("label_subtitle")
        info_layout.addWidget(info_title)

        example_lbl = QLabel(
            "iptables -A PM_CONNLIMIT -p tcp --dport [PUERTO] -m connlimit --connlimit-above [MAXIMO] -j REJECT"
        )
        example_lbl.setObjectName("label_mono")
        example_lbl.setWordWrap(True)
        info_layout.addWidget(example_lbl)
        layout.addWidget(info_frame)

        layout.addStretch()
        scroll.setWidget(container)
        main_layout.addWidget(scroll)

    def _build_profiles_card(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("card")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        top_row = QHBoxLayout()
        subtitle = QLabel("Puertos Protegidos")
        subtitle.setObjectName("label_subtitle")
        top_row.addWidget(subtitle)
        top_row.addStretch()

        btn_add = QPushButton("Proteger nuevo puerto")
        btn_add.setObjectName("btn_primary")
        btn_add.clicked.connect(self._add_profile)
        top_row.addWidget(btn_add)
        layout.addLayout(top_row)

        self._table = QTableWidget(0, 6)
        self._table.setHorizontalHeaderLabels(["Nombre", "Protocolo", "Puerto", "Limite Maximo", "Accion", "Estado"])
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setMaximumHeight(280)
        layout.addWidget(self._table)

        return frame

    def _refresh_table(self):
        profiles = self._config.get("conn_profiles", [])
        self._table.setRowCount(len(profiles))
        for row, p in enumerate(profiles):
            self._table.setItem(row, 0, QTableWidgetItem(p.get("name", "")))
            self._table.setItem(row, 1, QTableWidgetItem(p.get("proto", "tcp").upper()))
            self._table.setItem(row, 2, QTableWidgetItem(str(p.get("port", ""))))
            self._table.setItem(row, 3, QTableWidgetItem(f"Max. {p.get('max', '')} conexiones"))
            self._table.setItem(row, 4, QTableWidgetItem(p.get("action", "REJECT")))

            from PySide6.QtWidgets import QCheckBox as _QCB
            chk = _QCB("Activo" if p.get("enabled", False) else "Inactivo")
            chk.setChecked(p.get("enabled", False))
            chk.setStyleSheet(
                "QCheckBox { color: #8AAABB; font-size: 11px; padding: 0 8px; background: transparent; }"
                "QCheckBox:checked { color: #22C55E; }"
                "QCheckBox::indicator { width:14px; height:14px; border-radius:4px; border:1px solid #2B3E5C; background:#1F3050; }"
                "QCheckBox::indicator:checked { background:#3B82F6; border-color:#3B82F6; }"
            )
            chk.toggled.connect(lambda checked, r=row, c=chk: (
                c.setText("Activo" if checked else "Inactivo"),
                self._toggle_profile(r, checked)
            ))
            self._table.setCellWidget(row, 5, chk)

    def _add_profile(self):
        dialog = AddProfileDialog(parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._config["conn_profiles"].append(dialog.get_profile())
            self._refresh_table()
            self.config_changed.emit(self._config)

    def _toggle_profile(self, row: int, enabled: bool):
        profiles = self._config.get("conn_profiles", [])
        if 0 <= row < len(profiles):
            profiles[row]["enabled"] = enabled
            self.config_changed.emit(self._config)

    def update_config(self, config: dict):
        self._config = config
        if not self._config.get("conn_profiles"):
            self._config["conn_profiles"] = copy.deepcopy(DEFAULT_CONN_PROFILES)
        self._refresh_table()
