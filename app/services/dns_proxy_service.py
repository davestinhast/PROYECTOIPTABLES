"""
Servidor DNS Proxy en segundo plano.
Intercepta peticiones de DNS redireccionadas y devuelve NXDOMAIN para dominios bloqueados.
Permite bloquear de forma 100% inmune a la aleatorización de mayúsculas (0x20 DNS casing).
"""

import socket
import threading
import logging
from app.constants import DNS_PROXY_PORT

logger = logging.getLogger("dns_proxy")
logging.basicConfig(level=logging.INFO)

_server_instance = None
_server_lock = threading.Lock()

class DNSProxyServer:
    def __init__(self, ip="0.0.0.0", port=DNS_PROXY_PORT, upstream="8.8.8.8"):
        self.ip = ip
        self.port = port
        self.upstream = upstream
        self.sock = None
        self.running = False
        self.thread = None
        self.config = {}

    def start(self, config: dict):
        with _server_lock:
            self.config = config
            if self.running:
                return
            try:
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                # Permitir reusar la dirección/puerto
                self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                self.sock.bind((self.ip, self.port))
                self.running = True
                self.thread = threading.Thread(target=self._listen, daemon=True)
                self.thread.start()
                logger.info(f"Servidor DNS Proxy iniciado en {self.ip}:{self.port} (Upstream: {self.upstream})")
            except Exception as e:
                logger.error(f"Error al iniciar DNS Proxy: {e}")

    def update_config(self, config: dict):
        self.config = config

    def stop(self):
        with _server_lock:
            self.running = False
            if self.sock:
                try:
                    self.sock.close()
                except Exception:
                    pass
                self.sock = None
            logger.info("Servidor DNS Proxy detenido.")

    def _listen(self):
        while self.running:
            try:
                data, addr = self.sock.recvfrom(2048)
                if not data:
                    continue
                # Ejecutar el manejo de cada query en un hilo ligero para no bloquear
                threading.Thread(target=self._handle_query, args=(data, addr), daemon=True).start()
            except Exception:
                break

    def _handle_query(self, data, addr):
        if len(data) < 12:
            return

        # Palabras clave a bloquear basadas en la configuración cargada
        blocked_domains = self.config.get("blocked_domains", {})
        keywords = []
        has_blocked = False

        for key, cfg in blocked_domains.items():
            if cfg.get("enabled", False):
                has_blocked = True
                if key == "facebook":
                    keywords += [b"facebook", b"fbcdn"]
                elif key == "youtube":
                    keywords += [b"youtu", b"googlevideo", b"ytimg"]
                elif key == "hotmail":
                    keywords += [b"hotmail", b"outlook", b"live.com"]

        # Si hay al menos un sitio bloqueado, siempre cegar servidores DoH y DNS alternativos
        if has_blocked:
            keywords += [b"dns.google", b"cloudflare-dns", b"dns.quad9", b"use-application-dns.net"]

        # Analizar payload DNS de forma case-insensitive
        payload_lower = data.lower()
        should_block = False
        for kw in keywords:
            if kw in payload_lower:
                should_block = True
                break

        if should_block:
            # Responder con un paquete DNS tipo NXDOMAIN (Código de error de nombre: RCODE = 3)
            # Transaction ID: bytes 0-1
            # Flags para Respuesta NXDOMAIN: 0x8183 (Response, standard query, recursion desired, recursion available, NXDOMAIN)
            # Questions Count: bytes 4-5
            # Answer Count: 0 (0x0000)
            # Authority Count: 0 (0x0000)
            # Additional Count: 0 (0x0000)
            tx_id = data[:2]
            qd_count = data[4:6]
            # Cabecera DNS NXDOMAIN + la pregunta original (data[12:])
            response = tx_id + b"\x81\x83" + qd_count + b"\x00\x00\x00\x00\x00\x00" + data[12:]
            try:
                self.sock.sendto(response, addr)
                logger.info(f"DNS Proxy: Interceptado y bloqueado dominio (NXDOMAIN) para {addr}")
            except Exception:
                pass
        else:
            # Reenviar al servidor DNS real aguas arriba (upstream)
            try:
                up_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                up_sock.settimeout(2.0)
                up_sock.sendto(data, (self.upstream, 53))
                resp, _ = up_sock.recvfrom(2048)
                self.sock.sendto(resp, addr)
                up_sock.close()
            except Exception:
                # Si falla el DNS real, simplemente ignorar
                pass

def get_dns_proxy() -> DNSProxyServer:
    global _server_instance
    with _server_lock:
        if _server_instance is None:
            _server_instance = DNSProxyServer()
        return _server_instance
