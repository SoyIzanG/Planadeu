
from pathlib import Path

carpeta = Path("app/templates")

correcciones = {
    "Editarar resultado": "Editar resultado",
    "Editarar partido": "Editar partido",
    "Editarar elemento de la galería": "Editar elemento de la galería",
    "No fixtures. Añadir a season first, then schedule fixtures.":
        "No hay partidos. Añade primero una temporada y después programa los encuentros.",
    "No standings available. Añadir a season and teams to get started.":
        "Todavía no hay clasificación. Añade una temporada y equipos para empezar.",
    "No fixtures. Añadir a season and schedule matches.":
        "No hay partidos. Añade una temporada y programa los encuentros.",
    "No comments yet": "Todavía no hay comentarios",
    "Admin": "Administración",
}

for archivo in carpeta.rglob("*.html"):
    contenido = archivo.read_text(encoding="utf-8")
    original = contenido

    for ingles, espanol in correcciones.items():
        contenido = contenido.replace(ingles, espanol)

    if contenido != original:
        archivo.write_text(contenido, encoding="utf-8")
        print(f"Corregido: {archivo}")

print("Correcciones terminadas.")
