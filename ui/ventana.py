from __future__ import annotations

import sys
import tkinter as tk
import tkinter.font as tkfont
import traceback
from threading import Event, Thread
from tkinter import messagebox, ttk
from typing import Any

from runas_auto import ServicioRunas
from runas_auto.arranque import activar_inicio_windows, consumir_pedido_mostrar
from runas_auto.lcu import ClienteNoDisponible
from runas_auto.log import registrar, registrar_excepcion
from runas_auto.skins import ETIQUETAS_SKIN
from runas_auto.twitch_auth import TwitchAuthError

# Hextech Obsidian Utility (Stitch): utilidad oscura, densa, acento dorado.
CANVAS = "#0b0f19"
PANEL = "#111726"
PANEL_BAJO = "#171b26"
TARJETA = "#1a2236"
HOVER = "#222d47"
INSET = "#0a0e18"
BORDE = "#26334d"
BORDE_SUAVE = "#1e293b"
ORO = "#c8aa6e"
ORO_CLARO = "#f0e6d2"
TEXTO = "#dfe2f1"
MUTED = "#998f81"
OK = "#22c55e"
ERROR = "#ef4444"
TWITCH = "#9146ff"
SELECCION = "#3a3220"
TINTA = "#0b0f19"


def _sigla(nombre: str) -> str:
    limpio = "".join(c for c in nombre if c.isalnum())
    if len(limpio) >= 2:
        return limpio[:2].upper()
    return (limpio or "?").upper()


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
        self._asignacion_sel: int | None = None
        self._tarjetas: dict[int, tk.Frame] = {}
        self._botones_skin: dict[str, tk.Button] = {}
        self._fuentes()

        self.title("LoL Runas Auto")
        self.geometry("1140x780")
        self.minsize(1020, 680)
        self.configure(bg=CANVAS)
        self._estilos()

        self.var_estado = tk.StringVar(value="Iniciando…")
        self.var_lcu = tk.StringVar(value="LCU · …")
        self.var_busqueda = tk.StringVar()
        self.var_pagina = tk.StringVar()
        self.var_log = tk.StringVar(value="Elige un campeón y una página de runas.")
        self.var_mapeados = tk.StringVar(value="0 mapeados")
        self.var_inicio = tk.BooleanVar(value=self.servicio.config.iniciar_con_windows())
        self.var_skin = tk.StringVar(
            value=ETIQUETAS_SKIN.get(self.servicio.modo_skin(), "No cambiar")
        )
        self.var_bloqueos = tk.BooleanVar(
            value=self.servicio.config.bloquear_solicitudes()
        )
        twitch = self.servicio.twitch()
        self.var_twitch = tk.BooleanVar(value=bool(twitch.get("habilitado")))
        self.var_canal = tk.StringVar(value=str(twitch.get("canal") or ""))
        self.var_client_id = tk.StringVar(value=str(twitch.get("client_id") or ""))
        self._oauth_cancelar: Event | None = None
        self._dlg_twitch: tk.Toplevel | None = None

        self._construir()
        self.var_busqueda.trace_add("write", lambda *_: self._filtrar_campeones())
        self.bind("<Control-f>", self._foco_busqueda)
        self.bind("<Control-F>", self._foco_busqueda)
        self.protocol("WM_DELETE_WINDOW", self.ocultar)
        self._iniciar_bandeja()
        if iniciar_oculto:
            self.withdraw()
        self.report_callback_exception = self._error_tk  # type: ignore[method-assign]
        self.after(80, self._arrancar)
        self.after(800, self._revisar_pedido_mostrar)

    def _fuentes(self) -> None:
        familias = {nombre.casefold() for nombre in tkfont.families()}

        def elegir(opciones: tuple[str, ...], respaldo: str) -> str:
            for nombre in opciones:
                if nombre.casefold() in familias:
                    return nombre
            return respaldo

        self.fuente_titulo = elegir(("Space Grotesk", "Segoe UI"), "Segoe UI")
        self.fuente_cuerpo = elegir(("Geist", "Segoe UI"), "Segoe UI")
        self.fuente_mono = elegir(
            ("JetBrains Mono", "Cascadia Mono", "Consolas"), "Consolas"
        )

    def _estilos(self) -> None:
        estilo = ttk.Style(self)
        try:
            estilo.theme_use("clam")
        except tk.TclError:
            pass
        estilo.configure(
            "Combo.TCombobox",
            fieldbackground=INSET,
            background=TARJETA,
            foreground=ORO,
            arrowcolor=ORO,
            bordercolor=BORDE,
            lightcolor=BORDE,
            darkcolor=BORDE,
            padding=4,
        )
        estilo.map(
            "Combo.TCombobox",
            fieldbackground=[("readonly", INSET)],
            foreground=[("readonly", ORO)],
            selectbackground=[("readonly", INSET)],
            selectforeground=[("readonly", ORO)],
        )
        estilo.configure(
            "Oscuro.TCheckbutton",
            background=PANEL_BAJO,
            foreground=TEXTO,
            font=(self.fuente_cuerpo, 9),
            indicatorcolor=INSET,
            focuscolor=PANEL_BAJO,
        )
        estilo.map(
            "Oscuro.TCheckbutton",
            background=[("active", PANEL_BAJO)],
            foreground=[("active", ORO_CLARO)],
            indicatorcolor=[("selected", ORO), ("!selected", INSET)],
        )
        estilo.configure(
            "Caja.TCheckbutton",
            background=INSET,
            foreground=TEXTO,
            indicatorcolor=INSET,
            focuscolor=INSET,
        )
        estilo.map(
            "Caja.TCheckbutton",
            background=[("active", INSET)],
            indicatorcolor=[("selected", ORO), ("!selected", CANVAS)],
        )
        estilo.configure(
            "Estado.TCheckbutton",
            background=PANEL,
            foreground=MUTED,
            font=(self.fuente_cuerpo, 9),
            indicatorcolor=INSET,
            focuscolor=PANEL,
        )
        estilo.map(
            "Estado.TCheckbutton",
            background=[("active", PANEL)],
            foreground=[("active", TEXTO)],
            indicatorcolor=[("selected", ORO), ("!selected", INSET)],
        )
        estilo.configure(
            "Oscuro.Vertical.TScrollbar",
            background=TARJETA,
            troughcolor=INSET,
            bordercolor=INSET,
            arrowcolor=ORO,
            relief="flat",
        )
        self.option_add("*TCombobox*Listbox.background", INSET)
        self.option_add("*TCombobox*Listbox.foreground", TEXTO)
        self.option_add("*TCombobox*Listbox.selectBackground", SELECCION)
        self.option_add("*TCombobox*Listbox.selectForeground", ORO)
        self.option_add("*TCombobox*Listbox.font", (self.fuente_mono, 10))

    def _construir(self) -> None:
        self._barra_marca()
        self._barra_estado()

        cuerpo = tk.Frame(self, bg=CANVAS)
        cuerpo.pack(fill="both", expand=True, padx=10, pady=8)
        cuerpo.columnconfigure(0, weight=4, uniform="col")
        cuerpo.columnconfigure(1, weight=4, uniform="col")
        cuerpo.columnconfigure(2, weight=4, uniform="col")
        cuerpo.rowconfigure(0, weight=1)

        self._panel_asignar(cuerpo).grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        self._panel_configurados(cuerpo).grid(row=0, column=1, sticky="nsew", padx=5)
        self._panel_twitch(cuerpo).grid(row=0, column=2, sticky="nsew", padx=(5, 0))
        self._pie()
        self._pintar_botones_skin()

    def _barra_marca(self) -> None:
        barra = tk.Frame(self, bg=INSET, height=34)
        barra.pack(fill="x")
        barra.pack_propagate(False)
        tk.Label(
            barra,
            text="LoL Runas Auto",
            bg=INSET,
            fg=ORO,
            font=(self.fuente_titulo, 12, "bold"),
        ).pack(side="left", padx=(12, 8))
        pastilla = tk.Frame(barra, bg=PANEL_BAJO, highlightbackground=BORDE, highlightthickness=1)
        pastilla.pack(side="left", pady=6)
        self.lbl_punto_lcu = tk.Label(
            pastilla, text="●", bg=PANEL_BAJO, fg=MUTED, font=(self.fuente_mono, 8)
        )
        self.lbl_punto_lcu.pack(side="left", padx=(6, 2))
        tk.Label(
            pastilla,
            textvariable=self.var_lcu,
            bg=PANEL_BAJO,
            fg=OK,
            font=(self.fuente_mono, 8),
        ).pack(side="left", padx=(0, 6))
        self.lbl_lcu = pastilla.winfo_children()[-1]

    def _barra_estado(self) -> None:
        barra = tk.Frame(self, bg=PANEL, highlightbackground=BORDE_SUAVE, highlightthickness=1)
        barra.pack(fill="x", padx=10, pady=(8, 0))
        izquierda = tk.Frame(barra, bg=PANEL)
        izquierda.pack(side="left", fill="x", expand=True, padx=10, pady=8)
        tk.Label(
            izquierda,
            text="Runas por campeón",
            bg=PANEL,
            fg=ORO,
            font=(self.fuente_titulo, 15, "bold"),
        ).pack(side="left")
        pastilla = tk.Frame(
            izquierda, bg=INSET, highlightbackground=BORDE, highlightthickness=1
        )
        pastilla.pack(side="left", padx=(12, 0))
        self.lbl_punto = tk.Label(
            pastilla, text="●", bg=INSET, fg=MUTED, font=(self.fuente_cuerpo, 9)
        )
        self.lbl_punto.pack(side="left", padx=(8, 4), pady=3)
        self.lbl_estado = tk.Label(
            pastilla,
            textvariable=self.var_estado,
            bg=INSET,
            fg=MUTED,
            font=(self.fuente_mono, 9),
        )
        self.lbl_estado.pack(side="left", padx=(0, 8), pady=3)

        derecha = tk.Frame(barra, bg=PANEL)
        derecha.pack(side="right", padx=10)
        ttk.Checkbutton(
            derecha,
            text="Iniciar con Windows",
            variable=self.var_inicio,
            command=self._toggle_inicio,
            style="Estado.TCheckbutton",
        ).pack(side="left", padx=(0, 12))
        tk.Label(
            derecha,
            text="Cerrar envía la app a la bandeja",
            bg=PANEL,
            fg=MUTED,
            font=(self.fuente_cuerpo, 8),
        ).pack(side="left")

    def _panel_asignar(self, padre: tk.Widget) -> tk.Frame:
        marco = tk.Frame(
            padre, bg=PANEL_BAJO, highlightbackground=BORDE, highlightthickness=1
        )
        self._cabecera_panel(marco, "Preconfigurar campeón", "Paso 1")

        cuerpo = tk.Frame(marco, bg=PANEL_BAJO)
        cuerpo.pack(fill="both", expand=True, padx=10, pady=10)

        tk.Label(
            cuerpo, text="Buscar campeón", bg=PANEL_BAJO, fg=MUTED, font=(self.fuente_cuerpo, 8)
        ).pack(anchor="w")
        self.entrada_busqueda = tk.Entry(
            cuerpo,
            textvariable=self.var_busqueda,
            bg=INSET,
            fg=TEXTO,
            insertbackground=ORO,
            relief="flat",
            font=(self.fuente_cuerpo, 10),
            highlightthickness=1,
            highlightbackground=BORDE,
            highlightcolor=ORO,
        )
        self.entrada_busqueda.pack(fill="x", pady=(2, 8), ipady=4)
        self.entrada_busqueda.bind("<Return>", lambda _e: self._seleccionar_primero())

        lista_frame = tk.Frame(
            cuerpo, bg=INSET, highlightbackground=BORDE, highlightthickness=1
        )
        lista_frame.pack(fill="both", expand=True)
        scroll = ttk.Scrollbar(lista_frame, style="Oscuro.Vertical.TScrollbar")
        scroll.pack(side="right", fill="y")
        self.lista_campeones = tk.Listbox(
            lista_frame,
            bg=INSET,
            fg=TEXTO,
            selectbackground=SELECCION,
            selectforeground=ORO,
            activestyle="none",
            relief="flat",
            font=(self.fuente_mono, 10),
            highlightthickness=0,
            bd=0,
            yscrollcommand=scroll.set,
            exportselection=False,
        )
        self.lista_campeones.pack(side="left", fill="both", expand=True)
        scroll.config(command=self.lista_campeones.yview)
        self.lista_campeones.bind("<<ListboxSelect>>", lambda _e: self._al_elegir_campeon())
        self.lista_campeones.bind("<Double-1>", lambda _e: self._guardar())

        tk.Label(
            cuerpo,
            text="Página de runas",
            bg=PANEL_BAJO,
            fg=MUTED,
            font=(self.fuente_cuerpo, 8),
        ).pack(anchor="w", pady=(10, 2))
        fila_pagina = tk.Frame(cuerpo, bg=PANEL_BAJO)
        fila_pagina.pack(fill="x")
        self.combo_paginas = ttk.Combobox(
            fila_pagina,
            textvariable=self.var_pagina,
            state="readonly",
            font=(self.fuente_mono, 10),
            style="Combo.TCombobox",
        )
        self.combo_paginas.pack(side="left", fill="x", expand=True, ipady=2)
        self._boton(fila_pagina, "Actualizar", self._refrescar_paginas).pack(
            side="left", padx=(8, 0)
        )

        tk.Label(
            cuerpo,
            text="Skin en champ select",
            bg=PANEL_BAJO,
            fg=MUTED,
            font=(self.fuente_cuerpo, 8),
        ).pack(anchor="w", pady=(10, 2))
        fila_skin = tk.Frame(cuerpo, bg=PANEL_BAJO)
        fila_skin.pack(fill="x")
        for indice, etiqueta in enumerate(ETIQUETAS_SKIN.values()):
            fila_skin.columnconfigure(indice, weight=1)
            boton = tk.Button(
                fila_skin,
                text=etiqueta,
                command=lambda valor=etiqueta: self._elegir_skin(valor),
                relief="flat",
                bd=0,
                font=(self.fuente_cuerpo, 9),
                cursor="hand2",
                highlightthickness=1,
            )
            boton.grid(row=0, column=indice, sticky="ew", padx=(0 if indice == 0 else 3, 0), ipady=3)
            self._botones_skin[etiqueta] = boton
        tk.Label(
            cuerpo,
            text="El modo de skin vale para todos los campeones.",
            bg=PANEL_BAJO,
            fg=MUTED,
            font=(self.fuente_cuerpo, 8),
        ).pack(anchor="w", pady=(4, 0))

        caja = tk.Frame(
            cuerpo, bg=INSET, highlightbackground=BORDE_SUAVE, highlightthickness=1
        )
        caja.pack(fill="x", pady=(10, 0))
        fila_bloqueo = tk.Frame(caja, bg=INSET)
        fila_bloqueo.pack(fill="x", padx=8, pady=8)
        ttk.Checkbutton(
            fila_bloqueo,
            variable=self.var_bloqueos,
            command=self._guardar_bloqueos,
            style="Caja.TCheckbutton",
        ).pack(side="left", anchor="n")
        lbl_bloqueo = tk.Label(
            fila_bloqueo,
            text="Bloquear solicitudes de quien no jugó mis últimas 2 partidas (máx. 3)",
            bg=INSET,
            fg=TEXTO,
            font=(self.fuente_cuerpo, 8),
            wraplength=250,
            justify="left",
            anchor="w",
        )
        lbl_bloqueo.pack(side="left", fill="x", expand=True, padx=(4, 0))
        lbl_bloqueo.bind("<Button-1>", lambda _e: self._alternar_bloqueos())
        caja.bind(
            "<Configure>",
            lambda e: lbl_bloqueo.configure(wraplength=max(140, e.width - 48)),
        )

        self._boton(cuerpo, "Guardar asignación", self._guardar, primario=True).pack(
            fill="x", pady=(12, 0), ipady=2
        )
        return marco

    def _panel_configurados(self, padre: tk.Widget) -> tk.Frame:
        marco = tk.Frame(padre, bg=INSET, highlightbackground=BORDE, highlightthickness=1)
        cabecera = tk.Frame(marco, bg=TARJETA, height=36)
        cabecera.pack(fill="x")
        cabecera.pack_propagate(False)
        tk.Label(
            cabecera,
            text="Asignaciones activas",
            bg=TARJETA,
            fg=ORO,
            font=(self.fuente_titulo, 12, "bold"),
        ).pack(side="left", padx=10)
        self.lbl_mapeados = tk.Label(
            cabecera,
            textvariable=self.var_mapeados,
            bg=SELECCION,
            fg=ORO,
            font=(self.fuente_mono, 8),
            padx=6,
            pady=1,
        )
        self.lbl_mapeados.pack(side="right", padx=10)

        aviso = tk.Frame(marco, bg=PANEL_BAJO)
        aviso.pack(fill="x")
        tk.Label(
            aviso,
            text=(
                "Se aplican solas al bloquear en champ select. "
                "Cerrar la ventana mantiene la vigilancia en la bandeja."
            ),
            bg=PANEL_BAJO,
            fg=MUTED,
            font=(self.fuente_cuerpo, 8),
            wraplength=320,
            justify="left",
            anchor="w",
        ).pack(fill="x", padx=10, pady=8)
        aviso.bind("<Configure>", lambda e: aviso.winfo_children()[0].configure(wraplength=max(160, e.width - 20)))

        zona = tk.Frame(marco, bg=INSET)
        zona.pack(fill="both", expand=True, padx=8, pady=(0, 4))
        self.canvas_asignaciones = tk.Canvas(zona, bg=INSET, highlightthickness=0, bd=0)
        scroll = ttk.Scrollbar(
            zona, orient="vertical", command=self.canvas_asignaciones.yview, style="Oscuro.Vertical.TScrollbar"
        )
        self.marco_asignaciones = tk.Frame(self.canvas_asignaciones, bg=INSET)
        self._ventana_asignaciones = self.canvas_asignaciones.create_window(
            (0, 0), window=self.marco_asignaciones, anchor="nw"
        )
        self.marco_asignaciones.bind(
            "<Configure>",
            lambda _e: self.canvas_asignaciones.configure(
                scrollregion=self.canvas_asignaciones.bbox("all")
            ),
        )
        self.canvas_asignaciones.bind(
            "<Configure>",
            lambda e: self.canvas_asignaciones.itemconfigure(self._ventana_asignaciones, width=e.width),
        )
        self.canvas_asignaciones.configure(yscrollcommand=scroll.set)
        self.canvas_asignaciones.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self._enganchar_rueda(self.canvas_asignaciones)
        self._enganchar_rueda(self.marco_asignaciones)

        self._boton(marco, "Quitar seleccionado", self._quitar, peligro=True).pack(
            fill="x", padx=10, pady=(4, 10), ipady=1
        )
        return marco

    def _panel_twitch(self, padre: tk.Widget) -> tk.Frame:
        marco = tk.Frame(
            padre, bg=PANEL_BAJO, highlightbackground=BORDE, highlightthickness=1
        )
        cabecera = tk.Frame(marco, bg=TARJETA, height=36)
        cabecera.pack(fill="x")
        cabecera.pack_propagate(False)
        tk.Label(
            cabecera,
            text="Chat de Twitch",
            bg=TARJETA,
            fg=ORO,
            font=(self.fuente_titulo, 12, "bold"),
        ).pack(side="left", padx=10)
        self.lbl_twitch_chip = tk.Label(
            cabecera,
            text="apagado",
            bg=INSET,
            fg=MUTED,
            font=(self.fuente_mono, 8),
            padx=6,
        )
        self.lbl_twitch_chip.pack(side="right", padx=10)

        cuerpo = tk.Frame(marco, bg=PANEL_BAJO)
        cuerpo.pack(fill="both", expand=True, padx=10, pady=10)

        ttk.Checkbutton(
            cuerpo,
            text="Escuchar chat",
            variable=self.var_twitch,
            command=self._guardar_twitch,
            style="Oscuro.TCheckbutton",
        ).pack(anchor="w")

        tk.Label(
            cuerpo, text="Canal", bg=PANEL_BAJO, fg=MUTED, font=(self.fuente_cuerpo, 8)
        ).pack(anchor="w", pady=(10, 2))
        fila = tk.Frame(cuerpo, bg=PANEL_BAJO)
        fila.pack(fill="x")
        entrada = self._entrada(fila, self.var_canal)
        entrada.pack(side="left", fill="x", expand=True, ipady=3)
        entrada.bind("<Return>", lambda _e: self._guardar_twitch())
        self._boton(fila, "Conectar", self._guardar_twitch).pack(side="left", padx=(8, 0))

        tk.Label(
            cuerpo, text="Client ID", bg=PANEL_BAJO, fg=MUTED, font=(self.fuente_cuerpo, 8)
        ).pack(anchor="w", pady=(10, 2))
        self._entrada(cuerpo, self.var_client_id).pack(fill="x", ipady=3)

        fila_sesion = tk.Frame(cuerpo, bg=PANEL_BAJO)
        fila_sesion.pack(fill="x", pady=(8, 0))
        self.btn_twitch_sesion = self._boton(
            fila_sesion, "Iniciar sesión", self._iniciar_sesion_twitch, primario=True
        )
        self.btn_twitch_sesion.pack(side="left", fill="x", expand=True)
        self._boton(fila_sesion, "Cerrar sesión", self._cerrar_sesion_twitch).pack(
            side="left", padx=(8, 0)
        )

        self.lbl_twitch_cuenta = tk.Label(
            cuerpo,
            text="",
            bg=PANEL_BAJO,
            fg=MUTED,
            font=(self.fuente_cuerpo, 8),
            anchor="w",
            justify="left",
            wraplength=300,
        )
        self.lbl_twitch_cuenta.pack(fill="x", pady=(8, 0))
        cuerpo.bind(
            "<Configure>",
            lambda e: self.lbl_twitch_cuenta.configure(wraplength=max(160, e.width - 4)),
        )

        caja = tk.Frame(cuerpo, bg=INSET, highlightbackground=BORDE, highlightthickness=1)
        caja.pack(fill="both", expand=True, pady=(12, 0))
        tk.Label(
            caja,
            text="COMANDOS",
            bg=INSET,
            fg=TWITCH,
            font=(self.fuente_mono, 8),
        ).pack(anchor="w", padx=8, pady=(8, 4))
        for comando, ayuda in (
            ("!skin", "aleatoria de las que tienes"),
            ("!skin siguiente", "rota a la siguiente"),
            ("!skin PROJECT", "busca por nombre"),
            ("!skin 3", "la número 3 de tu lista"),
        ):
            fila_cmd = tk.Frame(caja, bg=INSET)
            fila_cmd.pack(fill="x", padx=8, pady=1)
            tk.Label(
                fila_cmd,
                text=comando,
                bg=INSET,
                fg=ORO,
                font=(self.fuente_mono, 9),
                width=16,
                anchor="w",
            ).pack(side="left")
            tk.Label(
                fila_cmd,
                text=ayuda,
                bg=INSET,
                fg=MUTED,
                font=(self.fuente_cuerpo, 8),
                anchor="w",
            ).pack(side="left", fill="x")
        tk.Label(
            caja,
            text="Solo skins que ya tienes. Sin sesión el chat se oye; con sesión el bot dice quién la eligió.",
            bg=INSET,
            fg=MUTED,
            font=(self.fuente_cuerpo, 8),
            wraplength=280,
            justify="left",
        ).pack(anchor="w", padx=8, pady=(6, 8))
        self._pintar_cuenta_twitch()
        return marco

    def _pie(self) -> None:
        pie = tk.Frame(self, bg=INSET, highlightbackground=BORDE_SUAVE, highlightthickness=1)
        pie.pack(fill="x", padx=10, pady=(0, 10))
        tk.Label(
            pie,
            text="ACTIVIDAD",
            bg=INSET,
            fg=ORO,
            font=(self.fuente_mono, 8),
        ).pack(side="left", padx=(10, 8), pady=8)
        self.lbl_log = tk.Label(
            pie,
            textvariable=self.var_log,
            bg=INSET,
            fg=TEXTO,
            font=(self.fuente_cuerpo, 9),
            anchor="w",
            justify="left",
        )
        self.lbl_log.pack(side="left", fill="x", expand=True, pady=8)
        self.lbl_bandeja = tk.Label(
            pie,
            text="bandeja activa",
            bg=INSET,
            fg=OK,
            font=(self.fuente_mono, 8),
        )
        self.lbl_bandeja.pack(side="right", padx=10)
        pie.bind("<Configure>", lambda e: self.lbl_log.configure(wraplength=max(200, e.width - 220)))

    def _cabecera_panel(self, marco: tk.Frame, titulo: str, badge: str) -> None:
        cabecera = tk.Frame(marco, bg=TARJETA, height=36)
        cabecera.pack(fill="x")
        cabecera.pack_propagate(False)
        tk.Label(
            cabecera,
            text=titulo,
            bg=TARJETA,
            fg=ORO,
            font=(self.fuente_titulo, 12, "bold"),
        ).pack(side="left", padx=10)
        tk.Label(
            cabecera,
            text=badge,
            bg=INSET,
            fg=MUTED,
            font=(self.fuente_mono, 8),
            padx=6,
        ).pack(side="right", padx=10)

    def _entrada(self, padre: tk.Widget, variable: tk.StringVar) -> tk.Entry:
        return tk.Entry(
            padre,
            textvariable=variable,
            bg=INSET,
            fg=TEXTO,
            insertbackground=ORO,
            relief="flat",
            font=(self.fuente_cuerpo, 10),
            highlightthickness=1,
            highlightbackground=BORDE,
            highlightcolor=ORO,
        )

    def _boton(
        self,
        padre: tk.Widget,
        texto: str,
        comando,
        primario: bool = False,
        peligro: bool = False,
    ) -> tk.Button:
        if primario:
            colores = dict(
                bg=ORO,
                fg=TINTA,
                activebackground=ORO_CLARO,
                activeforeground=TINTA,
                font=(self.fuente_titulo, 10, "bold"),
            )
        elif peligro:
            colores = dict(
                bg="#3a1d18",
                fg="#ffb4ab",
                activebackground="#5a2820",
                activeforeground="white",
                font=(self.fuente_cuerpo, 9),
            )
        else:
            colores = dict(
                bg=TARJETA,
                fg=TEXTO,
                activebackground=HOVER,
                activeforeground=ORO_CLARO,
                font=(self.fuente_cuerpo, 9),
            )
        return tk.Button(
            padre,
            text=texto,
            command=comando,
            relief="flat",
            bd=0,
            cursor="hand2",
            highlightthickness=1,
            highlightbackground=ORO if primario else BORDE,
            highlightcolor=ORO,
            padx=10,
            **colores,
        )

    def _elegir_skin(self, etiqueta: str) -> None:
        self.var_skin.set(etiqueta)
        self._pintar_botones_skin()
        self._guardar_modo_skin()

    def _pintar_botones_skin(self) -> None:
        actual = self.var_skin.get()
        for etiqueta, boton in self._botones_skin.items():
            activo = etiqueta == actual
            boton.configure(
                bg=SELECCION if activo else INSET,
                fg=ORO if activo else MUTED,
                highlightbackground=ORO if activo else BORDE,
            )

    def _foco_busqueda(self, _evento: tk.Event | None = None) -> str:
        self.entrada_busqueda.focus_set()
        self.entrada_busqueda.selection_range(0, "end")
        return "break"

    def _enganchar_rueda(self, widget: tk.Widget) -> None:
        widget.bind("<MouseWheel>", self._rueda_asignaciones)
        for hijo in widget.winfo_children():
            self._enganchar_rueda(hijo)

    def _rueda_asignaciones(self, evento: tk.Event) -> None:
        self.canvas_asignaciones.yview_scroll(int(-1 * (evento.delta / 120)), "units")

    def _arrancar(self) -> None:
        if self.servicio.config.iniciar_con_windows():
            activar_inicio_windows(True)
        self._pintar_configurados()
        self.servicio.iniciar(self._evento_hilo)
        self._actualizar_estado()
        if self.icono_bandeja is None and hasattr(self, "lbl_bandeja"):
            self.lbl_bandeja.configure(text="sin bandeja", fg=ERROR)
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
        elif tipo == "skin":
            if evento.get("usuario"):
                texto = (
                    f"{evento.get('usuario')} eligió '{evento.get('skin_nombre')}' "
                    f"para {evento.get('campeon_nombre')}."
                )
            else:
                texto = (
                    f"Skin '{evento.get('skin_nombre')}' "
                    f"para {evento.get('campeon_nombre')}."
                )
            self._log(texto)
            self._notificar("Skin aplicada", texto)
        elif tipo == "twitch":
            mensaje = str(evento.get("mensaje") or "")
            if evento.get("conectado"):
                self._log(mensaje or "Chat de Twitch conectado.")
            else:
                self._log(mensaje or "Chat de Twitch desconectado.", error=True)
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
        elif tipo == "bloqueo":
            texto = str(evento.get("mensaje") or "Solicitud bloqueada.")
            self._log(texto)
            self._notificar("Solicitud bloqueada", texto)
        elif tipo == "reporte":
            texto = str(evento.get("mensaje") or "Reporte de la partida enviado.")
            self._log(texto)
            self._notificar("Reporte enviado", texto)
        elif tipo == "fase":
            if self.winfo_viewable():
                self._log(f"Fase: {evento.get('fase')}")
        elif tipo == "error":
            self._log(str(evento.get("mensaje") or "Error"), error=True)
        self._pintar_cuenta_twitch()
        self._actualizar_estado()

    def _actualizar_estado(self) -> None:
        if not self.winfo_exists() or not self.winfo_viewable():
            return
        try:
            estado = self.servicio.estado()
        except Exception:
            self.var_estado.set("Sin conexión")
            self.var_lcu.set("LCU · SIN CONEXIÓN")
            self.lbl_estado.configure(fg=ERROR)
            self.lbl_lcu.configure(fg=ERROR)
            self.lbl_punto.configure(fg=ERROR)
            self.lbl_punto_lcu.configure(fg=ERROR)
            return
        if estado.get("conectado"):
            nombre = estado.get("invocador") or "invocador"
            extra = ""
            if estado.get("twitch_habilitado"):
                canal = estado.get("twitch_canal") or ""
                if estado.get("twitch_conectado"):
                    extra = f"  ·  Twitch #{canal}"
                    if estado.get("twitch_puede_hablar"):
                        extra += " (responde)"
                else:
                    extra = "  ·  Twitch…"
            self.var_estado.set(f"Conectado como {nombre}  ·  vigilando{extra}")
            self.var_lcu.set("LCU · CONECTADO")
            self.lbl_estado.configure(fg=OK)
            self.lbl_lcu.configure(fg=OK)
            self.lbl_punto.configure(fg=OK)
            self.lbl_punto_lcu.configure(fg=OK)
        else:
            self.var_estado.set("Cliente de LoL no detectado")
            self.var_lcu.set("LCU · DESCONECTADO")
            self.lbl_estado.configure(fg=ERROR)
            self.lbl_lcu.configure(fg=ERROR)
            self.lbl_punto.configure(fg=ERROR)
            self.lbl_punto_lcu.configure(fg=ERROR)

    def _filtrar_campeones(self) -> None:
        previo = self._campeon_seleccionado()
        previo_id = int(previo["id"]) if previo else None
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
        configurados = {int(item["campeon_id"]) for item in self.servicio.configurados()}
        self.campeones_visibles = visibles
        self.lista_campeones.delete(0, "end")
        for indice, campeon in enumerate(visibles):
            marca = " ●" if int(campeon["id"]) in configurados else ""
            self.lista_campeones.insert(
                "end", f"{_sigla(str(campeon['nombre'])):<3} {campeon['nombre']}{marca}"
            )
            if int(campeon["id"]) in configurados:
                self.lista_campeones.itemconfig(indice, foreground=ORO)
        if previo_id is None:
            return
        for indice, campeon in enumerate(visibles):
            if int(campeon["id"]) == previo_id:
                self.lista_campeones.selection_set(indice)
                self.lista_campeones.see(indice)
                break

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
        total = len(self.configurados_filas)
        self.var_mapeados.set(f"{total} mapeado" if total == 1 else f"{total} mapeados")
        for hijo in self.marco_asignaciones.winfo_children():
            hijo.destroy()
        self._tarjetas.clear()
        if not self.configurados_filas:
            tk.Label(
                self.marco_asignaciones,
                text="Todavía no hay campeones asignados.",
                bg=INSET,
                fg=MUTED,
                font=(self.fuente_cuerpo, 9),
                anchor="w",
            ).pack(fill="x", padx=4, pady=8)
            self._asignacion_sel = None
            return
        ids = {int(item["campeon_id"]) for item in self.configurados_filas}
        if self._asignacion_sel not in ids:
            self._asignacion_sel = None
        modo_skin = self.var_skin.get() or "No cambiar"
        for item in self.configurados_filas:
            self._tarjeta_asignacion(item, modo_skin)
        self._marcar_tarjeta()
        self._enganchar_rueda(self.marco_asignaciones)

    def _tarjeta_asignacion(self, item: dict[str, Any], modo_skin: str) -> None:
        campeon_id = int(item["campeon_id"])
        nombre = str(item.get("campeon_nombre") or campeon_id)
        pagina = str(item.get("pagina_nombre") or "—")
        tarjeta = tk.Frame(
            self.marco_asignaciones,
            bg=TARJETA,
            highlightbackground=BORDE,
            highlightthickness=1,
        )
        tarjeta.pack(fill="x", pady=3)
        self._tarjetas[campeon_id] = tarjeta

        sigla = tk.Label(
            tarjeta,
            text=_sigla(nombre),
            bg=TARJETA,
            fg=ORO,
            font=(self.fuente_mono, 9, "bold"),
            width=3,
        )
        sigla.pack(side="left", padx=(8, 4), pady=8)
        textos = tk.Frame(tarjeta, bg=TARJETA)
        textos.pack(side="left", fill="x", expand=True, pady=6)
        fila_nombre = tk.Frame(textos, bg=TARJETA)
        fila_nombre.pack(anchor="w")
        lbl_nombre = tk.Label(
            fila_nombre,
            text=nombre,
            bg=TARJETA,
            fg=TEXTO,
            font=(self.fuente_cuerpo, 10, "bold"),
        )
        lbl_nombre.pack(side="left")
        lbl_auto = tk.Label(
            fila_nombre,
            text=" auto ",
            bg=INSET,
            fg=OK,
            font=(self.fuente_mono, 7),
        )
        lbl_auto.pack(side="left", padx=(6, 0))
        detalle = tk.Label(
            textos,
            text=f"Página: {pagina}   ·   Skin: {modo_skin}",
            bg=TARJETA,
            fg=MUTED,
            font=(self.fuente_cuerpo, 8),
            anchor="w",
        )
        detalle.pack(anchor="w")
        quitar = tk.Button(
            tarjeta,
            text="✕",
            command=lambda cid=campeon_id: self._quitar_id(cid),
            bg=TARJETA,
            fg=MUTED,
            activebackground=HOVER,
            activeforeground=ERROR,
            relief="flat",
            bd=0,
            font=(self.fuente_cuerpo, 10),
            cursor="hand2",
            padx=6,
        )
        quitar.pack(side="right", padx=4)

        def elegir(_evento: tk.Event | None = None, cid: int = campeon_id) -> None:
            self._asignacion_sel = cid
            self._marcar_tarjeta()
            self._cargar_desde_tabla(cid)

        for widget in (tarjeta, sigla, textos, fila_nombre, lbl_nombre, lbl_auto, detalle):
            widget.bind("<Button-1>", elegir)

    def _marcar_tarjeta(self) -> None:
        for campeon_id, tarjeta in self._tarjetas.items():
            activa = campeon_id == self._asignacion_sel
            tarjeta.configure(highlightbackground=ORO if activa else BORDE, highlightthickness=1)

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
        self._asignacion_sel = int(campeon["id"])
        self._pintar_configurados()
        self._filtrar_campeones()
        self._log(f"{campeon['nombre']} usará la página '{pagina['nombre']}'.")

    def _quitar_id(self, campeon_id: int) -> None:
        self._asignacion_sel = campeon_id
        self._quitar()

    def _quitar(self) -> None:
        if self._asignacion_sel is None:
            messagebox.showinfo("Nada seleccionado", "Elige una asignación de la lista.")
            return
        campeon_id = self._asignacion_sel
        nombre = next(
            (
                i.get("campeon_nombre")
                for i in self.configurados_filas
                if int(i["campeon_id"]) == campeon_id
            ),
            str(campeon_id),
        )
        self.servicio.quitar(campeon_id)
        self._asignacion_sel = None
        self._pintar_configurados()
        self._filtrar_campeones()
        self._log(f"Quité la asignación de {nombre}.")

    def _cargar_desde_tabla(self, campeon_id: int | None = None) -> None:
        if campeon_id is None:
            campeon_id = self._asignacion_sel
        if campeon_id is None:
            return
        self._asignacion_sel = campeon_id
        self._marcar_tarjeta()
        for indice, campeon in enumerate(self.campeones_visibles):
            if int(campeon["id"]) == campeon_id:
                self.lista_campeones.selection_clear(0, "end")
                self.lista_campeones.selection_set(indice)
                self.lista_campeones.see(indice)
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

    def _alternar_bloqueos(self) -> None:
        self.var_bloqueos.set(not self.var_bloqueos.get())
        self._guardar_bloqueos()

    def _guardar_bloqueos(self) -> None:
        activo = bool(self.var_bloqueos.get())
        self.servicio.config.set_bloquear_solicitudes(activo)
        if activo:
            self._log(
                "Bloquearé hasta 3 solicitudes de quien no esté en tus últimas 2 partidas "
                "ni en la sala si estás en cola."
            )
        else:
            self._log("No bloquearé solicitudes de amistad.")

    def _guardar_modo_skin(self) -> None:
        etiqueta = self.var_skin.get()
        modo = next((clave for clave, valor in ETIQUETAS_SKIN.items() if valor == etiqueta), "ninguna")
        self.servicio.set_modo_skin(modo)
        self._pintar_botones_skin()
        if hasattr(self, "marco_asignaciones"):
            self._pintar_configurados()
        if modo == "ninguna":
            self._log("No cambiaré la skin en champ select.")
        elif modo == "aleatoria":
            self._log("En champ select pondré una skin aleatoria de las que tienes.")
        else:
            self._log("En champ select rotaré a la siguiente skin que tengas.")

    def _guardar_twitch(self) -> None:
        canal = self.var_canal.get().strip()
        activo = bool(self.var_twitch.get())
        client_id = self.var_client_id.get().strip()
        if client_id:
            self.servicio.set_twitch_client_id(client_id)
        if activo and not canal:
            self.var_twitch.set(False)
            self._log("Escribe tu canal de Twitch para que el chat elija skins.", error=True)
            return
        try:
            self.servicio.set_twitch(activo, canal)
        except Exception as exc:  # noqa: BLE001
            self._log(str(exc), error=True)
            return
        if activo:
            self._log(f"El chat de #{canal} puede pedir skins con !skin.")
        else:
            self._log("Chat de Twitch desconectado.")
        self._pintar_cuenta_twitch()

    def _pintar_cuenta_twitch(self) -> None:
        if not hasattr(self, "lbl_twitch_cuenta"):
            return
        datos = self.servicio.twitch()
        if not self.var_client_id.get().strip() and datos.get("client_id"):
            self.var_client_id.set(str(datos.get("client_id") or ""))
        if datos.get("canal") and not self.var_canal.get().strip():
            self.var_canal.set(str(datos.get("canal") or ""))
        if datos.get("puede_hablar"):
            self.lbl_twitch_cuenta.configure(
                text=f"Responde en el chat como {datos.get('login')} (quién eligió la skin).",
                fg=OK,
            )
            self.btn_twitch_sesion.configure(text="Volver a iniciar sesión")
            self.lbl_twitch_chip.configure(text="responde", fg=OK, bg="#12301f")
        elif datos.get("habilitado"):
            self.lbl_twitch_cuenta.configure(
                text="Sin sesión: el chat se oye, pero no se responde. Crea una app pública en dev.twitch.tv y pega el Client ID.",
                fg=MUTED,
            )
            self.btn_twitch_sesion.configure(text="Iniciar sesión")
            self.lbl_twitch_chip.configure(text="escucha", fg=TWITCH, bg="#241438")
        else:
            self.lbl_twitch_cuenta.configure(
                text="Sin sesión: el chat se oye, pero no se responde. Crea una app pública en dev.twitch.tv y pega el Client ID.",
                fg=MUTED,
            )
            self.btn_twitch_sesion.configure(text="Iniciar sesión")
            self.lbl_twitch_chip.configure(text="apagado", fg=MUTED, bg=INSET)

    def _iniciar_sesion_twitch(self) -> None:
        client_id = self.var_client_id.get().strip()
        if not client_id:
            messagebox.showinfo(
                "Twitch",
                "Crea una aplicación en https://dev.twitch.tv/console/apps "
                "(tipo Public, OAuth Redirect http://localhost) y pega aquí el Client ID.",
            )
            return
        self.servicio.set_twitch_client_id(client_id)
        if self._dlg_twitch is not None and self._dlg_twitch.winfo_exists():
            self._dlg_twitch.lift()
            return
        self._oauth_cancelar = Event()
        dlg = tk.Toplevel(self)
        dlg.title("Iniciar sesión en Twitch")
        dlg.configure(bg=PANEL)
        dlg.resizable(False, False)
        dlg.transient(self)
        dlg.geometry("460x210")
        self._dlg_twitch = dlg
        borde = tk.Frame(dlg, bg=PANEL, highlightbackground=ORO, highlightthickness=1)
        borde.pack(fill="both", expand=True)
        tk.Label(
            borde,
            text="Iniciar sesión en Twitch",
            bg=PANEL,
            fg=ORO,
            font=(self.fuente_titulo, 13, "bold"),
        ).pack(anchor="w", padx=16, pady=(14, 4))
        tk.Label(
            borde,
            text="Abre el navegador, inicia sesión en Twitch y autoriza la app.",
            bg=PANEL,
            fg=TEXTO,
            font=(self.fuente_cuerpo, 10),
            wraplength=420,
            justify="left",
        ).pack(anchor="w", padx=16, pady=(0, 10))
        var_codigo = tk.StringVar(value="Pidiendo código…")
        caja = tk.Frame(borde, bg=TARJETA, highlightbackground=BORDE, highlightthickness=1)
        caja.pack(fill="x", padx=16)
        tk.Label(
            caja,
            textvariable=var_codigo,
            bg=TARJETA,
            fg=ORO,
            font=(self.fuente_mono, 20, "bold"),
        ).pack(anchor="w", padx=12, pady=8)
        self._boton(borde, "Cancelar", self._cancelar_login_twitch).pack(
            anchor="e", padx=16, pady=12
        )
        dlg.protocol("WM_DELETE_WINDOW", self._cancelar_login_twitch)

        def al_codigo(datos: dict[str, Any]) -> None:
            codigo = str(datos.get("user_code") or "")
            self.after(0, lambda: var_codigo.set(codigo or "Autoriza en el navegador…"))

        def trabajo() -> None:
            try:
                self.servicio.iniciar_sesion_twitch(
                    client_id,
                    al_codigo=al_codigo,
                    cancelar=self._oauth_cancelar,
                )
            except TwitchAuthError as exc:
                texto = str(exc)
                error = "cancelado" not in texto.lower()
                self.after(0, lambda t=texto, e=error: self._login_twitch_fin(t, error=e))
            except Exception as exc:  # noqa: BLE001
                self.after(0, lambda: self._login_twitch_fin(str(exc), error=True))
            else:
                self.after(
                    0,
                    lambda: self._login_twitch_fin(
                        "Listo. Cuando alguien ponga !skin, el chat verá quién eligió y que ya está para esta partida."
                    ),
                )

        Thread(target=trabajo, daemon=True, name="twitch-oauth").start()

    def _cancelar_login_twitch(self) -> None:
        self.servicio.cancelar_login_twitch()
        if self._oauth_cancelar is not None:
            self._oauth_cancelar.set()
        self._cerrar_dlg_twitch()

    def _cerrar_dlg_twitch(self) -> None:
        dlg = self._dlg_twitch
        self._dlg_twitch = None
        if dlg is not None:
            try:
                dlg.destroy()
            except tk.TclError:
                pass

    def _login_twitch_fin(self, mensaje: str, error: bool = False) -> None:
        self._cerrar_dlg_twitch()
        datos = self.servicio.twitch()
        if datos.get("canal"):
            self.var_canal.set(str(datos["canal"]))
        self.var_twitch.set(bool(datos.get("habilitado")))
        self._pintar_cuenta_twitch()
        self._log(mensaje, error=error)

    def _cerrar_sesion_twitch(self) -> None:
        self.servicio.cerrar_sesion_twitch()
        self._pintar_cuenta_twitch()
        self._log("Cerré la sesión de Twitch. El chat ya no responderá.")

    def _aplicar_inicio(self, activo: bool) -> None:
        self.servicio.config.set_iniciar_con_windows(activo)
        activar_inicio_windows(activo)
        self._log(
            "Se iniciará con Windows."
            if activo
            else "Ya no se iniciará al prender la PC."
        )

    def _iniciar_bandeja(self) -> None:
        try:
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
        except Exception as exc:  # noqa: BLE001
            registrar_excepcion(exc)
            self.icono_bandeja = None
            self._log(f"No pude crear el icono de bandeja: {exc}", error=True)

    def _error_tk(self, exc_type, exc, tb) -> None:  # noqa: ANN001
        detalle = "".join(traceback.format_exception(exc_type, exc, tb))
        registrar(detalle)
        try:
            messagebox.showerror("LoL Runas Auto", detalle[-1500:])
        except Exception:
            pass

    def _revisar_pedido_mostrar(self) -> None:
        if consumir_pedido_mostrar():
            self.mostrar()
        if self.winfo_exists():
            self.after(800, self._revisar_pedido_mostrar)

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
