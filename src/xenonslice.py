#!/usr/bin/env python3
"""XenonSlice - punto de entrada.

    xenonslice                     abre la interfaz
    xenonslice aplicar [--sin-audio] [--sin-easyeffects] [--sin-wine] [--reiniciar-audio] [--dry-run]
    xenonslice revertir [--heredados]
    xenonslice estado              muestra qué está configurado
    xenonslice topologia [--verificar]
    xenonslice apps                lista apps y su zona
    xenonslice --version
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import core  # noqa: E402


def _print_estado():
    for c in core.estado():
        icono = {"ok": "✔", "falta": "✘", "aviso": "•"}.get(c["estado"], "?")
        print(f"{icono} {c['nombre']}: {c['detalle']}")


def _print_topologia(verificar):
    t = core.detectar_topologia()
    print(f"Modelo: {t['modelo']}")
    print(f"Núcleos: {t['nucleos']}  Hilos: {t['hilos']}  Dominios L3: {t['l3']}")
    if t["ok"]:
        p = core.perfil()
        print(f"Compatible. Sistema: hilos {p['sistema']} · Usuario: hilos {p['usuario']}")
    else:
        print("No compatible:")
        for m in t["motivos"]:
            print(f"  - {m}")
    for a in t["avisos"]:
        print(f"Aviso: {a}")
    if verificar:
        return 0 if t["ok"] else 3
    return 0


def _print_apps():
    apps, _ = core.listar_apps()
    zonas = core.zonas()
    for a in apps:
        estado, _ = core.verificar(a)
        marca = {"ok": "✔", "falla": "✘"}.get(estado, " ")
        print(f"{marca} {a['nombre']:<40} {zonas[a['regla']]['etiqueta']}")
    return 0


def _lanzar_gui():
    import gui
    return gui.lanzar()


def main(argv):
    if not argv:
        return _lanzar_gui()
    cmd = argv[0]
    resto = argv[1:]

    if cmd in ("-h", "--help", "ayuda"):
        print(__doc__)
        return 0
    if cmd in ("--version", "version"):
        print(f"XenonSlice {core.VERSION}")
        return 0

    if cmd == "aplicar":
        pasos = ["audio", "easyeffects", "wine"]
        if "--sin-audio" in resto:
            pasos.remove("audio")
        if "--sin-easyeffects" in resto:
            pasos.remove("easyeffects")
        if "--sin-wine" in resto:
            pasos.remove("wine")
        if "--dry-run" in resto:
            print(core.vista_previa(pasos))
            return 0
        ok, msg = core.aplicar(pasos, reiniciar_audio="--reiniciar-audio" in resto)
        print(msg)
        return 0 if ok else 1

    if cmd == "revertir":
        ok, msg = core.revertir(heredados="--heredados" in resto)
        print(msg)
        return 0 if ok else 1

    if cmd == "estado":
        _print_estado()
        return 0

    if cmd == "topologia":
        return _print_topologia(verificar="--verificar" in resto)

    if cmd == "apps":
        return _print_apps()

    print(f"Comando desconocido: {cmd}\n\n{__doc__}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))