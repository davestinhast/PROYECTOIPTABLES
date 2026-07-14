"""
Pantalla 1 — Bloqueo de sitios web
Bloquea acceso a Facebook, YouTube y Hotmail mediante ipset + iptables.
"""

import subprocess
from datetime import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QScrollArea, QPushButton, QApplication,
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtWidgets import QCheckBox
from app.constants import BLOCKED_DOMAINS, LINUX_RULES_FILE, IPSET_SET_PREFIX


# ─── WORKERS ─────────────────────────────────────────────────────────────────

class _EnableIPForwardWorker(QThread):
    finished = Signal(bool)

    def run(self):
        from app.core.platform_detector import enable_ip_forward
        ok = enable_ip_forward()
        self.finished.emit(ok)


class _CheckSiteWorker(QThread):
    """Verifica cuántas IPs tiene el ipset set y si el sitio es accesible."""
    finished = Signal(str, int, bool)  # key, ip_count_in_set, reachable

    def __init__(self, key: str, domain: str):
        super().__init__()
        self._key = key
        self._domain = domain

    def run(self):
        set_name = f"{IPSET_SET_PREFIX}{self._key.upper()}"

        # Contar IPs en el ipset set
        ip_count = 0
        try:
            result = subprocess.run(
                ["ipset", "list", set_name, "-terse"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    if line.startswith("Number of entries:"):
                        ip_count = int(line.split(":")[1].strip())
                        break
        except Exception:
            ip_count = -1  # ipset no disponible o set no existe

        # Verificar accesibilidad TCP (puerto 443)
        import socket
        reachable = False
        if self._domain:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(3)
                s.connect((self._domain, 443))
                s.close()
                reachable = True
            except Exception:
                reachable = False

        self.finished.emit(self._key, ip_count, reachable)


class _RefreshIpsetWorker(QThread):
    progress = Signal(str)
    finished = Signal(bool, str)

    def __init__(self, config: dict):
        super().__init__()
        self._config = config

    def run(self):
        from app.services import firewall_service
        self.progress.emit("Resolviendo IPs actuales...")
        ok, msg = firewall_service.refresh_ipset(self._config)
        self.finished.emit(ok, msg)


# ─── STATUS BAR (reemplaza la prereq card compleja) ──────────────────────────

class _StatusBar(QFrame):
    """Barra de estado simple: IP Forward + botón activar."""

    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self._config = config
        self._worker = None
        self.setObjectName("card_accent_blue")
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(12)

        # IP Forward status
        self._ipfwd_lbl = QLabel("Verificando...")
        self._ipfwd_lbl.setObjectName("label_secondary")
        layout.addWidget(self._ipfwd_lbl)

        self._btn_enable_ipfwd = QPushButton("Activar IP Forward")
        self._btn_enable_ipfwd.setObjectName("btn_success")
        self._btn_enable_ipfwd.setVisible(False)
        self._btn_enable_ipfwd.clicked.connect(self._on_enable)
        layout.addWidget(self._btn_enable_ipfwd)

        layout.addStretch()

        # Mostrar ruta del archivo de reglas
        rules_path = self._config.get("rules_file", "") or LINUX_RULES_FILE
        path_lbl = QLabel(f"Archivo: {rules_path}")
        path_lbl.setObjectName("label_hint")
        layout.addWidget(path_lbl)

        # Botón copiar comando de gateway
        srv_ip = self._config.get("server_ip", "") or "X.X.X.X"
        self._gw_cmd = f"sudo ip route add default via {srv_ip}"
        btn_copy_gw = QPushButton("Copiar cmd gateway")
        btn_copy_gw.setObjectName("btn_small")
        btn_copy_gw.setToolTip(
            f"Ejecutar en los PCs cliente para configurar gateway:\n{self._gw_cmd}"
        )
        btn_copy_gw.clicked.connect(
            lambda: QApplication.clipboard().setText(self._gw_cmd)
        )
        layout.addWidget(btn_copy_gw)

        self.refresh()

    def refresh(self):
        from app.core.platform_detector import is_linux, has_ip_forward
        if is_linux():
            if has_ip_forward():
                self._ipfwd_lbl.setText("✓  IP Forward activo")
                self._ipfwd_lbl.setStyleSheet("color: #22c55e; font-size: 12px; background: transparent;")
                self._btn_enable_ipfwd.setVisible(False)
            else:
                self._ipfwd_lbl.setText("✗  IP Forward INACTIVO — el bloqueo no funcionará en clientes")
                self._ipfwd_lbl.setStyleSheet("color: #ef4444; font-size: 12px; font-weight: 600; background: transparent;")
                self._btn_enable_ipfwd.setVisible(True)
        else:
            self._ipfwd_lbl.setText("— Modo demo (IP Forward no aplica)")
            self._ipfwd_lbl.setStyleSheet("color: #6b7585; font-size: 12px; background: transparent;")

    def _on_enable(self):
        self._btn_enable_ipfwd.setEnabled(False)
        self._btn_enable_ipfwd.setText("Activando...")
        self._worker = _EnableIPForwardWorker()
        self._worker.finished.connect(self._on_done)
        self._worker.start()

    def _on_done(self, ok: bool):
        self._btn_enable_ipfwd.setEnabled(True)
        self._btn_enable_ipfwd.setText("Activar IP Forward")
        self.refresh()

    def update_config(self, config: dict):
        self._config = config


# ─── SITE CARD ───────────────────────────────────────────────────────────────

class SiteCard(QFrame):
    toggled         = Signal(str, bool)
    check_requested = Signal(str)

    def __init__(self, key: str, cfg: dict, parent=None):
        super().__init__(parent)
        self._key = key
        self._cfg = cfg
        self.setObjectName("card")
        self._setup_ui()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 14, 20, 14)
        main_layout.setSpacing(10)

        # ── Fila superior: nombre + toggle + botón verificar ──
        top_row = QHBoxLayout()
        top_row.setSpacing(16)

        # Nombre del sitio
        label_name = QLabel(self._cfg["label"])
        label_name.setObjectName("label_title")
        label_name.setStyleSheet("font-size: 15px; font-weight: 700; color: #e8eaf0; background: transparent;")
        top_row.addWidget(label_name)

        # Descripción
        desc = QLabel(self._cfg.get("description", ""))
        desc.setObjectName("label_secondary")
        top_row.addWidget(desc, stretch=1)

        # Toggle
        self._toggle = QCheckBox("Habilitar bloqueo")
        self._toggle.setChecked(self._cfg.get("enabled", False))
        self._toggle.toggled.connect(lambda checked: self.toggled.emit(self._key, checked))
        self._toggle.setStyleSheet("font-weight: 600; color: #c0c8d8; background: transparent;")
        top_row.addWidget(self._toggle)

        # Botón verificar
        self._btn_check = QPushButton("Verificar")
        self._btn_check.setObjectName("btn_small")
        self._btn_check.clicked.connect(lambda: self.check_requested.emit(self._key))
        top_row.addWidget(self._btn_check)

        main_layout.addLayout(top_row)

        # ── Separador ──
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        main_layout.addWidget(sep)

        # ── Fila inferior: estado del set ipset + accesibilidad ──
        status_row = QHBoxLayout()
        status_row.setSpacing(20)

        self._badge = QLabel("○  Sin verificar")
        self._badge.setStyleSheet(
            "color: #4a5060; font-size: 12px; font-weight: 600; background: transparent;"
        )
        status_row.addWidget(self._badge)

        self._ipset_label = QLabel("ipset: —")
        self._ipset_label.setObjectName("label_mono")
        status_row.addWidget(self._ipset_label)

        self._reach_label = QLabel("")
        self._reach_label.setObjectName("label_secondary")
        status_row.addWidget(self._reach_label)

        status_row.addStretch()

        # Dominios (colapsado como texto pequeño)
        domains_text = "  ·  ".join(self._cfg.get("domains", [])[:4])
        if len(self._cfg.get("domains", [])) > 4:
            domains_text += "  ..."
        domains_lbl = QLabel(domains_text)
        domains_lbl.setObjectName("label_mono")
        domains_lbl.setStyleSheet("color: #3a4050; font-size: 10px; background: transparent;")
        status_row.addWidget(domains_lbl)

        main_layout.addLayout(status_row)

    def set_checking(self, checking: bool):
        self._btn_check.setEnabled(not checking)
        if checking:
            self._badge.setText("⏳  Verificando...")
            self._badge.setStyleSheet(
                "color: #f59e0b; font-size: 12px; font-weight: 600; background: transparent;"
            )

    def set_check_result(self, ip_count: int, reachable: bool):
        """
        ip_count: -1 = ipset no disponible / set no existe
                   0 = set existe pero vacío (reglas no aplicadas)
                  >0 = set con IPs cargadas
        reachable: True si la conexión TCP:443 al dominio fue exitosa
        """
        ts = datetime.now().strftime("%H:%M")

        if ip_count == -1:
            # ipset no disponible (modo demo o sin root)
            self._badge.setText("○  No disponible (modo demo)")
            self._badge.setStyleSheet(
                "color: #4a5060; font-size: 12px; font-weight: 600; background: transparent;"
            )
            self._ipset_label.setText(f"ipset: — ({ts})")
            self._ipset_label.setStyleSheet("color: #4a5060; font-size: 11px; background: transparent;")
            self._reach_label.setText("")
        elif ip_count == 0:
            # Set vacío o no existe → bloqueo inactivo
            self._badge.setText("🟡  INACTIVO — aplica las reglas primero")
            self._badge.setStyleSheet(
                "color: #f59e0b; font-size: 12px; font-weight: 600; background: transparent;"
            )
            self._ipset_label.setText(f"ipset: 0 IPs cargadas ({ts})")
            self._ipset_label.setStyleSheet("color: #f59e0b; font-size: 11px; background: transparent;")
            if reachable:
                self._reach_label.setStyleSheet("color: #ef4444; font-size: 11px; background: transparent;")
                self._reach_label.setText("TCP 443: accesible (sin bloqueo)")
            else:
                self._reach_label.setText("")
        else:
            # Set con IPs → bloqueo activo
            if reachable:
                # Hay IPs en el set pero el sitio responde → puede ser que Kali no sea el gateway
                self._badge.setText("🟠  PARCIAL — set cargado pero sitio alcanzable desde Kali")
                self._badge.setStyleSheet(
                    "color: #f97316; font-size: 12px; font-weight: 600; background: transparent;"
                )
                self._reach_label.setStyleSheet("color: #f97316; font-size: 11px; background: transparent;")
                self._reach_label.setText("Kali también es cliente — normal si OUTPUT no bloquea a Kali")
            else:
                self._badge.setText("🔴  BLOQUEADO")
                self._badge.setStyleSheet(
                    "color: #ef4444; font-size: 12px; font-weight: 600; background: transparent;"
                )
                self._reach_label.setStyleSheet("color: #22c55e; font-size: 11px; background: transparent;")
                self._reach_label.setText("TCP 443: bloqueado ✓")

            self._ipset_label.setText(f"ipset: {ip_count} IPs bloqueadas ({ts})")
            self._ipset_label.setStyleSheet("color: #22c55e; font-size: 11px; background: transparent;")

        self._btn_check.setEnabled(True)

    def set_enabled(self, enabled: bool):
        self._toggle.blockSignals(True)
        self._toggle.setChecked(enabled)
        self._toggle.blockSignals(False)


# ─── PAGE ────────────────────────────────────────────────────────────────────

class WebsitesPage(QWidget):
    config_changed = Signal(dict)

    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self._config = config
        self._workers: list   = []
        self._checking: set   = set()
        self._refresh_worker  = None

        self._auto_timer = QTimer(self)
        self._auto_timer.setInterval(30_000)
        self._auto_timer.timeout.connect(self._verify_all)

        self._setup_ui()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(14)

        # ── Título y botones de acción ──
        title_row = QHBoxLayout()
        title = QLabel("Bloqueo de Sitios Web")
        title.setObjectName("label_title")
        title_row.addWidget(title)
        title_row.addStretch()

        btn_refresh_ips = QPushButton("↻  Actualizar IPs bloqueadas")
        btn_refresh_ips.setObjectName("btn_secondary")
        btn_refresh_ips.setToolTip(
            "Resuelve los dominios de nuevo y actualiza los sets de ipset.\n"
            "Útil cuando las IPs de Facebook/YouTube/Hotmail cambian (CDN).\n"
            "No necesita recargar las reglas iptables."
        )
        btn_refresh_ips.clicked.connect(self._on_refresh_ips)
        title_row.addWidget(btn_refresh_ips)
        self._btn_refresh_ips = btn_refresh_ips

        btn_verify_all = QPushButton("Verificar todos")
        btn_verify_all.setObjectName("btn_secondary")
        btn_verify_all.clicked.connect(self._verify_all)
        title_row.addWidget(btn_verify_all)

        btn_flush = QPushButton("Limpiar todas las reglas")
        btn_flush.setObjectName("btn_danger")
        btn_flush.setToolTip(
            "Elimina TODAS las reglas iptables activas del sistema.\n"
            "Úsalo para restaurar la conectividad si algo falla."
        )
        btn_flush.clicked.connect(self._flush_rules)
        title_row.addWidget(btn_flush)

        layout.addLayout(title_row)

        # ── Barra de estado (IP Forward, ruta archivo) ──
        self._status_bar = _StatusBar(self._config)
        layout.addWidget(self._status_bar)

        # ── Descripción ──
        info = QLabel(
            "Activa los sitios que querés bloquear y presioná "
            "<b>Aplicar reglas</b> en la barra inferior. "
            "El bloqueo aplica para todos los equipos que tengan a Kali como puerta de enlace (gateway)."
        )
        info.setObjectName("label_secondary")
        info.setWordWrap(True)
        layout.addWidget(info)

        # ── Status de actualización ──
        self._refresh_status = QLabel("")
        self._refresh_status.setObjectName("label_secondary")
        self._refresh_status.setVisible(False)
        layout.addWidget(self._refresh_status)

        # ── Cards por sitio ──
        blocked = self._config.get("blocked_domains", BLOCKED_DOMAINS)
        self._site_cards: dict = {}
        for key, cfg in blocked.items():
            card = SiteCard(key, cfg)
            card.toggled.connect(self._on_toggle)
            card.check_requested.connect(self._on_check_requested)
            layout.addWidget(card)
            self._site_cards[key] = card

        layout.addStretch()
        scroll.setWidget(container)
        main_layout.addWidget(scroll)

    def showEvent(self, event):
        super().showEvent(event)
        self._status_bar.refresh()
        self._verify_all()
        if not self._auto_timer.isActive():
            self._auto_timer.start()

    def hideEvent(self, event):
        super().hideEvent(event)
        self._auto_timer.stop()

    def _verify_all(self):
        for key in self._site_cards:
            self._on_check_requested(key)

    def _on_toggle(self, key: str, enabled: bool):
        if "blocked_domains" not in self._config:
            self._config["blocked_domains"] = {}
        if key not in self._config["blocked_domains"]:
            self._config["blocked_domains"][key] = BLOCKED_DOMAINS.get(key, {})
        self._config["blocked_domains"][key]["enabled"] = enabled
        self.config_changed.emit(self._config)

    def _on_check_requested(self, key: str):
        if key in self._checking:
            return
        card = self._site_cards.get(key)
        if not card:
            return
        self._checking.add(key)
        card.set_checking(True)
        domains = (
            self._config.get("blocked_domains", BLOCKED_DOMAINS)
            .get(key, {})
            .get("domains", [])
        )
        primary_domain = domains[0] if domains else ""
        worker = _CheckSiteWorker(key, primary_domain)
        worker.finished.connect(self._on_check_done)
        self._workers.append(worker)
        worker.start()

    def _on_check_done(self, key: str, ip_count: int, reachable: bool):
        self._checking.discard(key)
        self._workers = [w for w in self._workers if w.isRunning()]
        card = self._site_cards.get(key)
        if card:
            card.set_check_result(ip_count, reachable)

    def _on_refresh_ips(self):
        if self._refresh_worker and self._refresh_worker.isRunning():
            return
        self._btn_refresh_ips.setEnabled(False)
        self._btn_refresh_ips.setText("Actualizando...")
        self._refresh_status.setText("Resolviendo IPs actuales de los dominios bloqueados...")
        self._refresh_status.setStyleSheet("color: #f59e0b; background: transparent;")
        self._refresh_status.setVisible(True)

        self._refresh_worker = _RefreshIpsetWorker(self._config)
        self._refresh_worker.progress.connect(
            lambda msg: self._refresh_status.setText(msg)
        )
        self._refresh_worker.finished.connect(self._on_refresh_done)
        self._refresh_worker.start()

    def _on_refresh_done(self, ok: bool, msg: str):
        self._btn_refresh_ips.setEnabled(True)
        self._btn_refresh_ips.setText("↻  Actualizar IPs bloqueadas")
        if ok:
            self._refresh_status.setText(f"✓  {msg}")
            self._refresh_status.setStyleSheet("color: #22c55e; background: transparent;")
        else:
            self._refresh_status.setText(f"✗  {msg}")
            self._refresh_status.setStyleSheet("color: #ef4444; background: transparent;")
        self._verify_all()

    def _flush_rules(self):
        from app.services import firewall_service
        from PySide6.QtWidgets import QMessageBox
        reply = QMessageBox.warning(
            self, "Limpiar todas las reglas",
            "Esto eliminará TODAS las reglas iptables activas del sistema.\n"
            "Los sitios bloqueados volverán a ser accesibles.\n\n¿Continuar?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        ok, msg = firewall_service.flush_all()
        if ok:
            QMessageBox.information(self, "Reglas eliminadas", msg)
            self._verify_all()
        else:
            QMessageBox.warning(self, "Error", f"No se pudo limpiar: {msg}")

    def update_config(self, config: dict):
        self._config = config
        self._status_bar.update_config(config)
        blocked = config.get("blocked_domains", {})
        for key, card in self._site_cards.items():
            if key in blocked:
                card.set_enabled(blocked[key].get("enabled", False))
