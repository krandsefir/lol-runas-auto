# LoL Runas Auto

Aplicación de Windows que elige **tu** página de runas según el campeón que bloqueas en League of Legends.

Si tienes una página para Warwick y otra para Yone (o Senna, Yorick, etc.) y a veces se te olvida cambiarla, esta app lo hace sola: detecta el campeón en champ select y activa la página que le asignaste.

No usa la API pública de Riot (historial, ranked). Habla con el **cliente local** (LCU), el mismo mecanismo que usan overlays como Porofessor o Blitz. El cliente de LoL tiene que estar abierto para leer y cambiar runas.

## Qué hace

- **Skins:** en champ select puede dejar la skin como está, poner una **aleatoria** de las que tienes, o rotar a la **siguiente**.
- **Chat de Twitch:** si activas el canal, el chat puede pedir una skin con `!skin`. Solo aplica skins que **ya tienes**.
- **Vigila champ select** en segundo plano. Cuando eliges un campeón, busca si tiene una página guardada y la deja seleccionada.
- **No inventa runas.** Usa las páginas que ya tienes en el cliente (`ww`, `SENA`, …).
- **Solo toca campeones configurados.** Si eliges uno que no está en la lista, no cambia nada.
- **Bandeja del sistema.** Arranca minimizado en los iconos ocultos (`^`). Cerrar la ventana no cierra el programa.
- **Inicio con Windows.** Opcional; al prender el PC espera en la bandeja, sin ventana.
- **Una sola instancia.** Si la abres otra vez, trae al frente la que ya está corriendo.
- **Aviso al aplicar.** Cuando cambia la página, muestra una notificación de Windows.
- **Poco uso en reposo.** Si LoL no está abierto, consulta cada ~8 s. Fuera de champ select, cada ~3 s. En champ select, cada ~1 s.

## Cómo se usa

1. Abre el cliente de LoL e inicia sesión.
2. Abre LoL Runas Auto (atajo del escritorio o el `.exe`).
3. Clic en el icono de la bandeja → **Configurar** (o abre el atajo, que muestra la ventana).
4. A la izquierda, **busca el campeón**, selecciónalo, elige la **página de runas** y pulsa **Guardar asignación**.
5. A la derecha ves **lo ya configurado**. Selecciona una fila y **Quitar seleccionado** para borrarla.
6. En **Skin en champ select** elige *No cambiar*, *Aleatoria* o *Siguiente* (solo skins que ya tienes).
7. Si streameas: marca **Escuchar chat**, escribe tu canal de Twitch y pulsa **Conectar**.
8. Marca **Iniciar con Windows** si quieres que arranque sola.
9. Cierra la ventana: sigue vigilando. Para apagarla del todo: clic derecho en el icono → **Salir**.

En la siguiente cola, si bloqueas Warwick y lo tenías asignado a `ww`, esa página se activa sola.

**Actualizar** recarga las páginas desde el cliente (útil si acabas de crear o renombrar una).

## Chat de Twitch (elegir skin)

El chat puede pedir una skin con `!skin`. Solo aplica skins que **ya tienes**.

Para **escuchar** el chat no hace falta cuenta: se une como espectador. Para que **responda** quién eligió la skin y confirme que ya quedó para esa partida, hay que iniciar sesión (bot).

### Escuchar el chat

1. Marca **Escuchar chat**.
2. Pon el nombre de tu canal (`krandsefir` o el enlace de Twitch).
3. Pulsa **Conectar**. En el estado debería verse `Twitch #tu_canal`.

### Que el bot responda en el chat

1. En [dev.twitch.tv/console/apps](https://dev.twitch.tv/console/apps) crea una aplicación:
   - **OAuth Redirect URLs:** `http://localhost`
   - **Client type:** **Public** (no Confidential)
2. Copia el **Client ID** y pégalo en LoL Runas Auto.
3. Pulsa **Iniciar sesión**. Se abre el navegador de Twitch; autoriza (con la cuenta del canal, o un bot que sea moderador).
4. Cuando esté listo verás *Responde en el chat como tu_cuenta*.

Al aplicar la skin, el chat verá algo como:

`@ana eligió PROJECT: Warwick para Warwick. Skin seleccionada para esta partida.`

La sesión se guarda en el PC y se renueva sola. Si pasa mucho tiempo inactiva (~30 días) hay que volver a iniciar sesión.

Comandos:

| Comando | Qué hace |
|---|---|
| `!skin` o `!skin aleatoria` | Una skin aleatoria de las que tienes |
| `!skin siguiente` | La siguiente en tu inventario |
| `!skin PROJECT` | Busca por nombre (parcial, sin importar mayúsculas) |
| `!skin 3` | La 3.ª skin de la lista que tienes |

Si piden la skin **antes** de champ select, se guarda y se aplica cuando elijas campeón. Hay un pequeño enfriamiento (~4 s) para que no spameen. Si el nombre no coincide con una skin tuya, no cambia nada y el bot lo dice en el chat.

El comando por defecto es `!skin`. El chat **no** cambia runas ni elige campeón.

No compartas el `config.json`: ahí queda el token de Twitch.

## Instalación (release)

1. Descarga [LoLRunasAuto-windows.zip](https://github.com/krandsefir/lol-runas-auto/releases/latest).
2. Descomprímelo (tiene que quedar `LoLRunasAuto.exe` junto a la carpeta `_internal`).
3. Ejecuta `LoLRunasAuto.exe`.

El instalador de desarrollo (`python build_exe.py`) además copia el programa a `%LOCALAPPDATA%\LoLRunasAuto\`, crea atajo en el escritorio y lo deja en el inicio de Windows.

## Desarrollo

```powershell
cd lol-runas-auto
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

| Comando | Qué hace |
|---|---|
| `python main.py` | Ventana de configuración + vigilancia |
| `python main.py --bandeja` | Solo bandeja (como al arrancar Windows) |
| `python main.py --consola` | Vigilancia en consola, sin GUI |
| `python build_exe.py` | Genera el `.exe`, lo instala y lo deja en inicio |

Requisitos: Windows, Python 3, cliente de LoL.

## Cómo funciona por dentro

1. Encuentra el cliente por el `lockfile` de League o por el proceso `LeagueClientUx.exe`.
2. Lee la fase del juego (`Matchmaking`, `ChampSelect`, etc.).
3. En champ select, obtiene el campeón elegido.
4. Si hay un mapeo campeón → página, pone esa página como actual. Si el modo de skin no es “No cambiar”, elige una skin **que ya tengas** (aleatoria o la siguiente) y la aplica en champ select. Si el chat de Twitch pidió una skin, esa petición tiene prioridad.

Los mapeos se guardan en:

- desarrollo: `data/config.json`
- ejecutable: `%APPDATA%\LoLRunasAuto\config.json`

La lista de campeones sale del cliente o, si no está abierto, de Data Dragon. Las páginas de runas **sí** necesitan el cliente abierto.

## Limitaciones

- No está hecha ni respaldada por Riot. La LCU puede cambiar en un parche.
- No aplica runas “meta” de u.gg/op.gg: solo las tuyas.
- Las skins aleatorias/siguientes (y las del chat de Twitch) son solo las que **ya tienes**; no desbloquea ni compra nada.
- El chat de Twitch es solo lectura hasta que inicies sesión; entonces responde quién eligió la skin. No pide la contraseña de Twitch (usas Authorize en el navegador).
- No elige campeón, no acepta cola, no cambia hechizos.
- En Corea Riot restringe apps LCU.

## Licencia

Uso personal. League of Legends es marca de Riot Games.
