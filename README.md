# M-FIREWALL

Administrador gráfico de reglas **iptables** para Kali Linux.
Interfaz PySide6 (Python) con modo demostración en Windows.

**Integrantes:**
- Quezada Juarez Fabrizio
- Espinola Figueroa Manuel
- Sanchez Bonifaz Lucero

---

## Requisitos

| Sistema | Requisito |
|---|---|
| Kali Linux | Python 3.10+, iptables, ipset, arp-scan |
| Windows | Python 3.10+, PySide6 (solo demostración visual) |

---

## Instalación en Kali Linux (primera vez)

### Paso 1 — Clonar el repositorio

```bash
git clone https://github.com/davestinhast/proyecto-m-firewall.git
cd proyecto-m-firewall
```

### Paso 2 — Ejecutar el instalador

Instala todas las dependencias del sistema y Python automáticamente:

```bash
sudo ./scripts/install.sh
```

Esto hace:
- Instala `iptables`, `ipset`, `iptables-persistent`, `rsyslog`, `arp-scan`
- Crea el entorno virtual Python en `.venv/`
- Instala `PySide6`, `requests`, `dnspython`
- Crea los directorios `/opt/proyecto-m/` y `/var/log/proyecto-m/`
- Configura rsyslog para redirigir logs con prefijo `PM-DROP`
- Instala el servicio systemd para cargar reglas al arrancar

### Paso 3 — Lanzar la aplicación

```bash
./run.sh
```

El script detecta automáticamente si no eres root y pide la contraseña.
No necesitas escribir `sudo` manualmente.

---

## Uso en cualquier otra PC con Kali (sin instalar)

```bash
git clone https://github.com/davestinhast/proyecto-m-firewall.git
cd proyecto-m-firewall
sudo ./scripts/install.sh
./run.sh
```

Mismo proceso. El instalador hace todo.

---

## Actualizar cuando hay cambios en GitHub

```bash
git checkout -- run.sh
git pull
./run.sh
```

---

## Uso en Windows (modo demostración)

Solo para ver la interfaz. Las reglas iptables no se aplican.

```bash
pip install -r requirements.txt
python run.py
```

---

## Qué hace cada pantalla

### Inicio (Dashboard)
Muestra el estado del sistema en tiempo real: modo, IP detectada, interfaz,
disponibilidad de iptables y permisos. Incluye una lista de 7 pasos guiados
que indica cuáles están configurados y cuáles faltan. También muestra
estadísticas rápidas y los últimos paquetes rechazados.

### Bloqueo de sitios web
Activa o desactiva el bloqueo de Facebook, YouTube y Hotmail/Outlook.
La aplicación resuelve los dominios a IPs automáticamente y carga sets de **ipset**
(`PM_FACEBOOK`, `PM_YOUTUBE`, `PM_HOTMAIL`). Las reglas iptables referencian esos sets,
permitiendo actualizar las IPs bloqueadas sin recargar iptables (importante porque
los CDN de estos sitios cambian constantemente). Bloquea TCP 80 y TCP 443.

### Control cliente / servidor
Bloquea las conexiones nuevas que el cliente intenta iniciar hacia el servidor.
El servidor puede seguir iniciando conexiones hacia el cliente (unidireccional).
Usa estados iptables: bloquea `NEW`, permite `ESTABLISHED` y `RELATED`.

### Bloqueo por MAC
Escanea la red local con ARP para detectar todos los equipos conectados
(muestra IP, MAC, hostname, fabricante). Permite seleccionar un equipo
y bloquearlo por su dirección MAC. También permite agregar MACs manualmente.

### Límite de conexiones
Usa el módulo `connlimit` de iptables para limitar cuántas conexiones
simultáneas puede abrir una misma IP hacia un puerto específico.
Por defecto incluye perfiles para SSH (puerto 22), HTTP (80) y HTTPS (443).

### Registros
Muestra en tiempo real los paquetes rechazados que se guardan en
`/var/log/proyecto-m/iptables-rejected.log`.
Permite filtrar por IP, protocolo y motivo. Se actualiza cada 4 segundos.
Soporta exportar los registros a CSV.

### Copias de seguridad
Cada vez que se aplican reglas se crea una copia automática con fecha y hora.
Desde esta pantalla se puede restaurar cualquier versión anterior.

### Configuración
Define las interfaces de red WAN y LAN, la IP del servidor (Kali),
la red del cliente en formato CIDR, y las rutas de archivos personalizadas.

---

## Dónde se guardan las cosas

| Archivo | Descripción |
|---|---|
| `/opt/proyecto-m/rules/project_m.rules.v4` | Reglas iptables generadas |
| `/opt/proyecto-m/rules/backups/` | Copias de seguridad automáticas |
| `/opt/proyecto-m/config/project_m.json` | Configuración guardada |
| `/var/log/proyecto-m/iptables-rejected.log` | Log de paquetes rechazados |

---

## Aplicar reglas

Cuando todos los pasos del dashboard estén configurados, pulsa
**"Aplicar reglas"** en la barra inferior. La aplicación:

1. Resuelve los dominios bloqueados a IPs actuales
2. Carga los sets de **ipset** (`PM_FACEBOOK`, `PM_YOUTUBE`, `PM_HOTMAIL`) con esas IPs
3. Guarda el archivo ipset en `/opt/proyecto-m/rules/project_m.ipset`
4. Genera el archivo de reglas completo (con referencias a los sets, no IPs hardcodeadas)
5. Valida con `iptables-restore --test` sin aplicar nada
6. Crea una copia de seguridad de las reglas anteriores
7. Escribe el archivo en `/opt/proyecto-m/rules/project_m.rules.v4`
8. Aplica las reglas con `iptables-restore`

Para actualizar las IPs de los sitios bloqueados sin recargar iptables, usa el botón
**"Actualizar IPs bloqueadas"** en la pestaña de Sitios Web.

---

## Cadenas iptables creadas

| Cadena | Función |
|---|---|
| `PM_REJECT` | Registra con `PM-DROP` y rechaza el paquete |
| `PM_WEBBLOCK` | Bloquea IPs de Facebook, YouTube, Hotmail |
| `PM_MACBLOCK` | Bloquea por dirección MAC |
| `PM_CONNLIMIT` | Limita conexiones simultáneas por IP |
| `PM_CLISRV` | Bloquea conexiones NEW del cliente al servidor |
