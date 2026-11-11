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
