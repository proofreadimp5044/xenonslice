#!/usr/bin/env bash
# Instalador local de XenonSlice (desde los archivos de esta carpeta).
#   ./install.sh                instala
#   ./install.sh --forzar       instala aunque la topología no sea compatible
#   ./install.sh -y             responde sí a instalar dependencias y no al acceso directo
#   ./install.sh --desinstalar  elimina XenonSlice (no revierte la configuración aplicada)
set -euo pipefail

AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DESTINO="${XS_DESTINO:-/opt/xenonslice}"
BIN="${XS_BIN:-/usr/local/bin}"
APPS="${XS_APPS:-/usr/share/applications}"

FORZAR=0; SI=0; DESINSTALAR=0
for a in "$@"; do
    case "$a" in
        --forzar) FORZAR=1 ;;
        -y) SI=1 ;;
        --desinstalar) DESINSTALAR=1 ;;
        *) echo "Opción desconocida: $a" >&2; exit 1 ;;
    esac
done

if [[ $EUID -ne 0 ]]; then
    echo "Se necesitan permisos de administrador para instalar en $DESTINO."
    exec sudo bash "${BASH_SOURCE[0]}" "$@"
fi

si_no() {
    local def="${2:-n}" r
    if [[ $SI -eq 1 ]]; then [[ "$def" == "s" ]]; return; fi
    if [[ "$def" == "s" ]]; then read -rp "$1 [S/n] " r; [[ -z "$r" || "$r" =~ ^[sSyY]$ ]]
    else read -rp "$1 [s/N] " r; [[ "$r" =~ ^[sSyY]$ ]]; fi
}

USUARIO="${SUDO_USER:-}"
HOME_USUARIO=""
[[ -n "$USUARIO" ]] && HOME_USUARIO="$(getent passwd "$USUARIO" | cut -d: -f6)"

escritorio() {
    local d=""
    [[ -n "$USUARIO" ]] && d="$(sudo -u "$USUARIO" xdg-user-dir DESKTOP 2>/dev/null || true)"
    [[ -z "$d" && -n "$HOME_USUARIO" ]] && d="$HOME_USUARIO/Desktop"
    echo "$d"
}

if [[ $DESINSTALAR -eq 1 ]]; then
    echo "Esto elimina XenonSlice de $DESTINO."
    echo "NO revierte la configuración aplicada: si quieres volver a 0-15, ejecuta antes «xenonslice revertir»."
    if [[ $SI -ne 1 ]]; then read -rp "¿Continuar? [s/N] " r; [[ "$r" =~ ^[sSyY]$ ]] || { echo "Cancelado."; exit 1; }; fi
    rm -rf "$DESTINO"
    rm -f "$BIN/xenonslice" "$APPS/xenonslice.desktop"
    if [[ "$(readlink "$BIN/xenon" 2>/dev/null || true)" == "$BIN/xenonslice" ]]; then rm -f "$BIN/xenon"; fi
    D="$(escritorio)"
    [[ -n "$D" ]] && rm -f "$D/xenonslice.desktop"
    echo "XenonSlice desinstalado."
    exit 0
fi

echo "== 1/5 Comprobando el equipo"
command -v python3 >/dev/null || { echo "Falta python3." >&2; exit 1; }
[[ -f "$AQUI/src/xenonslice.py" ]] || { echo "No encuentro src/xenonslice.py junto al instalador." >&2; exit 1; }
[[ -f "$AQUI/src/helper.py" ]] || { echo "No encuentro src/helper.py junto al instalador." >&2; exit 1; }
if ! python3 "$AQUI/src/xenonslice.py" topologia --verificar; then
    if [[ $FORZAR -eq 1 ]]; then
        echo "Continuando por --forzar (sin garantías)."
    else
        echo
        echo "Instalación cancelada: este equipo no cumple los requisitos (arriba está el motivo)."
        echo "Si aun así quieres instalarlo, usa --forzar."
        exit 3
    fi
fi

echo "== 2/5 Interfaz gráfica (Qt)"
if python3 -c "import PyQt6.QtWidgets" 2>/dev/null || python3 -c "import PySide6.QtWidgets" 2>/dev/null; then
    echo "Qt para Python: disponible."
elif command -v pacman >/dev/null; then
    if si_no "Falta Qt para la interfaz. ¿Instalar python-pyqt6 con pacman?" s; then
        pacman -S --needed --noconfirm python-pyqt6
    else
        echo "AVISO: sin Qt la interfaz no abrirá; la línea de comandos funciona igual."
    fi
else
    echo "AVISO: instala PyQt6 o PySide6 de tu distribución para usar la interfaz."
fi

echo "== 3/5 Copiando archivos a $DESTINO"
rm -rf "$DESTINO"
install -d -m 755 "$DESTINO" "$DESTINO/src" "$DESTINO/data"
install -m 644 "$AQUI"/src/*.py "$DESTINO/src/"
chmod 755 "$DESTINO/src/xenonslice.py" "$DESTINO/src/helper.py"
install -m 644 "$AQUI"/data/* "$DESTINO/data/"
install -m 755 "$AQUI/install.sh" "$DESTINO/install.sh"
[[ -f "$AQUI/README.md" ]] && install -m 644 "$AQUI/README.md" "$DESTINO/README.md"
chown -R root:root "$DESTINO"

echo "== 4/5 Comando y entrada del menú"
install -d -m 755 "$BIN" "$APPS"
printf '#!/bin/sh\nexec %s %s/src/xenonslice.py "$@"\n' "$(command -v python3)" "$DESTINO" > "$BIN/xenonslice"
chmod 755 "$BIN/xenonslice"
if [[ "$(readlink "$BIN/xenon" 2>/dev/null || true)" == "$BIN/xenonslice" ]]; then
    echo "Alias «xenon» ya existente (es de XenonSlice)."
elif [[ ! -e "$BIN/xenon" ]] && ! command -v xenon >/dev/null 2>&1; then
    ln -s "$BIN/xenonslice" "$BIN/xenon"
    echo "Alias «xenon» creado."
else
    echo "Ya existe un comando «xenon» distinto: no se crea el alias (usa «xenonslice»)."
fi
install -m 644 "$AQUI/data/xenonslice.desktop" "$APPS/xenonslice.desktop"
command -v update-desktop-database >/dev/null && update-desktop-database "$APPS" 2>/dev/null || true

echo "== 5/5 Acceso directo en el escritorio"
if [[ -n "$USUARIO" ]] && si_no "¿Crear un acceso directo en el escritorio?" n; then
    D="$(escritorio)"
    mkdir -p "$D"
    install -o "$USUARIO" -m 755 "$AQUI/data/xenonslice.desktop" "$D/xenonslice.desktop"
    echo "Creado en $D"
else
    echo "Omitido."
fi

echo
echo "Listo. XenonSlice no ha cambiado nada de tu sistema todavía."
echo "  xenonslice            abre la interfaz"
echo "  xenonslice aplicar    aplica la configuración (con vista previa)"
echo "  xenonslice estado     comprueba qué está configurado"