import asyncio
import asyncpg
import os

async def run():
    conn = await asyncpg.connect(os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/forecast_dcic"))
    await conn.execute("ALTER TABLE productos ADD COLUMN IF NOT EXISTS tipo VARCHAR(20) DEFAULT 'Producto'")
    await conn.close()
    print('OK - columna tipo agregada')

asyncio.run(run())
