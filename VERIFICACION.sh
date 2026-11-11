echo "== Estructura =="
find . -type f | sort

echo
echo "== Sintaxis Python =="
for f in src/*.py; do
    python3 -m py_compile "$f" && echo "OK  $f" || echo "FALLA  $f"
done

echo
echo "== Sintaxis bash =="
bash -n install.sh && echo "OK  install.sh"

echo
echo "== ¿core.py completo? =="
tail -n 5 src/core.py
wc -l src/core.py