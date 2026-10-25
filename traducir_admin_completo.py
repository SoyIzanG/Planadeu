
from pathlib import Path
import shutil

carpeta = Path("app/templates/admin")

traducciones = {
    # Títulos y navegación
    "Analytics - Administración": "Estadísticas - Administración",
    "Visitor Analytics": "Estadísticas de visitas",
    "Fan Comments - Administración": "Comentarios - Administración",
    "Fan Comments Management": "Gestión de comentarios",
    "Gallery Management - Administración": "Gestión de la galería - Administración",
    "Gallery Management": "Gestión de la galería",
    "Fixtures - Administración": "Partidos - Administración",
    "Fixtures": "Partidos",
    "Analytics": "Estadísticas",

    # Botones
    "Manage Gallery": "Gestionar galería",
    "Manage": "Gestionar",
    "Moderate": "Moderar comentarios",
    "View Stats": "Ver estadísticas",
    "View": "Ver",
    "Clear": "Limpiar búsqueda",
    "Back to Gallery": "Volver a la galería",
    "Current image:": "Imagen actual:",
    "Current:": "Actual:",
    "Add Season": "Añadir temporada",
    "Add Team": "Añadir equipo",
    "Add Player": "Añadir jugador",

    # Comentarios
    "Comments List": "Lista de comentarios",
    "Comments (": "Comentarios (",
    "Comment Details": "Detalles del comentario",
    "Comment:": "Comentario:",
    "Approved": "Aprobado",
    "Pending": "Pendiente",
    "Length:": "Longitud:",
    "chars": "caracteres",
    "No fan comments found": "No se han encontrado comentarios",
    "No fan comments have been posted yet.": "Todavía no se ha publicado ningún comentario.",
    "Comments pagination": "Paginación de comentarios",

    # Galería
    "No gallery items found": "No se han encontrado elementos en la galería",
    "Start by adding your first gallery item!": "¡Empieza añadiendo el primer elemento a la galería!",
    "Highlight": "Momento destacado",
    "Story": "Historia",
    "Event": "Evento",
    "No match association": "Sin partido asociado",
    "Current image:": "Imagen actual:",
    "View": "Ver",
    "Featured items will be displayed prominently on the gallery page and may appear in special sections.":
        "Los elementos destacados aparecerán de forma visible en la galería y podrían mostrarse en secciones especiales.",
    "Story: League news, player stories, events":
        "Historia: noticias de la liga, historias de jugadores y eventos",
    "Gallery pagination": "Paginación de la galería",

    # Jugadores y posiciones
    "Goalkeeper": "Portero",
    "Defender": "Defensa",
    "Midfielder": "Centrocampista",
    "Forward": "Delantero",
    "e.g. 25": "Por ejemplo, 25",

    # Temporadas y equipos
    "Active season": "Temporada activa",
    "Delete?": "¿Eliminar?",
    "Are you sure?": "¿Estás seguro?",
    
    # Resultados y eventos
    "Enter Result:": "Introducir resultado:",
    "Add events in order. Firstly, select the option of the event and click on add event. Then fill in the new fields. ":
        "Añade los eventos en orden. Primero, selecciona el tipo de evento y pulsa el botón para añadirlo. Después, completa los nuevos campos. ",
    "Do not fill in the first boxes but use it to generate the type of events.":
        "No rellenes los primeros campos: utilízalos para generar los tipos de eventos.",
    "For goals: select scorer and optionally assist, the checkbox for own goal or penalty.":
        "Para los goles: selecciona al goleador y, si corresponde, al asistente. Marca la casilla si es en propia puerta o de penalti.",
    "For cards: select player.": "Para las tarjetas: selecciona al jugador.",
    "For sub: select both players.": "Para las sustituciones: selecciona a ambos jugadores.",
    "If error occurs, refresh the page and start all over.":
        "Si se produce un error, actualiza la página y vuelve a empezar.",
    "Save Result": "Guardar resultado",

    # Estadísticas
    "No page data available": "No hay datos de páginas disponibles",
    "About This Analytics": "Acerca de estas estadísticas",
    "No personal data stored": "No se almacenan datos personales",
    "Data used for analytics only": "Los datos se utilizan únicamente para elaborar estadísticas",
}

for archivo in carpeta.rglob("*.html"):
    contenido = archivo.read_text(encoding="utf-8")
    original = contenido

    # Crear copia de seguridad sin sobrescribir una anterior
    copia = archivo.with_suffix(archivo.suffix + ".antes_traduccion.bak")
    if contenido != original and not copia.exists():
        shutil.copy2(archivo, copia)

    for ingles, espanol in traducciones.items():
        contenido = contenido.replace(ingles, espanol)

    if contenido != original:
        if not copia.exists():
            shutil.copy2(archivo, copia)
        archivo.write_text(contenido, encoding="utf-8")
        print(f"Traducido: {archivo}")

print("Revisión de traducciones terminada.")
