#!/usr/bin/env bash
# Desinstalador de un solo paso para XenonSlice (doble clic o terminal).
# Revierte la configuración y quita la app.
set -uo pipefail

AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG="/tmp/xenonslice-desinstalar.log"
: > "$LOG"

pausa() {
    echo
    read -rp "Pulsa Enter para cerrar… " _ || true
}

error() {
    echo
    echo "✘ ERROR: $1"
    echo "  Log completo: $LOG"
    pausa
    exit 1
}

echo "== XenonSlice: desinstalación completa ==" | tee -a "$LOG"
echo "Se revertirá la configuración (todo vuelve a 0-15) y se quitará la app." | tee -a "$LOG"
echo | tee -a "$LOG"

if [[ $EUID -eq 0 ]]; then
    USUARIO="${SUDO_USER:-}"
    [[ -z "$USUARIO" ]] && error "ejecuta como usuario normal, no como root."
    ELEVAR=(sudo -u "$USUARIO" -H)
else
    ELEVAR=()
fi

# 1) Revertir configuración (si la app está instalada)
if [[ -x /usr/local/bin/xenonslice ]]; then
    echo "Paso 1/2: revirtiendo la configuración…" | tee -a "$LOG"
    if ! "${ELEVAR[@]}" /usr/local/bin/xenonslice revertir 2>&1 | tee -a "$LOG"; then
        echo "⚠ No se pudo revertir del todo. Sigue con la desinstalación." | tee -a "$LOG"
    fi
else
    echo "Paso 1/2: la app no está instalada; se omite revertir." | tee -a "$LOG"
fi

# 2) Desinstalar la app
echo | tee -a "$LOG"
echo "Paso 2/2: quitando la app (se pedirá tu contraseña)…" | tee -a "$LOG"
if [[ $EUID -ne 0 ]]; then
    if ! sudo bash "$AQUI/install.sh" --desinstalar 2>&1 | tee -a "$LOG"; then
        error "falló la desinstalación (install.sh --desinstalar)."
    fi
else
    if ! bash "$AQUI/install.sh" --desinstalar 2>&1 | tee -a "$LOG"; then
        error "falló la desinstalación (install.sh --desinstalar)."
    fi
fi

# Limpieza de restos propios
rm -rf "$HOME/.config/xenonslice" 2>/dev/null || true
rm -f /tmp/xenonslice-gui.log /tmp/xs.out /tmp/xs.err 2>/dev/null || true
pkill -f '/opt/xenonslice/src/xenonslice.py' 2>/dev/null || true

echo | tee -a "$LOG"
echo "== Listo ==" | tee -a "$LOG"
echo "La configuración de slices se ha revertido (todo a 0-15)." | tee -a "$LOG"
echo "Si el sistema sigue con los límites viejos, reinicia sesión o el equipo." | tee -a "$LOG"
pausa