"""XenonSlice - interfaz gráfica (Qt). Funciona con PyQt6 o PySide6."""
import shutil
import sys
import time

import core


def lanzar():
    try:
        from PyQt6 import QtCore as C, QtGui as G, QtWidgets as W
    except ImportError:
        try:
            from PySide6 import QtCore as C, QtGui as G, QtWidgets as W
        except ImportError:
            print("Falta Qt para Python. Instálalo con:  sudo pacman -S python-pyqt6")
            return 1

    VERDE, ROJO, AMBAR = "#2e9e5b", "#d64545", "#c58a00"
    Btn = W.QMessageBox.StandardButton

    def item(texto, color=None):
        it = W.QTableWidgetItem(texto)
        if color:
            it.setForeground(G.QBrush(G.QColor(color)))
        return it

    def tabla(columnas):
        t = W.QTableWidget(0, len(columnas))
        t.setHorizontalHeaderLabels(columnas)
        t.verticalHeader().setVisible(False)
        t.verticalHeader().setDefaultSectionSize(38)
        t.setEditTriggers(W.QAbstractItemView.EditTrigger.NoEditTriggers)
        t.setSelectionBehavior(W.QAbstractItemView.SelectionBehavior.SelectRows)
        t.setSelectionMode(W.QAbstractItemView.SelectionMode.SingleSelection)
        t.horizontalHeader().setStretchLastSection(True)
        return t

    def boton(texto, funcion):
        b = W.QPushButton(texto)
        b.setMinimumHeight(38)
        b.clicked.connect(funcion)
        return b

    class Ventana(W.QMainWindow):
        def __init__(self):
            super().__init__()
            self.setWindowTitle(f"XenonSlice {core.VERSION}")
            self.resize(1020, 720)
            self.apps, self.unidades, self.filas = [], [], []
            self.tabs = W.QTabWidget()
            self.setCentralWidget(self.tabs)
            self.tabs.addTab(self._tab_sistema(), "Sistema")
            self.tabs.addTab(self._tab_apps(), "Apps")
            self.tabs.addTab(self._tab_marcha(), "En marcha")
            self.timer = C.QTimer(self)
            self.timer.timeout.connect(self._tick)
            self.timer.start(5000)
            C.QTimer.singleShot(150, self.escanear_todo)

        # ---------- utilidades ----------
        def mostrar_texto(self, titulo, texto):
            d = W.QDialog(self)
            d.setWindowTitle(titulo)
            d.resize(840, 560)
            lay = W.QVBoxLayout(d)
            e = W.QPlainTextEdit()
            e.setReadOnly(True)
            e.setPlainText(texto)
            e.setFont(G.QFontDatabase.systemFont(G.QFontDatabase.SystemFont.FixedFont))
            lay.addWidget(e)
            lay.addWidget(boton("Cerrar", d.accept))
            d.exec()

        def preguntar(self, titulo, texto):
            return W.QMessageBox.question(self, titulo, texto) == Btn.Yes

        # ---------- pestaña Sistema ----------
        def _tab_sistema(self):
            w = W.QWidget()
            lay = W.QVBoxLayout(w)
            self.lbl_topo = W.QLabel("Comprobando el equipo…")
            self.lbl_topo.setWordWrap(True)
            self.lbl_topo.setStyleSheet("padding:10px; border-left:5px solid #888;")
            lay.addWidget(self.lbl_topo)

            caja = W.QGroupBox("Qué configurar (los slices siempre se aplican)")
            l2 = W.QHBoxLayout(caja)
            self.chk = {}
            for clave, txt in (("audio", "Audio en zona Sistema"), ("easyeffects", "EasyEffects como servicio"),
                               ("wine", "WINE_CPU_TOPOLOGY")):
                c = W.QCheckBox(txt)
                c.setChecked(True)
                self.chk[clave] = c
                l2.addWidget(c)
            if not shutil.which("easyeffects"):
                self.chk["easyeffects"].setChecked(False)
                self.chk["easyeffects"].setEnabled(False)
                self.chk["easyeffects"].setText("EasyEffects (no instalado)")
            lay.addWidget(caja)

            self.t_sis = tabla(["Comprobación", "Estado", "Detalle"])
            self.t_sis.setColumnWidth(0, 320)
            self.t_sis.setColumnWidth(1, 100)
            lay.addWidget(self.t_sis)

            fila = W.QHBoxLayout()
            fila.addWidget(boton("Vista previa", self.vista_previa))
            self.btn_aplicar = boton("Aplicar configuración", self.aplicar)
            fila.addWidget(self.btn_aplicar)
            fila.addWidget(boton("Comprobar de nuevo", self.escanear_todo))
            lay.addLayout(fila)

            fila2 = W.QHBoxLayout()
            self.chk_heredados = W.QCheckBox("Al revertir, quitar también archivos de configuraciones anteriores")
            fila2.addWidget(self.chk_heredados, 1)
            fila2.addWidget(boton("Revertir", self.revertir))
            lay.addLayout(fila2)
            return w

        def pasos_elegidos(self):
            return [k for k, c in self.chk.items() if c.isChecked() and c.isEnabled()]

        def pintar_sistema(self):
            t = core.detectar_topologia()
            p = core.perfil()
            cab = f"{t['modelo']} — {t['nucleos']} núcleos, {t['hilos']} hilos, {t['l3']} dominio(s) de caché L3."
            if t["ok"]:
                texto = (f"✔ Compatible. {cab}\nSistema: hilos {p['sistema']} ({p['reservados']} núcleos) · "
                         f"Usuario: hilos {p['usuario']}")
                color = VERDE
            else:
                texto = f"✘ No compatible. {cab}\n" + "\n".join(f"• {m}" for m in t["motivos"])
                color = ROJO
            if t["avisos"]:
                texto += "\n" + "\n".join(f"Aviso: {a}" for a in t["avisos"])
            if t["ranking"]:
                texto += "\nRanking de núcleos (informativo): " + ", ".join(
                    f"{k}={v}" for k, v in sorted(t["ranking"].items()))
            self.lbl_topo.setText(texto)
            self.lbl_topo.setStyleSheet(f"padding:10px; border-left:5px solid {color};")
            self.btn_aplicar.setEnabled(t["ok"])

            tb = self.t_sis
            tb.setRowCount(0)
            if not t["ok"]:
                return
            simb = {"ok": ("✔ listo", VERDE), "falta": ("✘ falta", ROJO), "aviso": ("• sin datos", AMBAR)}
            for c in core.estado():
                r = tb.rowCount()
                tb.insertRow(r)
                txt, color = simb[c["estado"]]
                tb.setItem(r, 0, item(c["nombre"]))
                tb.setItem(r, 1, item(txt, color))
                tb.setItem(r, 2, item(c["detalle"]))

        def vista_previa(self):
            self.mostrar_texto("Vista previa", core.vista_previa(self.pasos_elegidos()))

        def aplicar(self):
            pasos = self.pasos_elegidos()
            if not self.preguntar("Aplicar configuración",
                                  "Se escribirán los archivos de la vista previa. Se te pedirá la contraseña "
                                  "de administrador para la parte del sistema.\n\n¿Continuar?"):
                return
            self.statusBar().showMessage("Aplicando…")
            W.QApplication.processEvents()
            ok, msg = core.aplicar(pasos)
            (W.QMessageBox.information if ok else W.QMessageBox.warning)(
                self, "Resultado" if ok else "No se pudo aplicar", msg)
            if ok and self.preguntar("Reiniciar el audio",
                                     "El audio, EasyEffects y Wine toman los cambios al reiniciar la sesión.\n"
                                     "Puedo reiniciar ahora el audio (se corta unos segundos). ¿Hacerlo?"):
                core.reiniciar_audio("easyeffects" in pasos)
            self.statusBar().clearMessage()
            self.pintar_sistema()

        def revertir(self):
            todo = self.chk_heredados.isChecked()
            if not self.preguntar("Revertir", "Se quitará la configuración de XenonSlice y todo volverá a 0-15."
                                  "\nSe te pedirá la contraseña de administrador.\n\n¿Continuar?"):
                return
            ok, msg = core.revertir(heredados=todo)
            (W.QMessageBox.information if ok else W.QMessageBox.warning)(
                self, "Resultado" if ok else "No se pudo revertir", msg)
            self.pintar_sistema()

        # ---------- pestaña Apps ----------
        def _tab_apps(self):
            w = W.QWidget()
            lay = W.QVBoxLayout(w)
            barra = W.QHBoxLayout()
            self.filtro = W.QLineEdit()
            self.filtro.setPlaceholderText("Buscar app…")
            self.filtro.textChanged.connect(self.filtrar)
            self.combo_filtro = W.QComboBox()
            for k, v in (("todas", "Todas"), ("regla", "Con zona asignada"), ("marcha", "En marcha"),
                         ("flatpak", "Flatpak")):
                self.combo_filtro.addItem(v, k)
            self.combo_filtro.currentIndexChanged.connect(self.filtrar)
            barra.addWidget(self.filtro, 1)
            barra.addWidget(self.combo_filtro)
            lay.addLayout(barra)
            self.t_apps = tabla(["App", "Tipo", "Zona", "En marcha", "Verificación"])
            for i, ancho in enumerate((260, 80, 190, 130)):
                self.t_apps.setColumnWidth(i, ancho)
            lay.addWidget(self.t_apps)
            nota = W.QLabel("Una zona nueva solo se aplica cuando la app se abre de nuevo. Las apps lanzadas "
                            "desde una terminal o desde Steam heredan la zona de quien las lanza.")
            nota.setWordWrap(True)
            lay.addWidget(nota)
            fila = W.QHBoxLayout()
            fila.addWidget(boton("Guardar zonas", self.guardar_zonas))
            fila.addWidget(boton("Cerrar app", self.cerrar_sel))
            fila.addWidget(boton("Abrir app", self.abrir_sel))
            fila.addWidget(boton("Volver a escanear", self.escanear_apps))
            lay.addLayout(fila)
            return w

        def escanear_apps(self):
            self.statusBar().showMessage("Escaneando apps…")
            W.QApplication.processEvents()
            self.apps, self.unidades = core.listar_apps()
            self.pintar_apps()
            self.statusBar().showMessage(f"{len(self.apps)} apps encontradas.", 5000)

        def pintar_apps(self):
            t = self.t_apps
            t.setRowCount(0)
            self.filas = list(self.apps)
            zonas = core.zonas()
            for a in self.filas:
                r = t.rowCount()
                t.insertRow(r)
                t.setItem(r, 0, item(a["nombre"]))
                t.setItem(r, 1, item(a["tipo"]))
                cb = W.QComboBox()
                for k, z in zonas.items():
                    cb.addItem(z["etiqueta"], k)
                cb.setCurrentIndex(list(zonas).index(a["regla"]))
                t.setCellWidget(r, 2, cb)
                estado, texto = core.verificar(a)
                t.setItem(r, 3, item(", ".join(sorted({u["cpus"] for u in a["unidades"]})) or "no"))
                t.setItem(r, 4, item(texto, {"ok": VERDE, "falla": ROJO}.get(estado)))
            self.filtrar()

        def filtrar(self):
            texto = self.filtro.text().strip().lower()
            modo = self.combo_filtro.currentData()
            for r, a in enumerate(self.filas):
                visible = texto in a["nombre"].lower() or texto in a["id"].lower()
                if modo == "regla":
                    visible = visible and a["regla"] != "predeterminada"
                elif modo == "marcha":
                    visible = visible and bool(a["unidades"])
                elif modo == "flatpak":
                    visible = visible and a["tipo"] == "flatpak"
                self.t_apps.setRowHidden(r, not visible)

        def _app_seleccionada(self):
            r = self.t_apps.currentRow()
            if r < 0 or r >= len(self.filas):
                self.statusBar().showMessage("Elige primero una app de la lista.", 5000)
                return None
            return self.filas[r]

        def guardar_zonas(self):
            cambios = []
            for r, a in enumerate(self.filas):
                nueva = self.t_apps.cellWidget(r, 2).currentData()
                if nueva != a["regla"]:
                    cambios.append((a, nueva))
            if not cambios:
                self.statusBar().showMessage("No hay cambios que guardar.", 5000)
                return
            for a, nueva in cambios:
                core.escribir_regla(a, nueva, recargar=False)
            core.run(["systemctl", "--user", "daemon-reload"])
            en_marcha = [a for a, _ in cambios if a["unidades"]]
            if en_marcha and self.preguntar(
                    "Reabrir apps", "Zonas guardadas. Para que se apliquen hay que cerrar y volver a abrir: "
                    + ", ".join(a["nombre"] for a in en_marcha) + ".\n\n¿Hacerlo ahora?"):
                for a in en_marcha:
                    core.cerrar(a)
                time.sleep(2)
                for a in en_marcha:
                    if not core.abrir(a):
                        W.QMessageBox.information(self, "Ábrela a mano", f"No pude abrir {a['nombre']}; ábrela desde el menú.")
            self.statusBar().showMessage(f"{len(cambios)} zona(s) guardada(s). Comprobando en 6 s…", 6000)
            C.QTimer.singleShot(6000, self.escanear_apps)

        def cerrar_sel(self):
            a = self._app_seleccionada()
            if a:
                core.cerrar(a)
                C.QTimer.singleShot(2500, self.escanear_apps)

        def abrir_sel(self):
            a = self._app_seleccionada()
            if a:
                if not core.abrir(a):
                    W.QMessageBox.information(self, "Ábrela a mano", "No encuentro cómo abrirla desde aquí; ábrela desde el menú.")
                C.QTimer.singleShot(6000, self.escanear_apps)

        # ---------- pestaña En marcha ----------
        def _tab_marcha(self):
            w = W.QWidget()
            lay = W.QVBoxLayout(w)
            self.t_marcha = tabla(["App", "Tipo", "Slice", "Cores reales", "Unidad"])
            for i, ancho in enumerate((260, 80, 150, 120)):
                self.t_marcha.setColumnWidth(i, ancho)
            lay.addWidget(self.t_marcha)
            lay.addWidget(W.QLabel("Se actualiza cada 5 segundos. Muestra dónde corre cada app lanzada como unidad de systemd."))
            return w

        def pintar_marcha(self):
            t = self.t_marcha
            t.setRowCount(0)
            sistema = core.perfil()["sistema"]
            for u in sorted(self.unidades, key=lambda x: (x["cpus"], x["app"].lower())):
                r = t.rowCount()
                t.insertRow(r)
                t.setItem(r, 0, item(u["app"]))
                t.setItem(r, 1, item(u["tipo"]))
                t.setItem(r, 2, item(u["slice"]))
                t.setItem(r, 3, item(u["cpus"], VERDE if u["cpus"] == sistema else None))
                t.setItem(r, 4, item(u["unidad"]))

        def _tick(self):
            if self.tabs.currentIndex() == 2:
                self.unidades = core.unidades_en_marcha()
                self.pintar_marcha()

        def escanear_todo(self):
            self.pintar_sistema()
            self.escanear_apps()
            self.pintar_marcha()

    app = W.QApplication(sys.argv)
    v = Ventana()
    v.show()
    return app.exec()
