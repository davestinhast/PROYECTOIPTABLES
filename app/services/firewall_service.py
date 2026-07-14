"""
Aplica, valida y restaura reglas iptables.

FLUJO DE APLICACIÓN:
  1. Resolver dominios → IPs (domain_service.resolve_all_domains)
  2. Aplicar ipset sets → PM_FACEBOOK, PM_YOUTUBE, PM_HOTMAIL (domain_service.apply_ipset)
  3. Generar archivo .rules.v4 con referencias a esos sets (rules_builder.build_rules)
  4. Validar con iptables-restore --test
  5. Escribir archivo personalizado en /opt/proyecto-m/rules/project_m.rules.v4
  6. Aplicar con iptables-restore
"""

import shutil
from datetime import datetime
from pathlib import Path
from app.core import command_runner, rules_builder
from app.core.platform_detector import get_mode
from app.constants import LINUX_RULES_FILE, LINUX_RULES_BACKUP_DIR, LINUX_IPSET_FILE


def validate_rules(rules_content: str) -> tuple[bool, str]:
    """Valida sin aplicar. Retorna (ok, mensaje)."""
    if get_mode() == "demo":
        return True, "Modo demostración — validación simulada correcta."
    rc, stdout, stderr = command_runner.run_iptables_restore(rules_content, dry_run=True)
    if rc == 0:
        return True, "Validación correcta."
    return False, stderr.strip() or "Error desconocido en iptables-restore --test"


def apply_rules(
    rules_content: str,
    rules_path: str = "",
    resolved: dict | None = None,
) -> tuple[bool, str]:
    """
    1. Activa ip_forward
    2. Aplica ipset sets (PM_FACEBOOK, PM_YOUTUBE, PM_HOTMAIL)
    3. Valida las reglas iptables
    4. Crea backup del archivo anterior
    5. Escribe el archivo personalizado en la ruta configurada
    6. Aplica con iptables-restore
    7. Retorna (ok, mensaje)

    Args:
        rules_content: Contenido del archivo .rules.v4
        rules_path:    Ruta donde guardar el archivo. Si está vacío usa LINUX_RULES_FILE.
        resolved:      Dict de IPs resueltas para cargar en ipset.
    """
    if get_mode() == "demo":
        return False, "Modo demostración — no se pueden aplicar reglas en Windows."

    # Determinar ruta de guardado
    target_path = rules_path.strip() if rules_path.strip() else LINUX_RULES_FILE

    # 1. Activar reenvío de paquetes IPv4 — necesario para FORWARD chain
    from app.core.platform_detector import enable_ip_forward
    enable_ip_forward()

    # 2. Aplicar ipset sets ANTES que iptables (las reglas los referencian)
    if resolved:
        from app.services.domain_service import apply_ipset, save_resolved_ips
        ipset_ok, ipset_msg = apply_ipset(resolved)
        if not ipset_ok:
            # No es fatal: el bloqueo por IPs no funcionará pero iptables carga igual
            pass
        else:
            # Guardar ipset file en disco para referencia
            try:
                from app.services.domain_service import build_ipset_file
                ipset_content = build_ipset_file(resolved)
                ipset_path = Path(LINUX_IPSET_FILE)
                ipset_path.parent.mkdir(parents=True, exist_ok=True)
                ipset_path.write_text(ipset_content, encoding="utf-8")
            except Exception:
                pass

    # 3. Validar
    ok, msg = validate_rules(rules_content)
    if not ok:
        return False, f"Validación fallida: {msg}"

    # 4. Backup del archivo anterior
    _create_backup(target_path)

    # 5. Escribir archivo personalizado
    try:
        p = Path(target_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(rules_content, encoding="utf-8")
    except Exception as e:
        return False, f"No se pudo escribir {target_path}: {e}"

    # 6. Aplicar
    rc, stdout, stderr = command_runner.run_iptables_restore(rules_content)
    if rc == 0:
        rule_count = rules_builder.get_rule_count(rules_content)
        return True, (
            f"Reglas aplicadas correctamente. "
            f"({rule_count} reglas en {target_path})"
        )
    return False, stderr.strip() or "Error al aplicar reglas."


def refresh_ipset(config: dict) -> tuple[bool, str]:
    """
    Actualiza los sets de ipset resolviendo los dominios de nuevo,
    SIN necesidad de recargar iptables.
    Útil para cuando las IPs de Facebook/YouTube/Hotmail cambian.
    """
    if get_mode() == "demo":
        return False, "Modo demostración."

    from app.services.domain_service import resolve_all_domains, apply_ipset
    blocked = config.get("blocked_domains", {})
    if not any(v.get("enabled", False) for v in blocked.values()):
        return False, "No hay sitios habilitados para actualizar."

    try:
        resolved = resolve_all_domains(blocked)
        ok, msg = apply_ipset(resolved)
        return ok, msg
    except Exception as e:
        return False, f"Error al actualizar IPs: {e}"


def restore_backup(backup_path: str) -> tuple[bool, str]:
    """Restaura un archivo de backup."""
    if get_mode() == "demo":
        return False, "Modo demostración."
    rc, stdout, stderr = command_runner.run_iptables_restore_file(backup_path)
    if rc == 0:
        return True, f"Restaurado desde {backup_path}"
    return False, stderr.strip()


def flush_all() -> tuple[bool, str]:
    """Elimina todas las reglas de todas las tablas de iptables (IPv4, IPv6 y nftables)."""
    if get_mode() == "demo":
        return False, "Modo demostración."

    # 1. Limpiar IPv4 (iptables)
    rc, _, err = command_runner.run_iptables(["-F"])
    if rc != 0:
        return False, err
    command_runner.run_iptables(["-X"])
    command_runner.run_iptables(["-t", "nat", "-F"])
    command_runner.run_iptables(["-t", "nat", "-X"])
    command_runner.run_iptables(["-t", "mangle", "-F"])
    command_runner.run_iptables(["-t", "mangle", "-X"])
    command_runner.run_iptables(["-P", "INPUT", "ACCEPT"])
    command_runner.run_iptables(["-P", "FORWARD", "ACCEPT"])
    command_runner.run_iptables(["-P", "OUTPUT", "ACCEPT"])

    # 2. Limpiar IPv6 (ip6tables)
    command_runner.run(["ip6tables", "-F"])
    command_runner.run(["ip6tables", "-X"])
    command_runner.run(["ip6tables", "-t", "nat", "-F"])
    command_runner.run(["ip6tables", "-t", "nat", "-X"])
    command_runner.run(["ip6tables", "-P", "INPUT", "ACCEPT"])
    command_runner.run(["ip6tables", "-P", "FORWARD", "ACCEPT"])
    command_runner.run(["ip6tables", "-P", "OUTPUT", "ACCEPT"])

    # 3. Vaciar nftables (por si hay reglas modernas de otros laboratorios)
    command_runner.run(["nft", "flush", "ruleset"])

    return True, "Todas las reglas del sistema (IPv4, IPv6 y nftables) han sido eliminadas."


def get_active_rules() -> tuple[bool, str]:
    """Retorna el listado actual de reglas iptables."""
    if get_mode() == "demo":
        return True, _demo_rules()
    rc, stdout, stderr = command_runner.run_iptables(["-L", "-n", "-v", "--line-numbers"])
    if rc == 0:
        return True, stdout
    return False, stderr


def list_backups(backup_dir: str = LINUX_RULES_BACKUP_DIR) -> list[dict]:
    """Lista copias de seguridad disponibles."""
    p = Path(backup_dir)
    if not p.exists():
        return []
    backups = []
    for f in sorted(p.glob("*.rules.v4"), reverse=True):
        stat = f.stat()
        content = f.read_text(errors="ignore")
        backups.append({
            "path": str(f),
            "name": f.name,
            "date": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
            "size": stat.st_size,
            "rule_count": rules_builder.get_rule_count(content),
        })
    return backups


def _create_backup(rules_path: str):
    p = Path(rules_path)
    if not p.exists():
        return
    backup_dir = Path(LINUX_RULES_BACKUP_DIR)
    backup_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = backup_dir / f"backup_{ts}.rules.v4"
    shutil.copy2(p, dest)


def _demo_rules() -> str:
    return """Chain INPUT (policy ACCEPT)
target     prot opt source               destination

Chain FORWARD (policy ACCEPT)
target     prot opt source               destination
PM_MACBLOCK  all  --  anywhere             anywhere
PM_CONNLIMIT all  --  anywhere             anywhere
PM_CLISRV  all  --  anywhere             anywhere
PM_WEBBLOCK all  --  anywhere             anywhere

Chain OUTPUT (policy ACCEPT)
target     prot opt source               destination
PM_WEBBLOCK all  --  anywhere             anywhere

Chain PM_REJECT (2 references)
LOG        all  --  anywhere             anywhere   LOG level warning prefix "PM-DROP "
DROP       all  --  anywhere             anywhere

Chain PM_WEBBLOCK (2 references)
target     prot opt source               destination
PM_REJECT  tcp  --  anywhere             anywhere   match-set PM_FACEBOOK dst tcp dpt:443
PM_REJECT  tcp  --  anywhere             anywhere   match-set PM_YOUTUBE dst tcp dpt:443
PM_REJECT  tcp  --  anywhere             anywhere   match-set PM_HOTMAIL dst tcp dpt:443

[MODO DEMOSTRACIÓN — reglas simuladas]"""
