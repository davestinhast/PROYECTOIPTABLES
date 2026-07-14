"""
Pantalla — Registros de paquetes rechazados
Muestra el log en tiempo real del archivo de iptables.
"""

import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextEdit, QFrame,
)
from PySide6.QtCore import QTimer
from app.constants import LINUX_LOG_FILE


class LogsPage(QWidget):
    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self._config = config
        self._setup_ui()
        self._load_entries()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._load_entries)
        self._timer.start(4000)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(14)

        # ── Encabezado ──
        header_row = QHBoxLayout()
        title = QLabel("Registros de Paquetes Rechazados")
        title.setObjectName("label_title")
        header_row.addWidget(title)
        header_row.addStretch()

        btn_refresh = QPushButton("Actualizar ahora")
        btn_refresh.setObjectName("btn_secondary")
        btn_refresh.clicked.connect(self._load_entries)
        header_row.addWidget(btn_refresh)

        btn_clear = QPushButton("Limpiar vista")
        btn_clear.setObjectName("btn_small")
        btn_clear.clicked.connect(lambda: self._text_area.setPlainText(""))
        header_row.addWidget(btn_clear)

        layout.addLayout(header_row)

        # ── Info del archivo ──
        log_file = self._config.get("log_file", LINUX_LOG_FILE)
        info_card = QFrame()
        info_card.setObjectName("card")
        info_layout = QHBoxLayout(info_card)
        info_layout.setContentsMargins(16, 10, 16, 10)

        info_lbl = QLabel(
            f"Los paquetes rechazados por las reglas iptables se registran en:<br>"
            f"<span style='color:#22c55e; font-family:monospace;'>{log_file}</span><br>"
            "<span style='color:#6b7585; font-size:11px;'>"
            "Prefijo del log: <b>PM-DROP</b> (generado por la cadena PM_REJECT)"
            "</span>"
        )
        info_lbl.setWordWrap(True)
        info_lbl.setObjectName("label_secondary")
        info_layout.addWidget(info_lbl)

        self._exists_lbl = QLabel("")
        self._exists_lbl.setObjectName("label_secondary")
        info_layout.addStretch()
        info_layout.addWidget(self._exists_lbl)

        layout.addWidget(info_card)

        # ── Area de texto (terminal look) ──
        self._text_area = QTextEdit()
        self._text_area.setReadOnly(True)
        self._text_area.setPlaceholderText(
            "Esperando paquetes rechazados...\n\n"
            "Cuando las reglas estén aplicadas y un cliente intente acceder\n"
            "a un sitio bloqueado, aparecerá el log aquí."
        )
        layout.addWidget(self._text_area, stretch=1)

        # ── Instrucciones (para cuando el archivo no existe) ──
        self._hint_lbl = QLabel(
            "Tip: Si el archivo no existe todavía, asegurate de que rsyslog esté configurado "
            "para redirigir los logs de iptables. El script <b>run.sh</b> lo configura automáticamente."
        )
        self._hint_lbl.setObjectName("label_secondary")
        self._hint_lbl.setWordWrap(True)
        self._hint_lbl.setVisible(False)
        layout.addWidget(self._hint_lbl)

    def _load_entries(self):
        log_file = self._config.get("log_file", LINUX_LOG_FILE)

        if not os.path.exists(log_file):
            self._text_area.setPlainText(
                f"[!] El archivo {log_file} no existe todavía.\n\n"
                "Esto es normal si:\n"
                "  • Las reglas aún no han sido aplicadas.\n"
                "  • Ningún cliente ha intentado acceder a sitios bloqueados.\n"
                "  • rsyslog no está configurado (ejecuta run.sh primero).\n\n"
                "Una vez que apliques las reglas y haya intentos de conexión bloqueados,\n"
                "los registros aparecerán aquí automáticamente."
            )
            self._exists_lbl.setText("● Sin archivo")
            self._exists_lbl.setStyleSheet("color: #f59e0b; font-size: 11px; background: transparent;")
            self._hint_lbl.setVisible(True)
            return

        self._hint_lbl.setVisible(False)
        try:
            with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
                # Filtrar solo líneas que contienen PM-DROP
                pm_lines = [l for l in lines if "PM-DROP" in l] or lines
                tail = pm_lines[-150:]
                self._text_area.setPlainText("".join(tail))
                scrollbar = self._text_area.verticalScrollBar()
                scrollbar.setValue(scrollbar.maximum())

            count = sum(1 for l in lines if "PM-DROP" in l)
            self._exists_lbl.setText(f"● {count} paquetes rechazados")
            self._exists_lbl.setStyleSheet("color: #ef4444; font-size: 11px; background: transparent;")
        except Exception as e:
            self._text_area.setPlainText(f"Error al leer el archivo:\n{e}")

    def update_config(self, config: dict):
        self._config = config
