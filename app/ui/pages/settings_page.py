"""
Pantalla — Configuración de red
Solo contiene lo necesario para la rúbrica: interfaces WAN/LAN, IP del servidor.
"""

import subprocess
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QScrollArea, QPushButton, QLineEdit, QComboBox, QFormLayout,
)
from PySide6.QtCore import Qt, Signal
from app.core import validators
from app.services import network_service
from app.constants import LINUX_RULES_FILE, LINUX_LOG_FILE


class SettingsPage(QWidget):
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
        layout.setSpacing(20)

        title = QLabel("Configuración")
        title.setObjectName("label_title")
        layout.addWidget(title)

        layout.addWidget(self._build_network_card())
        layout.addWidget(self._build_info_card())

        # Botón guardar
        self._save_error_lbl = QLabel("")
        self._save_error_lbl.setStyleSheet("color: #ef4444; font-size: 12px; background: transparent;")
        layout.addWidget(self._save_error_lbl)

        save_row = QHBoxLayout()
        btn_save = QPushButton("Guardar configuración")
        btn_save.setObjectName("btn_primary")
        btn_save.setMinimumHeight(38)
        btn_save.setMinimumWidth(200)
        btn_save.clicked.connect(self._save_all)
        save_row.addStretch()
        save_row.addWidget(btn_save)
        layout.addLayout(save_row)

        layout.addStretch()
        scroll.setWidget(container)
        main_layout.addWidget(scroll)

    def _build_network_card(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("card")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(20, 16, 20, 20)
        layout.setSpacing(14)

        subtitle = QLabel("Configuración de Red")
        subtitle.setObjectName("label_subtitle")
        layout.addWidget(subtitle)

        desc = QLabel(
            "Configura las interfaces de red de Kali. "
            "La interfaz LAN es hacia los equipos clientes; "
            "WAN es la salida a Internet."
        )
        desc.setObjectName("label_secondary")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        form = QFormLayout()
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        ifaces = network_service.get_available_interfaces()

        self._wan_combo = QComboBox()
        self._wan_combo.addItems(ifaces)
        self._wan_combo.setMinimumWidth(200)

        self._lan_combo = QComboBox()
        self._lan_combo.addItems(ifaces)
        self._lan_combo.setMinimumWidth(200)

        self._server_ip_input = QLineEdit()
        self._server_ip_input.setPlaceholderText("ej: 192.168.50.1")
        self._server_ip_input.setMinimumWidth(200)

        self._client_net_input = QLineEdit()
        self._client_net_input.setPlaceholderText("ej: 192.168.50.0/24")
        self._client_net_input.setMinimumWidth(200)

        form.addRow("Interfaz WAN (salida a Internet):", self._wan_combo)
        form.addRow("Interfaz LAN (hacia clientes):", self._lan_combo)
        form.addRow("IP del servidor Kali:", self._server_ip_input)
        form.addRow("Red de clientes (CIDR):", self._client_net_input)
        layout.addLayout(form)

        self._net_error = QLabel("")
        self._net_error.setStyleSheet("color: #ef4444; font-size: 12px; background: transparent;")
        layout.addWidget(self._net_error)

        btn_row = QHBoxLayout()
        btn_detect = QPushButton("Detectar automáticamente")
        btn_detect.setObjectName("btn_secondary")
        btn_detect.setToolTip("Detecta la IP y la interfaz de red activa automáticamente.")
        btn_detect.clicked.connect(self._auto_detect)
        btn_row.addWidget(btn_detect)

        btn_diag = QPushButton("Ejecutar diagnóstico")
        btn_diag.setObjectName("btn_secondary")
        btn_diag.setToolTip("Verifica IP Forward, MASQUERADE y configuración de interfaces.")
        btn_diag.clicked.connect(self._run_diag)
        btn_row.addWidget(btn_diag)

        btn_row.addStretch()
        layout.addLayout(btn_row)

        # Resultado diagnóstico
        self._diag_label = QLabel("")
        self._diag_label.setObjectName("label_secondary")
        self._diag_label.setWordWrap(True)
        self._diag_label.setVisible(False)
        layout.addWidget(self._diag_label)

        return frame

    def _build_info_card(self) -> QFrame:
        """Muestra las rutas del sistema (solo informativo, no editable por el usuario)."""
        frame = QFrame()
        frame.setObjectName("card")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(10)

        subtitle = QLabel("Rutas del Sistema (solo lectura)")
        subtitle.setObjectName("label_subtitle")
        layout.addWidget(subtitle)

        desc = QLabel(
            "Las reglas se guardan en un archivo personalizado "
            "(NO en /etc/sysconfig/iptables, según lo requiere la rúbrica)."
        )
        desc.setObjectName("label_secondary")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        rules_path = self._config.get("rules_file", "") or LINUX_RULES_FILE
        log_path   = self._config.get("log_file", "")   or LINUX_LOG_FILE

        form = QFormLayout()
        form.setSpacing(8)

        rules_lbl = QLabel(rules_path)
        rules_lbl.setStyleSheet(
            "font-family: 'Consolas','Courier New',monospace; font-size: 11px; "
            "color: #22c55e; background: #020208; border: 1px solid #1a2a1a; "
            "border-radius: 4px; padding: 5px 8px;"
        )
        rules_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        form.addRow("Archivo de reglas:", rules_lbl)

        log_lbl = QLabel(log_path)
        log_lbl.setStyleSheet(
            "font-family: 'Consolas','Courier New',monospace; font-size: 11px; "
            "color: #22c55e; background: #020208; border: 1px solid #1a2a1a; "
            "border-radius: 4px; padding: 5px 8px;"
        )
        log_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        form.addRow("Log de paquetes rechazados:", log_lbl)

        layout.addLayout(form)
        return frame

    def _load_config(self):
        cfg = self._config
        ifaces = network_service.get_available_interfaces()
        wan = cfg.get("interfaces", {}).get("wan", "")
        lan = cfg.get("interfaces", {}).get("lan", "")
        if wan in ifaces:
            self._wan_combo.setCurrentText(wan)
        if lan in ifaces:
            self._lan_combo.setCurrentText(lan)
        self._server_ip_input.setText(cfg.get("server_ip", ""))
        self._client_net_input.setText(cfg.get("client_network", ""))

    def _save_all(self):
        # Validar IP servidor
        srv_ip = self._server_ip_input.text().strip()
        if srv_ip:
            ok, msg = validators.validate_ipv4(srv_ip)
            if not ok:
                self._net_error.setText(f"IP servidor: {msg}")
                self._save_error_lbl.setText(f"Error: {msg}")
                return

        # Validar red cliente
        client_net = self._client_net_input.text().strip()
        if client_net:
            ok, msg = validators.validate_cidr(client_net)
            if not ok:
                self._net_error.setText(f"Red cliente: {msg}")
                self._save_error_lbl.setText(f"Error: {msg}")
                return

        self._net_error.setText("")
        self._save_error_lbl.setText("")

        self._config.setdefault("interfaces", {})
        self._config["interfaces"]["wan"] = self._wan_combo.currentText()
        self._config["interfaces"]["lan"] = self._lan_combo.currentText()
        self._config["server_ip"] = srv_ip
        self._config["client_network"] = client_net

        self.config_changed.emit(self._config)
        self._save_error_lbl.setText("")
        # Feedback visual
        self._save_error_lbl.setStyleSheet("color: #22c55e; font-size: 12px; background: transparent;")
        self._save_error_lbl.setText("✓ Configuración guardada correctamente.")

    def _auto_detect(self):
        ip, iface = network_service.get_own_ip_and_interface()
        self._server_ip_input.setText(ip)
        ifaces = network_service.get_available_interfaces()
        if iface in ifaces:
            self._lan_combo.setCurrentText(iface)
        self._net_error.setText(f"Detectado: IP={ip}, interfaz={iface}")
        self._net_error.setStyleSheet("color: #22c55e; font-size: 12px; background: transparent;")

    def _run_diag(self):
        from app.core.platform_detector import is_linux, has_ip_forward
        lines = []

        # IP Forward
        if is_linux():
            ip_fwd = has_ip_forward()
            icon = "✓" if ip_fwd else "✗"
            color = "#22c55e" if ip_fwd else "#ef4444"
            lines.append(f'<span style="color:{color}">{icon} IP Forward: {"activo" if ip_fwd else "INACTIVO"}</span>')
        else:
            lines.append('<span style="color:#6b7585">— IP Forward: modo demo</span>')

        # MASQUERADE
        masq = False
        if is_linux():
            try:
                r = subprocess.run(
                    ["iptables", "-t", "nat", "-L", "POSTROUTING", "-n"],
                    capture_output=True, text=True, timeout=5,
                )
                masq = "MASQUERADE" in r.stdout
            except Exception:
                masq = False
        icon = "✓" if masq else "✗"
        color = "#22c55e" if masq else "#f59e0b"
        msg = "configurado" if masq else "falta (aplica las reglas primero)"
        lines.append(f'<span style="color:{color}">{icon} NAT MASQUERADE: {msg}</span>')

        # Interfaces
        wan = self._config.get("interfaces", {}).get("wan", "")
        lan = self._config.get("interfaces", {}).get("lan", "")
        lines.append(f'<span style="color:#8892a4">  WAN: {wan or "no configurada"}  |  LAN: {lan or "no configurada"}</span>')

        # IP servidor
        srv = self._config.get("server_ip", "")
        if srv:
            lines.append(f'<span style="color:#3b82f6">  IP Kali: {srv}</span>')
            lines.append(f'<span style="color:#8892a4">  Gateway para clientes Linux: <b>sudo ip route add default via {srv}</b></span>')
        else:
            lines.append('<span style="color:#f59e0b">  IP del servidor no configurada</span>')

        self._diag_label.setText("<br>".join(lines))
        self._diag_label.setVisible(True)

    def update_config(self, config: dict):
        self._config = config
        self._load_config()
