
from pathlib import Path

carpeta = Path("app/templates")

traducciones = {
    "Statistics": "Estadísticas",
    "Top Scorers": "Máximos goleadores",
    "Top Assists": "Máximos asistentes",
    "Clean Sheets (GK/DEF)": "Porterías a cero (porteros/defensas)",
    "Most Cards": "Jugadores con más tarjetas",
    "No data": "Sin datos",
    "Fixtures & Results": "Partidos y resultados",
    "League Table": "Clasificación de la liga",
    "Portal de competición": "Portal de competición",
}

for archivo in carpeta.rglob("*.html"):
    contenido = archivo.read_text(encoding="utf-8")
    original = contenido

    for ingles, espanol in traducciones.items():
        contenido = contenido.replace(ingles, espanol)

    if contenido != original:
        archivo.write_text(contenido, encoding="utf-8")
        print(f"Traducido: {archivo}")

print("Traducción terminada.")
