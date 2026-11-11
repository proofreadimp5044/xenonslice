#!/usr/bin/env python3
"""XenonSlice - ayudante con privilegios.

Escribe y borra los drop-ins de /etc/systemd/system que aislan los slices del
sistema en los hilos 12-15. No reinicia nada: systemd aplica los cpusets al
siguiente arranque de los servicios/slices (por eso conviene reiniciar sesión
o el equipo tras aplicar/revertir).

Uso (lo invoca core.elevar, no a mano):
    helper.py aplicar
    helper.py revertir [--heredados]
"""
import sys
from pathlib import Path

MARCA = "# gestionado-por: xenonslice"
MARCAS = ("gestionado-por: xenonslice", "gestionado-por: zonas.py")
ETC = Path("/etc/systemd/system")

SISTEMA = "12-15"
TODOS = "0-15"

# (ruta, sección, cpus)
ITEMS = (
    (ETC / "system.slice.d" / "xenonslice.conf", "Slice", SISTEMA),
    (ETC / "init.scope.d" / "xenonslice.conf", "Scope", SISTEMA),
    (ETC / "user.slice.d" / "xenonslice.conf", "Slice", TODOS),
)

# Archivos antiguos (zonas.py / aplicar-aislamiento.sh) que se pueden limpiar.
HEREDADOS = (
    ETC / "system.slice.d" / "allowed-cpus.conf",
    ETC / "init.scope.d" / "allowed-cpus.conf",
    ETC / "user.slice.d" / "allowed-cpus.conf",
)


def _daemon_reload():
    import subprocess
    subprocess.run(["systemctl", "daemon-reload"], check=False)


def _tiene_marca(texto):
    return bool(texto) and any(m in texto for m in MARCAS)


def _borrar(ruta):
    if ruta.exists():
        ruta.unlink()
        return True
    return False


def aplicar():
    for ruta, seccion, cpus in ITEMS:
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(f"{MARCA}\n[{seccion}]\nAllowedCPUs={cpus}\n")
    _daemon_reload()
    print("Aplicado: system.slice e init.scope en 12-15; user.slice en 0-15.")


def revertir(heredados=False):
    borrados = 0
    for ruta, _, _ in ITEMS:
        if _borrar(ruta):
            borrados += 1
            try:
                ruta.parent.rmdir()
            except OSError:
                pass
    if heredados:
        for ruta in HEREDADOS:
            txt = ""
            try:
                txt = ruta.read_text()
            except OSError:
                continue
            if _tiene_marca(txt) or "AllowedCPUs" in txt:
                if _borrar(ruta):
                    borrados += 1
                    try:
                        ruta.parent.rmdir()
                    except OSError:
                        pass
    _daemon_reload()
    print(f"Revertido ({borrados} archivo(s) eliminado(s)).")


def main(argv):
    if not argv:
        print(__doc__, file=sys.stderr)
        return 2
    cmd, resto = argv[0], argv[1:]
    if cmd == "aplicar":
        aplicar()
        return 0
    if cmd == "revertir":
        revertir(heredados="--heredados" in resto)
        return 0
    print(f"Comando desconocido: {cmd}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))