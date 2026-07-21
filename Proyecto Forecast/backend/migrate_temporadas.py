"""
Limpia temporadas: deja solo los 4 tipos genéricos.
Reasigna productos/forecast a los nuevos IDs antes de borrar.
"""
import asyncio
import asyncpg
import os

DSN = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/forecast_dcic")

TIPOS = [
    'Verano',
    'Invierno',
    'No Estacional',
    'Verano/Rotativo',
]

async def run():
    conn = await asyncpg.connect(DSN)

    # 1. Insertar los 4 tipos si no existen
    for nombre in TIPOS:
        exists = await conn.fetchval("SELECT id FROM temporadas WHERE nombre=$1", nombre)
        if not exists:
            await conn.execute(
                "INSERT INTO temporadas (nombre, fecha_inicio, fecha_fin) VALUES ($1, NULL, NULL)",
                nombre
            )
            print(f"  INSERTED {nombre}")
        else:
            print(f"  EXISTS   {nombre} (id={exists})")

    # 2. Obtener IDs de los 4 tipos
    tipos_ids = {}
    for nombre in TIPOS:
        tid = await conn.fetchval("SELECT id FROM temporadas WHERE nombre=$1", nombre)
        tipos_ids[nombre] = tid
    print(f"\n  IDs: {tipos_ids}")

    # 3. Reasignar productos que apuntan a temporadas con año
    #    La logica: si el nombre contiene 'Verano' -> Verano, 'Invierno' -> Invierno, etc.
    old_temps = await conn.fetch(
        "SELECT id, nombre FROM temporadas WHERE nombre NOT IN ('Verano','Invierno','No Estacional','Verano/Rotativo')"
    )
    for t in old_temps:
        nombre_viejo = t['nombre']
        tid_viejo = t['id']

        # Determinar tipo equivalente
        if 'No Estacional' in nombre_viejo:
            nuevo = 'No Estacional'
        elif 'Rotativo' in nombre_viejo:
            nuevo = 'Verano/Rotativo'
        elif 'Verano' in nombre_viejo:
            nuevo = 'Verano'
        elif 'Invierno' in nombre_viejo:
            nuevo = 'Invierno'
        else:
            nuevo = None

        if nuevo:
            tid_nuevo = tipos_ids[nuevo]
            r1 = await conn.execute(
                "UPDATE productos SET temporada_id=$1 WHERE temporada_id=$2",
                tid_nuevo, tid_viejo
            )
            r2 = await conn.execute(
                "UPDATE forecast SET temporada_id=$1 WHERE temporada_id=$2",
                tid_nuevo, tid_viejo
            )
            print(f"  REMAP [{tid_viejo}] {nombre_viejo:<28} -> {nuevo}  (prod:{r1}, fc:{r2})")

    # 4. Borrar temporadas con año
    deleted = await conn.execute(
        "DELETE FROM temporadas WHERE nombre NOT IN ('Verano','Invierno','No Estacional','Verano/Rotativo')"
    )
    print(f"\n  DELETED old temporadas: {deleted}")

    # 5. Resultado final
    print("\nTemporadas finales:")
    rows = await conn.fetch("SELECT id, nombre FROM temporadas ORDER BY id")
    for r in rows:
        cnt = await conn.fetchval("SELECT COUNT(*) FROM productos WHERE temporada_id=$1", r['id'])
        print(f"  [{r['id']}] {r['nombre']:<20} productos: {cnt}")

    await conn.close()

asyncio.run(run())
