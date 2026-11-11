"""XenonSlice - núcleo: topología, plan de configuración, estado y reglas por app.

Sin dependencias de interfaz. Lo usan la línea de comandos, el ayudante con
privilegios (helper.py) y la ventana (gui.py).
"""
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

VERSION = "0.1.0"
AQUI = Path(__file__).resolve().parent

MARCA = "# gestionado-por: xenonslice"
MARCAS = ("gestionado-por: xenonslice", "gestionado-por: zonas.py")
ARCHIVO = "xenonslice.conf"
ARCHIVO_APP = "zona.conf"
RESERVADOS = 2

HOME = Path.home()
UID = os.getuid()
SYSFS = Path(os.environ.get("XS_SYSFS", "/sys/devices/system/cpu"))
CGROOT = Path(os.environ.get("XS_CGROOT", "/sys/fs/cgroup"))
ETC_SYSTEMD = Path(os.environ.get("XS_ETC", "/etc/systemd/system"))
CPUINFO = Path(os.environ.get("XS_CPUINFO", "/proc/cpuinfo"))
UNIT_DIR = HOME / ".config/systemd/user"
ENV_DIR = HOME / ".config/environment.d"
AUTOSTART = HOME / ".config/autostart/com.github.wwmm.easyeffects.desktop"
CONF_DIR = HOME / ".config/xenonslice"
UBASE = CGROOT / f"user.slice/user-{UID}.slice/user@{UID}.service"
SERVICIOS_AUDIO = ("pipewire", "pipewire-pulse", "wireplumber")
STEAM_FLATPAK = "com.valvesoftware.Steam"


# ----------------------------------------------------------------------------
# Utilidades
# ----------------------------------------------------------------------------
def run(cmd, timeout=15):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout, r.stderr
    except (OSError, subprocess.TimeoutExpired) as e:
        return 127, "", str(e)


def read(path, default=None):
    try:
        return Path(path).read_text().strip()
    except OSError:
        return default


def tiene_marca(texto):
    return bool(texto) and any(m in texto for m in MARCAS)


def parse_cpus(texto):
    cpus = set()
    for parte in (texto or "").strip().split(","):
        if not parte:
            continue
        if "-" in parte:
            a, b = parte.split("-")
            cpus.update(range(int(a), int(b) + 1))
        else:
            cpus.add(int(parte))
    return cpus


def unescape(s):
    return re.sub(r"\\x([0-9a-fA-F]{2})", lambda m: chr(int(m.group(1), 16)), s)


# ----------------------------------------------------------------------------
# Topología y perfil
# ----------------------------------------------------------------------------
def detectar_topologia():
    t = {"ok": False, "motivos": [], "avisos": [], "modelo": "desconocido",
         "hilos": 0, "nucleos": 0, "l3": 0, "ranking": {}}
    info = read(CPUINFO, "") or ""
    m = re.search(r"model name\s*:\s*(.+)", info)
    if m:
        t["modelo"] = m.group(1).strip()
    v = re.search(r"vendor_id\s*:\s*(\S+)", info)
    if not v or v.group(1) != "AuthenticAMD":
        t["motivos"].append("El procesador no es AMD.")

    online = parse_cpus(read(SYSFS / "online", ""))
    t["hilos"] = len(online)
    if len(online) != 16:
        t["motivos"].append(f"Se necesitan exactamente 16 hilos (8 núcleos con SMT); este equipo tiene {len(online)}.")
    if read(SYSFS / "smt/active") != "1":
        t["motivos"].append("SMT está desactivado.")

    grupos = set()
    for c in online:
        s = read(SYSFS / f"cpu{c}/topology/thread_siblings_list")
        if s:
            grupos.add(frozenset(parse_cpus(s)))
    t["nucleos"] = len(grupos)
    esperados = {frozenset({2 * k, 2 * k + 1}) for k in range(8)}
    if len(online) == 16 and grupos != esperados:
        t["motivos"].append("Los hilos hermanos de cada núcleo no son contiguos (0-1, 2-3, ...); "
                            "XenonSlice todavía no cubre esa numeración.")

    dominios = set()
    for c in online:
        for idx in (SYSFS / f"cpu{c}/cache").glob("index*"):
            if read(idx / "level") == "3":
                dominios.add(read(idx / "shared_cpu_list"))
    t["l3"] = len(dominios)
    if len(dominios) > 1:
        t["motivos"].append(f"Hay {len(dominios)} dominios de caché L3 (varios chiplets); solo se soporta un chip.")
    elif not dominios:
        t["avisos"].append("No pude leer la caché L3, así que no se pudo comprobar que sea un solo chip.")

    freqs = []
    for c in online:
        x = read(SYSFS / f"cpu{c}/cpufreq/cpuinfo_max_freq")
        if x and x.isdigit():
            freqs.append(int(x))
    if freqs and max(freqs) / max(1, min(freqs)) > 1.2:
        t["avisos"].append("Los núcleos tienen frecuencias máximas muy distintas: podrían ser núcleos mixtos, "
                           "que XenonSlice no ha probado.")

    for c in sorted(online):
        if c % 2 == 0:
            r = read(SYSFS / f"cpu{c}/cpufreq/amd_pstate_prefcore_ranking")
            if r and r.isdigit():
                t["ranking"][c // 2] = int(r)

    t["ok"] = not t["motivos"]
    return t


def perfil():
    ini = 16 - RESERVADOS * 2
    usuario = f"0-{ini - 1}"                       # "0-11"
    hilos = ",".join(str(c) for c in range(ini))   # "0,1,2,...,11"
    return {"sistema": f"{ini}-15", "usuario": usuario, "todos": "0-15",
            "wine": f"{ini}:{hilos}", "reservados": RESERVADOS}


def zonas():
    p = perfil()
    return {
        "predeterminada": {"etiqueta": f"Predeterminada ({p['usuario']})", "slice": None, "cpus": p["usuario"]},
        "sistema": {"etiqueta": f"Sistema ({p['sistema']})", "slice": "background.slice", "cpus": p["sistema"]},
        "libre": {"etiqueta": f"Libre ({p['todos']})", "slice": "session.slice", "cpus": p["todos"]},
    }


# ----------------------------------------------------------------------------
# Plan: qué archivos se escriben
# ----------------------------------------------------------------------------
def _dropin(ruta, seccion, cpus, paso, ambito):
    return dict(paso=paso, ambito=ambito, ruta=ruta,
                contenido=f"{MARCA}\n[{seccion}]\nAllowedCPUs={cpus}\n")


def items_sistema(p):
    """Archivos que escribe el ayudante con privilegios (en /etc/systemd/system)."""
    return [
        _dropin(ETC_SYSTEMD / "system.slice.d" / ARCHIVO, "Slice", p["sistema"], "base", "sistema"),
        _dropin(ETC_SYSTEMD / "init.scope.d" / ARCHIVO, "Scope", p["sistema"], "base", "sistema"),
        _dropin(ETC_SYSTEMD / "user.slice.d" / ARCHIVO, "Slice", p["todos"], "base", "sistema"),
    ]


def _unidad_easyeffects(p):
    return (f"{MARCA}\n[Unit]\nDescription=EasyEffects\n"
            "After=pipewire.service wireplumber.service pipewire-pulse.service\n"
            "Wants=pipewire.service wireplumber.service\nPartOf=graphical-session.target\n\n"
            f"[Service]\nSlice=session.slice\nExecStart=/usr/bin/easyeffects --gapplication-service\n"
            f"AllowedCPUs={p['sistema']}\nCPUSchedulingPolicy=rr\nCPUSchedulingPriority=50\n"
            "Restart=on-failure\nRestartSec=2\n\n[Install]\nWantedBy=graphical-session.target\n")


def items_usuario(p, pasos):
    """Archivos que escribe el usuario, sin privilegios."""
    it = [
        _dropin(UNIT_DIR / "app.slice.d" / ARCHIVO, "Slice", p["usuario"], "base", "usuario"),
        _dropin(UNIT_DIR / "background.slice.d" / ARCHIVO, "Slice", p["sistema"], "base", "usuario"),
    ]
    if "audio" in pasos:
        for s in SERVICIOS_AUDIO:
            it.append(_dropin(UNIT_DIR / f"{s}.service.d" / ARCHIVO, "Service", p["sistema"], "audio", "usuario"))
    if "easyeffects" in pasos:
        it.append(dict(paso="easyeffects", ambito="usuario", ruta=UNIT_DIR / "easyeffects.service",
                       contenido=_unidad_easyeffects(p)))
        it.append(dict(paso="easyeffects", ambito="usuario", ruta=AUTOSTART, respaldo=True,
                       contenido=f"{MARCA}\n[Desktop Entry]\nType=Application\nName=EasyEffects\nHidden=true\n"))
    if "wine" in pasos:
        it.append(dict(paso="wine", ambito="usuario", ruta=ENV_DIR / ARCHIVO,
                       contenido=f"{MARCA}\nWINE_CPU_TOPOLOGY={p['wine']}\n"))
    return it


def vista_previa(pasos=("audio", "easyeffects", "wine")):
    t = detectar_topologia()
    if not t["ok"]:
        return "No se puede aplicar:\n- " + "\n- ".join(t["motivos"])
    p = perfil()
    pasos = set(pasos)
    if "easyeffects" in pasos and not shutil.which("easyeffects"):
        pasos.discard("easyeffects")
    out = [f"Perfil: sistema = hilos {p['sistema']} ({p['reservados']} núcleos), "
           f"usuario = hilos {p['usuario']}, WINE_CPU_TOPOLOGY = {p['wine']}", ""]
    for titulo, items in (("Con privilegios (se pedirá tu contraseña)", items_sistema(p)),
                          ("Sin privilegios (en tu carpeta personal)", items_usuario(p, pasos))):
        out.append(f"== {titulo}")
        for i in items:
            out.append(f"--- {i['ruta']}")
            out.append("".join(f"    {l}\n" for l in i["contenido"].splitlines() if not l.startswith("# gestionado")).rstrip())
        out.append("")
    out.append("No se reinicia nada: el audio, EasyEffects y Wine toman los cambios al reiniciar la sesión "
               "(o con --reiniciar-audio).")
    return "\n".join(out)


# ----------------------------------------------------------------------------
# Aplicar / revertir
# ----------------------------------------------------------------------------
def elevar(argumentos):
    """Ejecuta el ayudante con privilegios (pkexec en la copia instalada, sudo en otro caso)."""
    helper = AQUI / "helper.py"
    base = [sys.executable, str(helper)] + list(argumentos)
    if os.geteuid() == 0:
        cmd = base
    elif str(helper).startswith("/opt/") and shutil.which("pkexec") and \
            (os.environ.get("WAYLAND_DISPLAY") or os.environ.get("DISPLAY")):
        cmd = ["pkexec"] + base
    elif shutil.which("sudo"):
        cmd = ["sudo"] + base
    else:
        return 127, "No encuentro pkexec ni sudo."
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    except (OSError, subprocess.TimeoutExpired) as e:
        return 127, str(e)
    return r.returncode, (r.stdout + r.stderr).strip()


def _escribir(item):
    ruta = item["ruta"]
    ruta.parent.mkdir(parents=True, exist_ok=True)
    if item.get("respaldo"):
        _respaldar_autostart(ruta)
    ruta.write_text(item["contenido"])


def _respaldar_autostart(ruta):
    CONF_DIR.mkdir(parents=True, exist_ok=True)
    bak, nada = CONF_DIR / "easyeffects-autostart.bak", CONF_DIR / "easyeffects-autostart.none"
    if bak.exists() or nada.exists():
        return
    actual = read(ruta)
    if actual is None:
        nada.touch()
    elif tiene_marca(actual):
        return
    elif "Hidden=true" in actual:
        # ya estaba anulado por un script anterior: usa su respaldo si existe
        for viejo in (HOME / ".local/share/cpu-isolation/easyeffects-autostart.desktop.bak",
                      HOME / "easyeffects-autostart.desktop.bak"):
            if viejo.exists():
                shutil.copy(viejo, bak)
                return
    else:
        shutil.copy(ruta, bak)


def _flatpak_steam():
    return shutil.which("flatpak") and run(["flatpak", "info", STEAM_FLATPAK])[0] == 0


def aplicar(pasos=("audio", "easyeffects", "wine"), reiniciar_audio=False):
    """Devuelve (ok, mensaje)."""
    t = detectar_topologia()
    if not t["ok"]:
        return False, "No se puede aplicar:\n- " + "\n- ".join(t["motivos"])
    p = perfil()
    pasos = set(pasos)
    log = []
    if "easyeffects" in pasos and not shutil.which("easyeffects"):
        pasos.discard("easyeffects")
        log.append("EasyEffects no está instalado: se omite ese paso.")

    todos = items_usuario(p, pasos)
    # Orden: primero los hijos, el padre (user.slice) al final.
    for i in [x for x in todos if x["paso"] == "base"]:
        _escribir(i)
    run(["systemctl", "--user", "daemon-reload"])
    rc, out = elevar(["aplicar"])
    if rc != 0:
        return False, "\n".join(log + ["Falló la parte con privilegios:", out])
    for i in [x for x in todos if x["paso"] != "base"]:
        _escribir(i)
    run(["systemctl", "--user", "daemon-reload"])
    if "easyeffects" in pasos:
        run(["systemctl", "--user", "enable", "easyeffects.service"])
    if "wine" in pasos and _flatpak_steam():
        run(["flatpak", "override", "--user", f"--env=WINE_CPU_TOPOLOGY={p['wine']}", STEAM_FLATPAK])
        log.append("Steam (flatpak): variable de Wine añadida.")
    if reiniciar_audio:
        _reiniciar_audio("easyeffects" in pasos)
        log.append("Audio reiniciado.")
    else:
        log.append("Cierra sesión y vuelve a entrar (o usa «reiniciar audio») para que lo tomen el audio, "
                   "EasyEffects y Wine.")
    log.insert(0, "Configuración aplicada.")
    return True, "\n".join(log)


def _reiniciar_audio(con_easyeffects):
    run(["systemctl", "--user", "stop", "app-com.github.wwmm.easyeffects@*.service"])
    run(["systemctl", "--user", "restart", "pipewire.service", "pipewire-pulse.service", "wireplumber.service"])
    if con_easyeffects:
        run(["systemctl", "--user", "restart", "easyeffects.service"])


reiniciar_audio = _reiniciar_audio


def _borrar_si_marcado(ruta):
    txt = read(ruta)
    if txt is not None and tiene_marca(txt):
        ruta.unlink()
        if ruta.parent.name.endswith(".d"):
            try:
                ruta.parent.rmdir()
            except OSError:
                pass
        return True
    return False


def revertir(heredados=False):
    """Deshace lo aplicado. Con heredados=True quita también los archivos de configuraciones anteriores."""
    p = perfil()
    run(["systemctl", "--user", "disable", "--now", "easyeffects.service"])
    for i in items_usuario(p, ("audio", "easyeffects", "wine")):
        if i["ruta"] == AUTOSTART:
            continue
        _borrar_si_marcado(i["ruta"])
    # Autostart de EasyEffects: restaurar el original
    bak, nada = CONF_DIR / "easyeffects-autostart.bak", CONF_DIR / "easyeffects-autostart.none"
    actual = read(AUTOSTART)
    if bak.exists():
        if actual is None or tiene_marca(actual) or "Hidden=true" in actual:
            shutil.copy(bak, AUTOSTART)
        bak.unlink()
    elif nada.exists():
        _borrar_si_marcado(AUTOSTART)
        nada.unlink()
    if _flatpak_steam():
        run(["flatpak", "override", "--user", "--unset-env=WINE_CPU_TOPOLOGY", STEAM_FLATPAK])
    if heredados:
        for d in ("app.slice.d", "background.slice.d", "pipewire.service.d",
                  "pipewire-pulse.service.d", "wireplumber.service.d"):
            f = UNIT_DIR / d / "cpus.conf"
            if f.exists():
                f.unlink()
                try:
                    f.parent.rmdir()
                except OSError:
                    pass
    run(["systemctl", "--user", "daemon-reload"])
    rc, out = elevar(["revertir"] + (["--heredados"] if heredados else []))
    if rc != 0:
        return False, "Falló la parte con privilegios:\n" + out
    return True, "Revertido. Reinicia la sesión para que todo vuelva a 0-15."


# ----------------------------------------------------------------------------
# Estado
# ----------------------------------------------------------------------------
def _cpuset(nombre, grupo, ruta, esperado, requerido=True):
    val = read(ruta)
    if val is None:
        return dict(nombre=nombre, grupo=grupo, estado="falta" if requerido else "aviso",
                    detalle="no existe o no está activo")
    ok = parse_cpus(val) == parse_cpus(esperado)
    return dict(nombre=nombre, grupo=grupo, estado="ok" if ok else "falta",
                detalle=val if ok else f"{val} (esperado {esperado})")


def estado():
    p = perfil()
    r = [
        _cpuset("user.slice", "base", CGROOT / "user.slice/cpuset.cpus.effective", p["todos"]),
        _cpuset("system.slice", "base", CGROOT / "system.slice/cpuset.cpus.effective", p["sistema"]),
        _cpuset("init.scope", "base", CGROOT / "init.scope/cpuset.cpus.effective", p["sistema"]),
        _cpuset("app.slice (tu sesión)", "base", UBASE / "app.slice/cpuset.cpus.effective", p["usuario"]),
        _cpuset("background.slice (tu sesión)", "base", UBASE / "background.slice/cpuset.cpus.effective", p["sistema"]),
        _cpuset("session.slice (tu sesión)", "base", UBASE / "session.slice/cpuset.cpus.effective", p["todos"]),
    ]
    for s in SERVICIOS_AUDIO:
        r.append(_cpuset(f"{s} en {p['sistema']}", "audio",
                         UBASE / f"session.slice/{s}.service/cpuset.cpus.effective", p["sistema"], requerido=False))
    inst = shutil.which("easyeffects") is not None
    u = read(UNIT_DIR / "easyeffects.service")
    r.append(dict(nombre="EasyEffects como servicio propio", grupo="easyeffects",
                  estado="ok" if tiene_marca(u) else ("falta" if inst else "aviso"),
                  detalle="configurado" if tiene_marca(u) else ("no configurado" if inst else "EasyEffects no está instalado")))
    w = read(ENV_DIR / ARCHIVO)
    r.append(dict(nombre="WINE_CPU_TOPOLOGY", grupo="wine",
                  estado="ok" if tiene_marca(w) else "falta",
                  detalle=(w.splitlines()[-1] if tiene_marca(w) else "no configurada")))
    return r


# ----------------------------------------------------------------------------
# Apps: escaneo, reglas por app y verificación
# ----------------------------------------------------------------------------
def _parse_desktop(path):
    d, dentro = {}, False
    try:
        lineas = Path(path).read_text(errors="ignore").splitlines()
    except OSError:
        return d
    for linea in lineas:
        linea = linea.strip()
        if linea.startswith("["):
            dentro = linea == "[Desktop Entry]"
        elif dentro and "=" in linea and not linea.startswith("#"):
            k, v = linea.split("=", 1)
            d.setdefault(k, v)
    return d


def escanear_flatpak():
    rc, out, _ = run(["flatpak", "list", "--app", "--columns=application,name"])
    apps = []
    if rc == 0:
        for linea in out.splitlines():
            partes = linea.split("\t")
            if len(partes) >= 2 and partes[0]:
                apps.append(dict(tipo="flatpak", id=partes[0], nombre=partes[1], archivo=None))
    return apps


def escanear_nativas():
    apps = {}
    for base in (Path("/usr/share/applications"), HOME / ".local/share/applications"):
        if not base.is_dir():
            continue
        for f in base.rglob("*.desktop"):
            d = _parse_desktop(f)
            if d.get("Type") != "Application":
                continue
            if d.get("NoDisplay", "").lower() == "true" or d.get("Hidden", "").lower() == "true":
                continue
            if any(k.startswith("X-Flatpak") for k in d):
                continue
            ident = str(f.relative_to(base))[:-len(".desktop")].replace("/", "-")
            apps[ident] = dict(tipo="nativa", id=ident, nombre=d.get("Name", ident), archivo=str(f))
    return list(apps.values())


def clasificar(unidad):
    m = re.match(r"^app-flatpak-(.+)-\d+\.scope$", unidad)
    if m:
        return "flatpak", m.group(1), f"app-flatpak-{m.group(1)}-.scope.d"
    m = re.match(r"^app-(.+)@[^@]+\.service$", unidad)
    if m:
        return "nativa", unescape(m.group(1)), f"app-{m.group(1)}@.service.d"
    return "otra", unidad, None


def unidades_en_marcha():
    _, out, _ = run(["systemctl", "--user", "list-units", "--all", "--no-legend", "--plain",
                     "--no-pager", "app-*.service", "app-*.scope"])
    nombres = [p[0] for p in (l.split() for l in out.splitlines()) if len(p) >= 4 and p[2] == "active"]
    if not nombres:
        return []
    _, out, _ = run(["systemctl", "--user", "show", "--no-pager", "-p", "Id", "-p", "ControlGroup"] + nombres, 20)
    res = []
    for bloque in out.strip().split("\n\n"):
        kv = dict(l.split("=", 1) for l in bloque.splitlines() if "=" in l)
        uid, cg = kv.get("Id"), kv.get("ControlGroup", "")
        if not uid or not cg:
            continue
        cpus = read(CGROOT / cg.lstrip("/") / "cpuset.cpus.effective") or "?"
        tipo, app, dirname = clasificar(uid)
        res.append(dict(unidad=uid, tipo=tipo, app=app, dir=dirname, slice=Path(cg).parent.name, cpus=cpus))
    return res


def _dirs_candidatos(app):
    if app.get("unidades") and app["unidades"][0].get("dir"):
        return [app["unidades"][0]["dir"]]
    if app["tipo"] == "flatpak":
        return [f"app-flatpak-{app['id']}-.scope.d"]
    base = app["id"]
    variantes = [f"app-{base}@.service.d"]
    if "-" in base:
        variantes.append("app-" + base.replace("-", "\\x2d") + "@.service.d")
    return variantes


def leer_regla(app):
    for d in _dirs_candidatos(app):
        txt = read(UNIT_DIR / d / ARCHIVO_APP)
        if tiene_marca(txt):
            m = re.search(r"^Slice=(\S+)", txt, re.M)
            for clave, z in zonas().items():
                if z["slice"] and m and m.group(1) == z["slice"]:
                    return clave
    return "predeterminada"


def escribir_regla(app, zona, recargar=True):
    seccion = "Scope" if app["tipo"] == "flatpak" else "Service"
    z = zonas()[zona]
    for d in _dirs_candidatos(app):
        carpeta = UNIT_DIR / d
        archivo = carpeta / ARCHIVO_APP
        if zona == "predeterminada":
            if tiene_marca(read(archivo)):
                archivo.unlink()
                try:
                    carpeta.rmdir()
                except OSError:
                    pass
        else:
            carpeta.mkdir(parents=True, exist_ok=True)
            cpus = f"AllowedCPUs={z['cpus']}\n" if zona == "sistema" else ""
            archivo.write_text(f"{MARCA}\n[{seccion}]\nSlice={z['slice']}\n{cpus}")
    app["regla"] = zona
    if recargar:
        run(["systemctl", "--user", "daemon-reload"])


def verificar(app):
    us = app.get("unidades") or []
    if not us:
        return "—", "no está en marcha"
    permitido = parse_cpus(zonas()[app["regla"]]["cpus"])
    real = ", ".join(sorted({u["cpus"] for u in us}))
    if all(parse_cpus(u["cpus"]) <= permitido for u in us):
        return "ok", f"coincide: corre en {real}"
    return "falla", f"corre en {real}: cierra y vuelve a abrir la app"


def listar_apps():
    apps = escanear_flatpak() + escanear_nativas()
    unidades = unidades_en_marcha()
    indice = {}
    for u in unidades:
        indice.setdefault((u["tipo"], u["app"]), []).append(u)
    for a in apps:
        a["unidades"] = indice.get((a["tipo"], a["id"]), [])
        a["regla"] = leer_regla(a)
    apps.sort(key=lambda a: (a["regla"] == "predeterminada", not a["unidades"], a["nombre"].lower()))
    return apps, unidades


def cerrar(app):
    if app["tipo"] == "flatpak":
        run(["flatpak", "kill", app["id"]])
    else:
        for u in app.get("unidades", []):
            run(["systemctl", "--user", "stop", u["unidad"]])


def abrir(app):
    import subprocess as sp
    if app["tipo"] == "flatpak":
        cmd = ["flatpak", "run", app["id"]]
    else:
        cmd = next((c for c in (["kioclient6", "exec", app["archivo"]], ["kioclient", "exec", app["archivo"]],
                                ["gtk-launch", app["id"]]) if shutil.which(c[0])), None)
        if cmd is None:
            return False
    sp.Popen(cmd, start_new_session=True, stdout=sp.DEVNULL, stderr=sp.DEVNULL)
    return True