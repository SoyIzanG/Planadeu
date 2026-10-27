# Sincronización automática de Juvenil Segona Divisió — Grup 29

Este repositorio incorpora una tarea de GitHub Actions que consulta diariamente Futbuteo y sincroniza el calendario/resultados con la temporada **2026-2027** en Supabase.

## Seguridad de los datos

- La tarea revisa individualmente las páginas `?j=5` a `?j=34`; el mapeo es `j=5 → jornada interna 1`, `j=6 → jornada 2`, etc.
- Solo considera una jornada completa si detecta **7 partidos**, 14 equipos distintos y el equipo que descansa, cubriendo exactamente los 15 equipos oficiales.
- Si la web no responde, cambia su HTML o falta un partido, la jornada se omite sin insertar datos parciales.
- No borra equipos, usuarios, jugadores, partidos ni eventos.
- No sustituye un resultado ya guardado por un marcador vacío.
- La UE Planadeu se excluye de los 15 equipos oficiales para la validación del descanso.
- Los eventos de acta no se inventan ni se extraen con este sincronizador. Los goles/actas detalladas deben añadirse solo cuando una fuente verificable los publique.
- La tarea informa en los logs de GitHub Actions qué jornadas se verificaron y cuáles se omitieron.

## Activación

1. En GitHub, abre **Settings → Secrets and variables → Actions** del repositorio.
2. Crea un secret llamado `DATABASE_URL` con la cadena de conexión PostgreSQL de Supabase (usa la cadena de conexión recomendada por Supabase; no la publiques en el código).
3. Abre **Actions → Actualización diaria de la liga → Run workflow** para probarla manualmente.
4. Revisa el resumen/log del trabajo. Si Futbuteo cambia el diseño y no se detectan las tarjetas de partidos o el descanso, la tarea fallará de forma conservadora y no escribirá esa jornada.

## Fuente

- Futbuteo: https://futbuteo.com/catalunya/resultados/juvenil-segona-divisio/grup-29/
- FCF: https://www.fcf.cat/

La tarea se ejecuta diariamente a las 06:20 UTC. GitHub puede retrasar la hora de inicio de trabajos programados en periodos de carga.
