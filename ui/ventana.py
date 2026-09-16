from __future__ import annotations

import sys
import tkinter as tk
from threading import Thread
from tkinter import messagebox, ttk
from typing import Any

from runas_auto import ServicioRunas
from runas_auto.arranque import activar_inicio_windows
from runas_auto.lcu import ClienteNoDisponible

FONDO = "#0a1428"
PANEL = "#111c33"
BORDE = "#c8aa6e"
TEXTO = "#f0e6d2"
MUTED = "#a09b8c"
OK = "#1f8a5b"
ERROR = "#c84b31"
SELECCION = "#1e3a5f"
FUENTE = ("Segoe UI", 10)
FUENTE_TITULO = ("Segoe UI", 16, "bold")
FUENTE_CHICA = ("Segoe UI", 9)


class VentanaRunas(tk.Tk):
    def __init__(self, iniciar_oculto: bool = False) -> None:
        super().__init__()
        self.servicio = ServicioRunas()
        self.campeones: list[dict[str, Any]] = []
        self.campeones_visibles: list[dict[str, Any]] = []
        self.paginas: list[dict[str, Any]] = []
        self.configurados_filas: list[dict[str, Any]] = []
        self._iniciar_oculto = iniciar_oculto
        self._catalogo_cargado = False
        self.icono_bandeja = None

        self.title("LoL Runas Auto")
        self.geometry("860x620")
        self.minsize(760, 540)
        self.configure(bg=FONDO)
        self._estilos()

        self.var_estado = tk.StringVar(value="Iniciando…")
        self.var_busqueda = tk.StringVar()
        self.var_pagina = tk.StringVar()
        self.var_log = tk.StringVar(value="Elige un campeón y una página de runas.")
        self.var_inicio = tk.BooleanVar(value=self.servicio.config.iniciar_con_windows())

        self._construir()
        self.var_busqueda.trace_add("write", lambda *_: self._filtrar_campeones())
        self.protocol("WM_DELETE_WINDOW", self.ocultar)
        self._iniciar_bandeja()
        if iniciar_oculto:
            self.withdraw()
        self.after(80, self._arrancar)

    def _estilos(self) -> None:
        estilo = ttk.Style(self)
        try:
            estilo.theme_use("clam")
        except tk.TclError:
            pass
        estilo.configure(
            "Arbol.Treeview",
            background=PANEL,
            fieldbackground=PANEL,
            foreground=TEXTO,
            rowheight=28,
            font=FUENTE,
            borderwidth=0,
        )
        estilo.configure(
            "Arbol.Treeview.Heading",
            background="#1a2744",
            foreground=BORDE,
            font=("Segoe UI", 10, "bold"),
            relief="flat",
        )
        estilo.map(
            "Arbol.Treeview",
            background=[("selected", SELECCION)],
            foreground=[("selected", TEXTO)],
        )
        estilo.configure(
            "Combo.TCombobox",
            fieldbackground=PANEL,
            background=PANEL,
            foreground=TEXTO,
            arrowcolor=BORDE,
        )

    def _construir(self) -> None:
        cabecera = tk.Frame(self, bg=FONDO)
        cabecera.pack(fill="x", padx=18, pady=(16, 8))
        tk.Label(
            cabecera,
            text="Runas por campeón",
            bg=FONDO,
            fg=BORDE,
            font=FUENTE_TITULO,
        ).pack(side="left")
        self.lbl_estado = tk.Label(
            cabecera,
            textvariable=self.var_estado,
            bg=FONDO,
            fg=MUTED,
            font=FUENTE_CHICA,
        )
        self.lbl_estado.pack(side="right")
        tk.Checkbutton(
            cabecera,
            text="Iniciar con Windows",
            variable=self.var_inicio,
            command=self._toggle_inicio,
            bg=FONDO,
            fg=TEXTO,
            selectcolor=PANEL,
            activebackground=FONDO,
            activeforeground=TEXTO,
            font=FUENTE_CHICA,
        ).pack(side="right", padx=(0, 16))

        cuerpo = tk.Frame(self, bg=FONDO)
        cuerpo.pack(fill="both", expand=True, padx=18, pady=4)
        cuerpo.columnconfigure(0, weight=1, uniform="col")
        cuerpo.columnconfigure(1, weight=1, uniform="col")
        cuerpo.rowconfigure(0, weight=1)

        self._panel_asignar(cuerpo).grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self._panel_configurados(cuerpo).grid(row=0, column=1, sticky="nsew", padx=(8, 0))

        pie = tk.Frame(self, bg=PANEL, highlightbackground=BORDE, highlightthickness=1)
        pie.pack(fill="x", padx=18, pady=(8, 16))
        self.lbl_log = tk.Label(
            pie,
            textvariable=self.var_log,
            bg=PANEL,
            fg=TEXTO,
            font=FUENTE,
            wraplength=780,
            justify="left",
            anchor="w",
        )
        self.lbl_log.pack(fill="x", padx=12, pady=10)

    def _panel_asignar(self, padre: tk.Widget) -> tk.Frame:
        marco = tk.Frame(padre, bg=PANEL, highlightbackground=BORDE, highlightthickness=1)
        tk.Label(
            marco,
            text="Preconfigurar",
            bg=PANEL,
            fg=BORDE,
            font=("Segoe UI", 12, "bold"),
        ).pack(anchor="w", padx=12, pady=(12, 6))

        tk.Label(marco, text="Buscar campeón", bg=PANEL, fg=MUTED, font=FUENTE_CHICA).pack(
            anchor="w", padx=12
        )
        entrada = tk.Entry(
            marco,
            textvariable=self.var_busqueda,
            bg="#0a1428",
            fg=TEXTO,
            insertbackground=TEXTO,
            relief="flat",
            font=FUENTE,
        )
        entrada.pack(fill="x", padx=12, pady=(2, 8), ipady=5)
        entrada.bind("<Return>", lambda _e: self._seleccionar_primero())

        lista_frame = tk.Frame(marco, bg=PANEL)
        lista_frame.pack(fill="both", expand=True, padx=12)
        scroll = tk.Scrollbar(lista_frame)
        scroll.pack(side="right", fill="y")
        self.lista_campeones = tk.Listbox(
            lista_frame,
            bg="#0a1428",
            fg=TEXTO,
            selectbackground=SELECCION,
            selectforeground=TEXTO,
            activestyle="none",
            relief="flat",
            font=FUENTE,
            highlightthickness=0,
            yscrollcommand=scroll.set,
            exportselection=False,
        )
        self.lista_campeones.pack(side="left", fill="both", expand=True)
        scroll.config(command=self.lista_campeones.yview)
        self.lista_campeones.bind("<<ListboxSelect>>", lambda _e: self._al_elegir_campeon())
        self.lista_campeones.bind("<Double-1>", lambda _e: self._guardar())

        tk.Label(marco, text="Página de runas", bg=PANEL, fg=MUTED, font=FUENTE_CHICA).pack(
            anchor="w", padx=12, pady=(10, 2)
        )
        fila_pagina = tk.Frame(marco, bg=PANEL)
        fila_pagina.pack(fill="x", padx=12)
        self.combo_paginas = ttk.Combobox(
            fila_pagina,
            textvariable=self.var_pagina,
            state="readonly",
            font=FUENTE,
            style="Combo.TCombobox",
        )
        self.combo_paginas.pack(side="left", fill="x", expand=True, ipady=2)
        tk.Button(
            fila_pagina,
            text="Actualizar",
            command=self._refrescar_paginas,
            bg="#1a2744",
            fg=TEXTO,
            activebackground=SELECCION,
            activeforeground=TEXTO,
            relief="flat",
            font=FUENTE_CHICA,
            cursor="hand2",
            padx=10,
        ).pack(side="left", padx=(8, 0))

        tk.Button(
            marco,
            text="Guardar asignación",
            command=self._guardar,
            bg=BORDE,
            fg="#0a1428",
            activebackground="#e0c080",
            activeforeground="#0a1428",
            relief="flat",
            font=("Segoe UI", 11, "bold"),
            cursor="hand2",
        ).pack(fill="x", padx=12, pady=14, ipady=6)
        return marco

    def _panel_configurados(self, padre: tk.Widget) -> tk.Frame:
        marco = tk.Frame(padre, bg=PANEL, highlightbackground=BORDE, highlightthickness=1)
        tk.Label(
            marco,
            text="Ya configurados",
            bg=PANEL,
            fg=BORDE,
            font=("Segoe UI", 12, "bold"),
        ).pack(anchor="w", padx=12, pady=(12, 6))
        tk.Label(
            marco,
            text="Estos se aplican solos en champ select. Cerrar la ventana la deja en la bandeja.",
            bg=PANEL,
            fg=MUTED,
            font=FUENTE_CHICA,
        ).pack(anchor="w", padx=12, pady=(0, 8))

        tabla_frame = tk.Frame(marco, bg=PANEL)
        tabla_frame.pack(fill="both", expand=True, padx=12)
        scroll = tk.Scrollbar(tabla_frame)
        scroll.pack(side="right", fill="y")
        self.tabla = ttk.Treeview(
            tabla_frame,
            columns=("campeon", "pagina"),
            show="headings",
            style="Arbol.Treeview",
            yscrollcommand=scroll.set,
            selectmode="browse",
        )
        self.tabla.heading("campeon", text="Campeón")
        self.tabla.heading("pagina", text="Página")
        self.tabla.column("campeon", width=160, anchor="w")
        self.tabla.column("pagina", width=160, anchor="w")
        self.tabla.pack(side="left", fill="both", expand=True)
        scroll.config(command=self.tabla.yview)
        self.tabla.bind("<Double-1>", lambda _e: self._cargar_desde_tabla())

        tk.Button(
            marco,
            text="Quitar seleccionado",
            command=self._quitar,
            bg=ERROR,
            fg="white",
            activebackground="#a33824",
            activeforeground="white",
            relief="flat",
            font=FUENTE,
            cursor="hand2",
        ).pack(fill="x", padx=12, pady=14, ipady=6)
        return marco

    def _arrancar(self) -> None:
        if self.servicio.config.iniciar_con_windows():
            activar_inicio_windows(True)
        self._pintar_configurados()
        self.servicio.iniciar(self._evento_hilo)
        self._actualizar_estado()
        if not self._iniciar_oculto:
            self._cargar_catalogo_async()
        elif not self.servicio.config.mapeos():
            self._notificar(
                "LoL Runas Auto",
                "Estoy en los iconos ocultos. Clic para configurar tus runas.",
            )

    def _cargar_catalogo_async(self) -> None:
        if self._catalogo_cargado:
            return
        self.var_log.set("Cargando campeones y páginas…")
        Thread(target=self._carga_fondo, daemon=True).start()

    def _carga_fondo(self) -> None:
        try:
            campeones = self.servicio.buscar_campeones("")
        except Exception as exc:  # noqa: BLE001
            self.after(0, lambda: self._log(f"No pude cargar campeones: {exc}", error=True))
            campeones = []
        try:
            paginas = self.servicio.paginas_runas()
        except ClienteNoDisponible:
            paginas = []
        except Exception:
            paginas = []
        self.after(0, lambda: self._aplicar_carga(campeones, paginas))

    def _aplicar_carga(
        self,
        campeones: list[dict[str, Any]],
        paginas: list[dict[str, Any]],
    ) -> None:
        self._catalogo_cargado = True
        self.campeones = campeones
        self._set_paginas(paginas)
        self._filtrar_campeones()
        self._pintar_configurados()
        if paginas:
            self._log("Listo. Asigna un campeón a su página y quedará guardado.")
        else:
            self._log("Abre el cliente de LoL para ver tus páginas de runas.", error=True)

    def _evento_hilo(self, evento: dict[str, Any]) -> None:
        self.after(0, lambda e=evento: self._manejar_evento(e))

    def _manejar_evento(self, evento: dict[str, Any]) -> None:
        tipo = evento.get("tipo")
        if tipo == "aplicado":
            texto = (
                f"Aplicadas '{evento.get('pagina_nombre')}' "
                f"para {evento.get('campeon_nombre')}."
            )
            self._log(texto)
            self._notificar("Runas aplicadas", texto)
        elif tipo == "sin_configurar":
            self._log(
                f"{evento.get('campeon_nombre')} no tiene página asignada.",
                error=True,
            )
        elif tipo == "cliente":
            self._log(
                "Cliente de LoL conectado."
                if evento.get("conectado")
                else "Cliente de LoL desconectado.",
                error=not evento.get("conectado"),
            )
            if evento.get("conectado") and self.winfo_viewable():
                self._refrescar_paginas()
        elif tipo == "fase":
            if self.winfo_viewable():
                self._log(f"Fase: {evento.get('fase')}")
        elif tipo == "error":
            self._log(str(evento.get("mensaje") or "Error"), error=True)
        self._actualizar_estado()

    def _actualizar_estado(self) -> None:
        if not self.winfo_exists() or not self.winfo_viewable():
            return
        try:
            estado = self.servicio.estado()
        except Exception:
            self.var_estado.set("Sin conexión")
            self.lbl_estado.configure(fg=ERROR)
            return
        if estado.get("conectado"):
            nombre = estado.get("invocador") or "invocador"
            self.var_estado.set(f"Conectado como {nombre}  ·  vigilando")
            self.lbl_estado.configure(fg=OK)
        else:
            self.var_estado.set("Cliente de LoL no detectado")
            self.lbl_estado.configure(fg=ERROR)

    def _filtrar_campeones(self) -> None:
        texto = self.var_busqueda.get().strip()
        if texto:
            consulta = texto.casefold()
            visibles = [
                c
                for c in self.campeones
                if consulta in c["nombre"].casefold()
                or consulta in str(c.get("alias", "")).casefold()
            ]
        else:
            visibles = list(self.campeones)
        self.campeones_visibles = visibles
        self.lista_campeones.delete(0, "end")
        for campeon in visibles:
            self.lista_campeones.insert("end", campeon["nombre"])

    def _seleccionar_primero(self) -> None:
        if not self.campeones_visibles:
            return
        self.lista_campeones.selection_clear(0, "end")
        self.lista_campeones.selection_set(0)
        self.lista_campeones.activate(0)
        self.lista_campeones.see(0)
        self._al_elegir_campeon()

    def _al_elegir_campeon(self) -> None:
        campeon = self._campeon_seleccionado()
        if not campeon:
            return
        for item in self.servicio.configurados():
            if int(item["campeon_id"]) == int(campeon["id"]):
                nombre = item.get("pagina_nombre") or ""
                if nombre and nombre in self.combo_paginas["values"]:
                    self.var_pagina.set(nombre)
                break

    def _campeon_seleccionado(self) -> dict[str, Any] | None:
        seleccion = self.lista_campeones.curselection()
        if not seleccion:
            return None
        indice = int(seleccion[0])
        if 0 <= indice < len(self.campeones_visibles):
            return self.campeones_visibles[indice]
        return None

    def _pagina_seleccionada(self) -> dict[str, Any] | None:
        nombre = self.var_pagina.get().strip()
        if not nombre:
            return None
        for pagina in self.paginas:
            if pagina["nombre"] == nombre:
                return pagina
        return None

    def _set_paginas(self, paginas: list[dict[str, Any]]) -> None:
        self.paginas = paginas
        nombres = [p["nombre"] for p in paginas]
        self.combo_paginas["values"] = nombres
        actual = next((p["nombre"] for p in paginas if p.get("actual")), "")
        if self.var_pagina.get() not in nombres:
            self.var_pagina.set(actual or (nombres[0] if nombres else ""))

    def _refrescar_paginas(self) -> None:
        try:
            paginas = self.servicio.paginas_runas()
        except ClienteNoDisponible:
            self._log("Abre el cliente de LoL para leer tus páginas.", error=True)
            return
        except Exception as exc:  # noqa: BLE001
            self._log(str(exc), error=True)
            return
        self._set_paginas(paginas)
        self._log(f"Páginas leídas: {', '.join(p['nombre'] for p in paginas) or 'ninguna'}.")

    def _pintar_configurados(self) -> None:
        self.configurados_filas = self.servicio.configurados()
        for fila in self.tabla.get_children():
            self.tabla.delete(fila)
        for item in self.configurados_filas:
            self.tabla.insert(
                "",
                "end",
                iid=str(item["campeon_id"]),
                values=(item.get("campeon_nombre"), item.get("pagina_nombre")),
            )

    def _guardar(self) -> None:
        campeon = self._campeon_seleccionado()
        pagina = self._pagina_seleccionada()
        if campeon is None:
            messagebox.showinfo("Falta el campeón", "Busca y selecciona un campeón de la lista.")
            return
        if pagina is None:
            messagebox.showinfo(
                "Falta la página",
                "Elige una página de runas. Si no ves ninguna, abre LoL y pulsa Actualizar.",
            )
            return
        try:
            self.servicio.asignar(campeon["id"], pagina_id=pagina["id"])
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("No se pudo guardar", str(exc))
            return
        self._pintar_configurados()
        self._log(f"{campeon['nombre']} usará la página '{pagina['nombre']}'.")

    def _quitar(self) -> None:
        seleccion = self.tabla.selection()
        if not seleccion:
            messagebox.showinfo("Nada seleccionado", "Elige una fila de la lista de configurados.")
            return
        campeon_id = int(seleccion[0])
        nombre = next(
            (
                i.get("campeon_nombre")
                for i in self.configurados_filas
                if int(i["campeon_id"]) == campeon_id
            ),
            str(campeon_id),
        )
        self.servicio.quitar(campeon_id)
        self._pintar_configurados()
        self._log(f"Quité la asignación de {nombre}.")

    def _cargar_desde_tabla(self) -> None:
        seleccion = self.tabla.selection()
        if not seleccion:
            return
        campeon_id = int(seleccion[0])
        for i, campeon in enumerate(self.campeones_visibles):
            if int(campeon["id"]) == campeon_id:
                self.lista_campeones.selection_clear(0, "end")
                self.lista_campeones.selection_set(i)
                self.lista_campeones.see(i)
                break
        else:
            campeon = next(
                (c for c in self.campeones if int(c["id"]) == campeon_id),
                None,
            )
            if campeon:
                self.var_busqueda.set(campeon["nombre"])
                self._filtrar_campeones()
                if self.campeones_visibles:
                    self.lista_campeones.selection_set(0)
        self._al_elegir_campeon()

    def _log(self, texto: str, error: bool = False) -> None:
        self.var_log.set(texto)
        self.lbl_log.configure(fg=ERROR if error else TEXTO)

    def _notificar(self, titulo: str, texto: str) -> None:
        icono = self.icono_bandeja
        if icono is None:
            return
        try:
            icono.notify(texto, titulo)
        except Exception:
            pass

    def _toggle_inicio(self) -> None:
        self._aplicar_inicio(bool(self.var_inicio.get()))

    def _aplicar_inicio(self, activo: bool) -> None:
        self.servicio.config.set_iniciar_con_windows(activo)
        activar_inicio_windows(activo)
        self._log(
            "Se iniciará con Windows."
            if activo
            else "Ya no se iniciará al prender la PC."
        )

    def _iniciar_bandeja(self) -> None:
        import pystray
        from runas_auto.icono import imagen_bandeja

        menu = pystray.Menu(
            pystray.MenuItem("Configurar", self._desde_bandeja_mostrar, default=True),
            pystray.MenuItem(
                "Iniciar con Windows",
                self._desde_bandeja_inicio,
                checked=lambda _: self.servicio.config.iniciar_con_windows(),
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Salir", self._desde_bandeja_salir),
        )
        self.icono_bandeja = pystray.Icon(
            "LoLRunasAuto",
            imagen_bandeja(),
            "LoL Runas Auto",
            menu,
        )
        Thread(target=self.icono_bandeja.run, daemon=True, name="bandeja").start()

    def _desde_bandeja_mostrar(self, *_args) -> None:
        self.after(0, self.mostrar)

    def _desde_bandeja_inicio(self, *_args) -> None:
        def toggle() -> None:
            nuevo = not self.servicio.config.iniciar_con_windows()
            self.var_inicio.set(nuevo)
            self._aplicar_inicio(nuevo)

        self.after(0, toggle)

    def _desde_bandeja_salir(self, *_args) -> None:
        self.after(0, self.salir)

    def mostrar(self) -> None:
        self.deiconify()
        self.lift()
        self.focus_force()
        self._pintar_configurados()
        self._actualizar_estado()
        if not self._catalogo_cargado:
            self._cargar_catalogo_async()

    def ocultar(self) -> None:
        self.withdraw()

    def salir(self) -> None:
        try:
            if self.icono_bandeja is not None:
                self.icono_bandeja.stop()
        except Exception:
            pass
        try:
            self.servicio.detener()
        except Exception:
            pass
        self.destroy()


def main(iniciar_oculto: bool = False) -> int:
    try:
        from ctypes import windll

        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    app = VentanaRunas(iniciar_oculto=iniciar_oculto)
    app.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
