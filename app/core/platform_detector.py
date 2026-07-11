"""
Detecta si la app corre en Linux (modo admin) o Windows (modo demo).
"""

import platform
import shutil
import sys
import os


def is_linux() -> bool:
    return platform.system() == "Linux"


def is_windows() -> bool:
    return platform.system() == "Windows"


def is_kali() -> bool:
    if not is_linux():
        return False
    try:
        with open("/etc/os-release") as f:
            content = f.read().lower()
            return "kali" in content
    except Exception:
        return False


def has_iptables() -> bool:
    return shutil.which("iptables") is not None


def has_ipset() -> bool:
    return shutil.which("ipset") is not None


def is_root() -> bool:
    if is_windows():
        return False
    return os.geteuid() == 0


def get_mode() -> str:
    """
    Retorna:
      'admin'  → Linux + iptables disponible
      'demo'   → Windows o sin iptables
    """
    if is_linux() and has_iptables():
        return "admin"
    return "demo"


def has_ip_forward() -> bool:
    """Verifica si el reenvío de paquetes IPv4 está activo."""
    try:
        with open("/proc/sys/net/ipv4/ip_forward") as f:
            return f.read().strip() == "1"
    except Exception:
        return False


def enable_ip_forward() -> bool:
    """Activa ip_forward en tiempo de ejecución y de forma persistente."""
    try:
        with open("/proc/sys/net/ipv4/ip_forward", "w") as f:
            f.write("1\n")
        # Persistir en sysctl.conf si no está ya
        sysctl_line = "net.ipv4.ip_forward = 1"
        try:
            with open("/etc/sysctl.conf", "r") as f:
                content = f.read()
            if sysctl_line not in content:
                with open("/etc/sysctl.conf", "a") as f:
                    f.write(f"\n# M-FIREWALL\n{sysctl_line}\n")
        except Exception:
            pass
        return True
    except Exception:
        return False


def get_system_info() -> dict:
    return {
        "os": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "machine": platform.machine(),
        "is_kali": is_kali(),
        "has_iptables": has_iptables(),
        "has_ipset": has_ipset(),
        "is_root": is_root(),
        "ip_forward": has_ip_forward() if is_linux() else False,
        "mode": get_mode(),
        "python": sys.version.split()[0],
    }
