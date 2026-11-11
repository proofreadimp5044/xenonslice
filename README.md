# XenonSlice

Replica la gestión de CPU de las consolas en CPUs AMD de 8 núcleos / 16 hilos
(Ryzen Z1 Extreme y similares). Reserva 2 núcleos (hilos 12-15) para el
sistema y el audio en tiempo real, y deja 6 (hilos 0-11) para juegos y apps.

## Por qué

En un chip monolítico de 8c/16t con una sola caché L3 compartida, dejar que
el sistema operativo reparta todo el trabajo entre los 16 hilos hace que:

- El audio en tiempo real compita con el juego por los mismos núcleos y
  aparezcan cortes o crujidos cuando la CPU se satura.
- El juego pierda 0.1 lows porque el planificador mueve hilos entre núcleos
  y estos compiten con procesos del sistema.
- El consumo suba innecesariamente al mantener todos los núcleos activos
  para cargas que no los necesitan.

XenonSlice replica lo que hacen las consolas: **separar el trabajo del juego
del trabajo del sistema**. Los núcleos 12-15 quedan para el sistema, el audio
(PipeWire, WirePlumber, EasyEffects) y las tareas de fondo. Los hilos 0-11
quedan para juegos y apps. Wine/Proton reciben `WINE_CPU_TOPOLOGY` para que
vean una topología coherente con esos 6 núcleos.

Objetivos:

- Mejorar los **0.1 lows** en juegos.
- Evitar **congelamientos** cuando la CPU está saturada.
- Reducir el **consumo de energía** al no despertar núcleos que no hacen falta.

## Cómo funciona

Usa los **cgroups v2** y los **slices de systemd** para asignar hilos a cada
grupo. No parchea el kernel ni instala módulos: solo escribe drop-ins de
systemd con `AllowedCPUs`.

| Slice | Hilos | Para qué |
|---|---|---|
| `app.slice` | 0-11 | Juegos y apps |
| `background.slice` | 12-15 | Tareas de fondo |
| `system.slice` / `init.scope` | 12-15 | Sistema |
| `session.slice` / `user.slice` | 0-15 | Sesión (sin restricción) |

Además:

- El audio (`pipewire`, `pipewire-pulse`, `wireplumber`) se mueve a 12-15.
- EasyEffects se configura como servicio propio en 12-15 con prioridad `rr`.
- `WINE_CPU_TOPOLOGY=12:0,1,2,3,4,5,6,7,8,9,10,11` para Wine/Proton (Steam
  flatpak incluido).
- Reglas por app: desde la GUI puedes asignar una app concreta a
  `Predeterminada (0-11)`, `Sistema (12-15)` o `Libre (0-15)`.

## Requisitos

- CPU AMD con exactamente 16 hilos (8 núcleos con SMT), un solo dominio L3.
  Probado en Ryzen Z1 Extreme. El instalador comprueba la topología y cancela
  si no es compatible.
- Linux con systemd.
- Plasma (probado en CachyOS). Para la interfaz: PyQt6 o PySide6.
- El usuario debe poder usar `sudo`.

## Instalación

**IMPORTANTE**: descomprime esta carpeta en tu carpeta personal.
Debe quedar exactamente en `~/xenonslice`.

1. Abre una terminal y ejecuta una vez:

   ```bash
   cd ~/xenonslice
   chmod +x preparar.sh
   ./preparar.sh

   ## Estado y compatibilidad

> **Experimental (v0.1.0).** Funciona y está probado en el hardware y el
> entorno que se indican abajo. En cualquier otro equipo, **no está probado**
> y el instalador puede rechazarlo.

**Probado en:**

- CPU: AMD Ryzen Z1 Extreme (8c/16t, un solo dominio de caché L3).
- Distro: CachyOS (Arch-based), systemd.
- Escritorio: Plasma 6 (Wayland) en escritorio y **Plasma Mobile**.
- Uso: aplicar, revertir, estado, GUI, CLI, reglas por app.

**No probado** (puede funcionar, pero no lo he probado):

- Otras CPUs AMD de 8c/16t de un solo chip (p. ej. 5800X3D, 5700X).
- Otras distros (Fedora, Debian, Ubuntu…).
- X11.
- Otros escritorios (GNOME, XFCE…).

**No soportado** (el instalador lo rechaza):

- CPUs con más o menos de 16 hilos.
- CPUs con varios dominios de caché L3 (varios chiplets: 5900X, 7900X…).
- CPUs sin SMT.
- Intel.

Si tu equipo no está en "Probado", el instalador cancelará. Puedes forzarlo
con `--forzar`, pero no hay garantía y puedes dejarte el sistema en un estado
que no esperas.

**Problema conocido:** en Plasma 6 + Wayland, la app puede no abrir desde el
menú tras reiniciar Desde una terminal, `xenonslice` funciona siempre. El `.desktop` abre una terminal
para que, si falla, veas el error.

## Cómo se hizo

Este proyecto se desarrolló con asistencia de IA (Claude, de Anthropic) para
el diseño, la escritura del código y la depuración. La idea, las pruebas en
hardware real y las decisiones de diseño son mías. La IA aceleró el proceso,
pero el código se ha revisado, probado y corregido en un Ryzen Z1 Extreme
con CachyOS.

Si encuentras un fallo, es tan mío como de la IA: abre un issue con tu CPU,
distro y lo que ha fallado.
