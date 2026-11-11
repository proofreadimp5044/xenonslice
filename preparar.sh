#!/usr/bin/env bash
# Da permisos de ejecución a los scripts y lanzadores de XenonSlice.
# Asume que la carpeta está en ~/xenonslice.
set -euo pipefail

AQUI="$HOME/xenonslice"

if [[ ! -d "$AQUI" ]]; then
    echo "No encuentro $AQUI."
    echo "Descomprime la carpeta XenonSlice en tu carpeta personal."
    read -rp "Pulsa Enter para cerrar… " _ || true
    exit 1
fi

cd "$AQUI"
chmod +x install.sh instalar-todo.sh desinstalar-todo.sh preparar.sh 2>/dev/null || true
for f in "Instalar XenonSlice.desktop" "Desinstalar XenonSlice.desktop" "Preparar permisos.desktop"; do
    [[ -f "$f" ]] && chmod +x "$f"
done

echo "Permisos aplicados en: $AQUI"
echo
echo "Siguiente paso: doble clic en «Instalar XenonSlice.desktop»"
echo "o ejecuta:  cd ~/xenonslice && ./instalar-todo.sh"
read -rp "Pulsa Enter para cerrar… " _ || true