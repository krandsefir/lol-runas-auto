"""App para aplicar automáticamente tu página de runas según el campeón.

Uso desde la GUI (cuando la armes):

    from runas_auto import ServicioRunas

    def al_evento(evento):
        print(evento)

    servicio = ServicioRunas()
    servicio.iniciar(al_evento=al_evento)

    # Buscar campeón y asignar una página tuya:
    servicio.buscar_campeones("war")
    servicio.paginas_runas()
    servicio.asignar(campeon_id=19, pagina_id=123)
    servicio.configurados()
    servicio.quitar(19)

    servicio.detener()
"""

from runas_auto.servicio import ServicioRunas

__all__ = ["ServicioRunas"]
