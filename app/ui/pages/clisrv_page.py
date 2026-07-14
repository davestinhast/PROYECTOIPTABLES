"""
Pantalla — Control cliente / servidor (bloqueo unidireccional)
Bloquea el envio de paquetes del cliente al servidor,
pero el servidor si puede enviar paquetes al cliente.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QScrollArea, QPushButton, QLineEdit, QComboBox,
    QCheckBox, QFormLayout,
)
from PySide6.QtCore import Qt, Signal
from app.core import validators
from app.services import network_service


class CliSrvPage(QWidget):
    config_changed = Signal(dict)

    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self._config = config
        self._setup_ui()
        self._load_config()

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
        title_row = QHBoxLayout()
        title = QLabel("Control Cliente / Servidor")
        title.setObjectName("label_title")
        title_row.addWidget(title)
        title_row.addStretch()
        self._enabled_toggle = QCheckBox("Habilitar regla")
        self._enabled_toggle.setStyleSheet("font-weight: 600; font-size: 13px; background: transparent;")
        self._enabled_toggle.toggled.connect(self._on_save)
        title_row.addWidget(self._enabled_toggle)
        layout.addLayout(title_row)

        # Descripcion de la regla
        desc_card = QFrame()
        desc_card.setObjectName("card_accent_blue")
        desc_layout = QVBoxLayout(desc_card)
        desc_layout.setContentsMargins(20, 14, 20, 14)
        desc_layout.setSpacing(6)

        desc_title = QLabel("Que hace esta regla")
        desc_title.setObjectName("label_subtitle")
        desc_layout.addWidget(desc_title)

        desc_text = QLabel(
            "Bloquea los paquetes nuevos (NEW) que el cliente intenta enviar al servidor.\n"
            "El servidor SI puede enviar paquetes al cliente sin restricciones.\n"
            "Los paquetes de respuesta (ESTABLISHED/RELATED) del cliente si son permitidos."
        )
        desc_text.setObjectName("label_secondary")
        desc_text.setWordWrap(True)
        desc_layout.addWidget(desc_text)

        # Estado visual simple (2 lineas de texto)
        self._status_srv_cli = QLabel("Cliente -> Servidor (NEW): BLOQUEADO")
        self._status_srv_cli.setStyleSheet(
            "color: #ef4444; font-weight: 600; font-size: 12px; background: transparent;"
        )
        self._status_cli_srv = QLabel("Servidor -> Cliente: PERMITIDO")
        self._status_cli_srv.setStyleSheet(
            "color: #22c55e; font-weight: 600; font-size: 12px; background: transparent;"
        )
        desc_layout.addWidget(self._status_srv_cli)
        desc_layout.addWidget(self._status_cli_srv)

        layout.addWidget(desc_card)

        # Formulario de configuracion
        config_card = QFrame()
        config_card.setObjectName("card")
        config_layout = QVBoxLayout(config_card)
        config_layout.setContentsMargins(20, 16, 20, 20)
        config_layout.setSpacing(14)

        config_title = QLabel("Configuracion")
        config_title.setObjectName("label_subtitle")
        config_layout.addWidget(config_title)

        form = QFormLayout()
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._srv_ip_input = QLineEdit()
        self._srv_ip_input.setPlaceholderText("ej: 192.168.50.1")
        self._srv_ip_input.setMinimumWidth(220)
        self._srv_ip_input.editingFinished.connect(self._on_save)

        self._cli_ip_input = QLineEdit()
        self._cli_ip_input.setPlaceholderText("ej: 192.168.50.10  o  192.168.50.0/24")
        self._cli_ip_input.setMinimumWidth(220)
        self._cli_ip_input.editingFinished.connect(self._on_save)

        self._iface_combo = QComboBox()
        self._iface_combo.addItem("(cualquier interfaz)")
        self._iface_combo.addItems(network_service.get_available_interfaces())
        self._iface_combo.setMinimumWidth(220)
        self._iface_combo.currentIndexChanged.connect(self._on_save)

        # Protocolos en una sola fila
        proto_widget = QWidget()
        proto_widget.setStyleSheet("background: transparent;")
        proto_row = QHBoxLayout(proto_widget)
        proto_row.setContentsMargins(0, 0, 0, 0)
        proto_row.setSpacing(16)
        self._proto_tcp  = QCheckBox("TCP")
        self._proto_udp  = QCheckBox("UDP")
        self._proto_icmp = QCheckBox("ICMP")
        self._proto_tcp.setChecked(True)
        for cb in [self._proto_tcp, self._proto_udp, self._proto_icmp]:
            cb.toggled.connect(self._on_save)
            proto_row.addWidget(cb)
        proto_row.addStretch()

        self._action_combo = QComboBox()
        self._action_combo.addItems(["DROP", "REJECT"])
        self._action_combo.setMinimumWidth(120)
        self._action_combo.currentIndexChanged.connect(self._on_save)

        form.addRow("IP del servidor:", self._srv_ip_input)
        form.addRow("IP del cliente:", self._cli_ip_input)
        form.addRow("Interfaz LAN:", self._iface_combo)
        form.addRow("Protocolos a bloquear:", proto_widget)
        form.addRow("Accion:", self._action_combo)
        config_layout.addLayout(form)

        # Boton autodetectar IP del servidor
        btn_row = QHBoxLayout()
        btn_detect = QPushButton("Detectar IP del servidor")
        btn_detect.setObjectName("btn_secondary")
        btn_detect.clicked.connect(self._auto_detect_srv)
        btn_row.addWidget(btn_detect)
        btn_row.addStretch()
        config_layout.addLayout(btn_row)

        # Error
        self._error_label = QLabel("")
        self._error_label.setStyleSheet("color: #ef4444; font-size: 12px; background: transparent;")
        config_layout.addWidget(self._error_label)

        layout.addWidget(config_card)

        # Nota importante
        note = QLabel(
            "Nota: Esta regla afecta el trafico en el chain FORWARD (clientes que pasan por Kali). "
            "El cliente debe tener a Kali como puerta de enlace (gateway) para que funcione."
        )
        note.setObjectName("label_hint")
        note.setWordWrap(True)
        layout.addWidget(note)

        layout.addStretch()
        scroll.setWidget(container)
        main_layout.addWidget(scroll)

    def _load_config(self):
        clisrv = self._config.get("clisrv", {})

        self._enabled_toggle.blockSignals(True)
        self._enabled_toggle.setChecked(clisrv.get("enabled", False))
        self._enabled_toggle.blockSignals(False)

        srv_ip = clisrv.get("server_ip", "") or self._config.get("server_ip", "")
        self._srv_ip_input.setText(srv_ip)

        cli_ip = clisrv.get("client_ip", "")
        if not cli_ip:
            net = self._config.get("client_network", "")
            if net and "/" in net:
                base = net.split("/")[0]
                parts = base.split(".")
                if len(parts) == 4:
                    cli_ip = f"{parts[0]}.{parts[1]}.{parts[2]}.10"
        self._cli_ip_input.setText(cli_ip)

        protos = clisrv.get("protocols", ["tcp"])
        self._proto_tcp.blockSignals(True)
        self._proto_udp.blockSignals(True)
        self._proto_icmp.blockSignals(True)
        self._proto_tcp.setChecked("tcp" in protos)
        self._proto_udp.setChecked("udp" in protos)
        self._proto_icmp.setChecked("icmp" in protos)
        self._proto_tcp.blockSignals(False)
        self._proto_udp.blockSignals(False)
        self._proto_icmp.blockSignals(False)

        action = clisrv.get("action", "DROP")
        idx = self._action_combo.findText(action)
        if idx >= 0:
            self._action_combo.setCurrentIndex(idx)

        iface = clisrv.get("interface", "")
        if iface:
            idx = self._iface_combo.findText(iface)
            if idx >= 0:
                self._iface_combo.setCurrentIndex(idx)

        self._update_status()

    def _update_status(self):
        enabled = self._enabled_toggle.isChecked()
        srv = self._srv_ip_input.text().strip() or "SERVIDOR"
        cli = self._cli_ip_input.text().strip() or "CLIENTE"
        if enabled:
            self._status_srv_cli.setText(f"{cli} -> {srv} (NEW): BLOQUEADO")
            self._status_cli_srv.setText(f"{srv} -> {cli}: PERMITIDO")
        else:
            self._status_srv_cli.setText(f"{cli} -> {srv}: sin restricciones (regla desactivada)")
            self._status_srv_cli.setStyleSheet(
                "color: #6b7585; font-weight: 600; font-size: 12px; background: transparent;"
            )
            self._status_cli_srv.setText(f"{srv} -> {cli}: sin restricciones (regla desactivada)")
            self._status_cli_srv.setStyleSheet(
                "color: #6b7585; font-weight: 600; font-size: 12px; background: transparent;"
            )

    def _auto_detect_srv(self):
        ip, iface = network_service.get_own_ip_and_interface()
        self._srv_ip_input.setText(ip)
        ifaces = network_service.get_available_interfaces()
        if iface in ifaces:
            self._iface_combo.setCurrentText(iface)
        self._on_save()

    def _on_save(self):
        srv_text = self._srv_ip_input.text().strip()
        cli_text = self._cli_ip_input.text().strip()

        if srv_text:
            ok, msg = validators.validate_ipv4(srv_text)
            if not ok:
                self._error_label.setText(f"IP servidor: {msg}")
                return
        if cli_text:
            # Aceptar IP o CIDR para el cliente
            ok, msg = validators.validate_ipv4(cli_text)
            if not ok:
                ok2, _ = validators.validate_cidr(cli_text)
                if not ok2:
                    self._error_label.setText(f"IP cliente: debe ser una IP o CIDR valido")
                    return

        self._error_label.setText("")
        protocols = []
        if self._proto_tcp.isChecked():  protocols.append("tcp")
        if self._proto_udp.isChecked():  protocols.append("udp")
        if self._proto_icmp.isChecked(): protocols.append("icmp")
        if not protocols:
            protocols = ["tcp"]

        iface = self._iface_combo.currentText()
        self._config["clisrv"] = {
            "enabled":    self._enabled_toggle.isChecked(),
            "server_ip":  srv_text,
            "client_ip":  cli_text,
            "interface":  "" if "(cualquier" in iface else iface,
            "protocols":  protocols,
            "action":     self._action_combo.currentText(),
        }
        self._update_status()
        self.config_changed.emit(self._config)

    def update_config(self, config: dict):
        self._config = config
        self._load_config()
