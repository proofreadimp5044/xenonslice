#!/usr/bin/env bash
# Instalador de un solo paso para XenonSlice (doble clic o terminal).
set -uo pipefail

AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG="/tmp/xenonslice-instalar.log"
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

echo "== XenonSlice: instalación completa ==" | tee -a "$LOG"
echo

# 1) Instalar (pide sudo una vez)
if [[ $EUID -ne 0 ]]; then
    echo "Paso 1/2: instalando la app (se pedirá tu contraseña)…" | tee -a "$LOG"
    if ! sudo bash "$AQUI/install.sh" "$@" 2>&1 | tee -a "$LOG"; then
        error "falló la instalación (install.sh)."
    fi
else
    if ! bash "$AQUI/install.sh" "$@" 2>&1 | tee -a "$LOG"; then
        error "falló la instalación (install.sh)."
    fi
fi

# 2) Aplicar la configuración como usuario normal
echo | tee -a "$LOG"
if [[ $EUID -eq 0 ]]; then
    USUARIO="${SUDO_USER:-}"
    [[ -z "$USUARIO" ]] && error "ejecuta como usuario normal, no como root."
    echo "Paso 2/2: aplicando la configuración como $USUARIO…" | tee -a "$LOG"
    if ! sudo -u "$USUARIO" -H /usr/local/bin/xenonslice aplicar 2>&1 | tee -a "$LOG"; then
        echo
        echo "⚠ La app se instaló, pero «aplicar» falló." | tee -a "$LOG"
        echo "  Puedes reintentarlo con:  xenonslice aplicar" | tee -a "$LOG"
    fi
else
    echo "Paso 2/2: aplicando la configuración…" | tee -a "$LOG"
    if ! /usr/local/bin/xenonslice aplicar 2>&1 | tee -a "$LOG"; then
        echo
        echo "⚠ La app se instaló, pero «aplicar» falló." | tee -a "$LOG"
        echo "  Puedes reintentarlo con:  xenonslice aplicar" | tee -a "$LOG"
    fi
fi

echo | tee -a "$LOG"
echo "== Listo ==" | tee -a "$LOG"
echo "  xenonslice            abre la interfaz" | tee -a "$LOG"
echo "  xenonslice estado     comprueba el estado" | tee -a "$LOG"
echo "  xenonslice revertir   vuelve a 0-15" | tee -a "$LOG"
echo | tee -a "$LOG"
echo "Si el audio o Wine no toman los cambios, cierra sesión y vuelve a entrar." | tee -a "$LOG"
pausa