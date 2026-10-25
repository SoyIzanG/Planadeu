
from pathlib import Path
import shutil

carpeta = Path("app/templates")

traducciones = {
    "Admin Dashboard": "Panel de administración",
    "Admin Login": "Acceso de administrador",
    "Login - League Site": "Acceso - Liga de Fútbol",
    "Login": "Iniciar sesión",
    "Logout": "Cerrar sesión",
    "Dashboard": "Panel de administración",

    "Search by name, nickname, or comment...":
        "Buscar por nombre, apodo o comentario...",
    "Search gallery...": "Buscar en la galería...",
    "Search highlights...": "Buscar momentos destacados...",
    "Search stories...": "Buscar historias...",
    "Search...": "Buscar...",
    "Search": "Buscar",

    "Are you sure you want to delete this comment?":
        "¿Seguro que quieres eliminar este comentario?",
    "Are you sure you want to delete this gallery item?":
        "¿Seguro que quieres eliminar este elemento de la galería?",
    "Delete Comment": "Eliminar comentario",
    "Delete": "Eliminar",
    "Delete?": "¿Eliminar?",

    "Edit Result": "Editar resultado",
    "Edit Fixture": "Editar partido",
    "Schedule Fixture": "Programar partido",
    "Update Fixture": "Actualizar partido",
    "Schedule": "Programar",
    "Edit Gallery Item": "Editar elemento de la galería",
    "Add Gallery Item": "Añadir elemento a la galería",
    "Update Gallery Item": "Actualizar elemento de la galería",
    "Gallery Item": "Elemento de la galería",
    "Register": "Registrar",
    "Edit": "Editar",
    "Add": "Añadir",
    "Player": "Jugador",
    "Season": "Temporada",
    "Team": "Equipo",

    "Save Result": "Guardar resultado",
    "Save": "Guardar",
    "Cancel": "Cancelar",
    "Submit": "Enviar",
    "Previous": "Anterior",
    "Next": "Siguiente",

    "No comments match your search criteria.":
        "Ningún comentario coincide con la búsqueda.",
    "No fixtures. Add a season first, then schedule fixtures.":
        "No hay partidos. Añade primero una temporada y después programa los encuentros.",
    "No standings available. Add a season and teams to get started.":
        "Todavía no hay clasificación. Añade una temporada y equipos para empezar.",
    "No fixtures. Add a season and schedule matches.":
        "No hay partidos. Añade una temporada y programa los encuentros.",

    "<!-- Search -->": "<!-- Búsqueda -->",
    "<!-- Filter and Search -->": "<!-- Filtros y búsqueda -->",
}

if not carpeta.exists():
    raise SystemExit(
        "No se encuentra app/templates. Ejecuta el script desde la carpeta del proyecto."
    )

archivos = list(carpeta.rglob("*.html"))
modificados = 0

for archivo in archivos:
    try:
        contenido = archivo.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        contenido = archivo.read_text(encoding="utf-8-sig")

    original = contenido

    for ingles, espanol in traducciones.items():
        contenido = contenido.replace(ingles, espanol)

    if contenido != original:
        copia = archivo.with_suffix(archivo.suffix + ".bak")
        if not copia.exists():
            shutil.copy2(archivo, copia)

        archivo.write_text(contenido, encoding="utf-8")
        print(f"Traducido: {archivo}")
        modificados += 1

print()
print(f"Archivos revisados: {len(archivos)}")
print(f"Archivos modificados: {modificados}")
print("Se han guardado copias .bak de los archivos modificados.")
