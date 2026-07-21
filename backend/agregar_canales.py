"""
Agrega los canales disponibles en la API que aún no están en canal_mapeo.
Ejecutar: python agregar_canales.py
"""
import asyncio
import asyncpg
import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/forecast_dcic")

CANALES_NUEVOS = [
    "Pérgolas",
    "Venta en Verde",
    "Comerc. Dcic Spa",
    "Rebajas",
]

async def main():
    conn = await asyncpg.connect(DATABASE_URL)

    # Ver estado actual
    print("=== Estado actual de canal_mapeo ===")
    rows = await conn.fetch("SELECT canal_id, nombre_api FROM canal_mapeo ORDER BY canal_id")
    for r in rows:
        print(f"  [{r['canal_id']}] {r['nombre_api']}")

    # Ver estructura de la tabla canales
    print("\n=== Tabla canales ===")
    canales = await conn.fetch("SELECT * FROM canales ORDER BY id")
    for c in canales:
        print(f"  {dict(c)}")

    # Canales ya mapeados
    mapeados = {r['nombre_api'] for r in rows}
    por_agregar = [c for c in CANALES_NUEVOS if c not in mapeados]

    if not por_agregar:
        print("\nTodos los canales ya están mapeados. Nada que hacer.")
        await conn.close()
        return

    print(f"\nCanales a agregar: {por_agregar}")

    # Insertar en tabla canales y luego en canal_mapeo
    for nombre in por_agregar:
        # Verificar si ya existe en tabla canales
        existing = await conn.fetchrow("SELECT id FROM canales WHERE nombre = $1", nombre)
        if existing:
            canal_id = existing['id']
            print(f"  '{nombre}' ya existe en canales con id={canal_id}")
        else:
            canal_id = await conn.fetchval(
                "INSERT INTO canales (nombre) VALUES ($1) RETURNING id", nombre
            )
            print(f"  '{nombre}' insertado en canales con id={canal_id}")

        await conn.execute(
            "INSERT INTO canal_mapeo (nombre_api, canal_id) VALUES ($1, $2) ON CONFLICT (nombre_api) DO NOTHING",
            nombre, canal_id
        )
        print(f"  -> canal_mapeo: '{nombre}' -> canal_id={canal_id}")

    print("\n=== canal_mapeo actualizado ===")
    rows = await conn.fetch("SELECT canal_id, nombre_api FROM canal_mapeo ORDER BY canal_id")
    for r in rows:
        print(f"  [{r['canal_id']}] {r['nombre_api']}")

    await conn.close()

asyncio.run(main())
