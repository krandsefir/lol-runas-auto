# LoL Runas Auto

Aplica tu página de runas al elegir un campeón. Corre en segundo plano, en los iconos ocultos de Windows.

## Ejecutable

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python build_exe.py
```

Eso deja:

- `C:\Users\Krandsefir\AppData\Local\LoLRunasAuto\LoLRunasAuto.exe`
- atajo en el Escritorio
- arranque automático al prender la PC (bandeja, sin ventana)

Clic en el icono de la bandeja: **Configurar**. Cerrar la ventana no cierra el programa; **Salir** en el icono sí.

## Desarrollo

```powershell
python main.py
python main.py --bandeja
```
