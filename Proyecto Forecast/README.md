# Forecast DCIC

Sistema de gestión de Forecast, Productos, Packs, Ventas y Stock.

## Stack Técnico
- **Base de Datos**: PostgreSQL
- **Backend**: Python + FastAPI (async)
- **Frontend**: React + Vite (próximo paso)

---

## Estructura del Proyecto

```
forecast-dcic/
├── database/
│   └── schema.sql          ← Esquema PostgreSQL completo
├── backend/
│   ├── main.py             ← App FastAPI
│   ├── database.py         ← Conexión PostgreSQL async
│   ├── requirements.txt
│   ├── models/
│   │   └── models.py       ← Modelos SQLAlchemy
│   ├── schemas/
│   │   └── schemas.py      ← Schemas Pydantic v2
│   └── routers/
│       ├── temporadas.py
│       ├── marcas.py
│       ├── categorias.py
│       ├── productos.py
│       ├── packs.py
│       ├── forecast.py     ← Incluye vista pivot y bulk-upsert
│       ├── ventas.py       ← Incluye carga masiva
│       └── stock.py        ← Calcula stock total automático
└── frontend/               ← Por construir (React)
```

---

## Setup Paso a Paso

### 1. Crear la base de datos PostgreSQL

```bash
psql -U postgres
CREATE DATABASE forecast_dcic;
\c forecast_dcic
\i database/schema.sql
```

### 2. Configurar variables de entorno

Crear archivo `.env` en `/backend/`:

```env
DATABASE_URL=postgresql+asyncpg://postgres:TU_PASSWORD@localhost:5432/forecast_dcic
```

### 3. Instalar dependencias Python

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 4. Levantar el backend

```bash
uvicorn main:app --reload --port 8000
```

API disponible en: http://localhost:8000  
Documentación Swagger: http://localhost:8000/docs

---

## Modelo de Datos

### Relaciones clave
- `productos` → pertenece a `marcas`, `categorias`, `temporadas`
- `packs` → pertenece a `marcas`, `categorias`, `temporadas`
- `pack_componentes` → relaciona `packs` con `productos` (N:M con cantidad)
- `forecast` → un registro por `(sku, año, mes)`
- `ventas` → historial de ventas por `sku` y `fecha`
- `stock` → un registro por `sku` con todas las bodegas

### Campos de Stock
| Campo | Descripción |
|-------|-------------|
| `stock_base` | Bodega propia |
| `stock_full_ml` | Full Fulfillment Mercado Libre |
| `stock_full_fala` | Full Fulfillment Falabella |
| `bodega_transito` | En tránsito (con ETA) |
| `por_arribar` | Confirmado, pendiente llegada |
| `pi` | Purchase Intent / pre-compra |

---

## API Endpoints

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/api/productos/` | Lista todos los productos |
| POST | `/api/productos/` | Crea producto |
| GET | `/api/packs/` | Lista packs con componentes |
| POST | `/api/packs/` | Crea pack con componentes |
| GET | `/api/forecast/?anio=2026` | Forecast por año |
| GET | `/api/forecast/pivot?anio=2026` | Forecast en formato pivot (12 meses) |
| POST | `/api/forecast/bulk-upsert` | Carga masiva de forecast |
| GET | `/api/ventas/` | Ventas con filtros |
| POST | `/api/ventas/bulk` | Carga masiva de ventas |
| GET | `/api/stock/` | Stock completo con totales |
| PUT | `/api/stock/{sku}` | Actualiza stock de un SKU |

---

## Próximos Pasos
1. ✅ Base de datos + Backend
2. ⬜ Carga del archivo Forecast 2026 (Excel)
3. ⬜ Frontend React
4. ⬜ Módulo de cálculos (cobertura, quiebre, etc.)
