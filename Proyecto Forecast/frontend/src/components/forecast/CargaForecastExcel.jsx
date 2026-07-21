import { useState, useRef } from "react"
import { cargaForecastExcel } from "../../services/api"

const MESES = ['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic']

export default function CargaForecastExcel({ onExito }) {
  const [archivo,   setArchivo]   = useState(null)
  const [anio,      setAnio]      = useState(2026)
  const [drag,      setDrag]      = useState(false)
  const [loading,   setLoading]   = useState(false)
  const [resultado, setResultado] = useState(null)
  const [error,     setError]     = useState("")
  const inputRef = useRef()

  function seleccionar(file) {
    if (!file) return
    if (!file.name.match(/\.xlsx?$/i)) {
      setError("Solo se aceptan archivos .xlsx"); return
    }
    setArchivo(file)
    setError("")
    setResultado(null)
  }

  async function cargar() {
    if (!archivo) return
    setLoading(true); setError(""); setResultado(null)
    try {
      const res = await cargaForecastExcel(archivo, anio)
      setResultado(res)
      if (res.creados > 0 || res.actualizados > 0) onExito?.()
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  function limpiar() {
    setArchivo(null); setResultado(null); setError("")
    if (inputRef.current) inputRef.current.value = ""
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>

      {/* Referencia de estructura ───────────────────────────── */}
      <div className="card" style={{ padding: "18px 22px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
          <div style={{ fontWeight: 600, fontSize: 14 }}>Estructura de la plantilla Excel</div>
          <a
            href="/Plantilla_Forecast_2026.xlsx"
            download
            className="btn btn-secondary btn-sm"
            style={{ textDecoration: "none" }}
          >
            ⬇ Descargar plantilla
          </a>
        </div>

        {/* Mini-tabla ejemplo */}
        <div style={{ overflowX: "auto", marginBottom: 12 }}>
          <table style={{ fontSize: 11, width: "auto", borderCollapse: "collapse" }}>
            <thead>
              <tr>
                {['SKU','Descripción','Temporada', ...MESES, 'TOTAL'].map(h => (
                  <th key={h} style={{
                    background: h === 'SKU' || h === 'TOTAL' ? 'var(--bg)' : 'var(--bg3)',
                    padding: '5px 10px', border: '1px solid var(--border)',
                    color: 'var(--text2)', fontWeight: 600, whiteSpace: 'nowrap'
                  }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {[
                ['DCX-001','Tabla SUP 10.6','Verano',        0,0,0,0,0,0,0,0,150,120,200,180,650],
                ['DCX-045','Chaleco Neo M', 'Invierno',       0,0,80,90,100,110,95,85,0,0,0,0,560],
                ['DCX-112','Kayak 2P',      'No Estacional', 30,25,35,40,45,40,38,42,50,55,60,50,510],
              ].map((fila, ri) => (
                <tr key={ri} style={{ background: ri % 2 === 0 ? 'var(--bg2)' : 'var(--bg)' }}>
                  {fila.map((v, ci) => (
                    <td key={ci} style={{
                      padding: '5px 10px', border: '1px solid var(--border)',
                      fontFamily: ci > 2 ? 'var(--mono)' : 'inherit',
                      color: ci === 0 ? 'var(--accent)' :
                             ci === 2 ? 'var(--warn)' :
                             (typeof v === 'number' && v === 0) ? 'var(--text3)' : 'var(--text)',
                      fontWeight: ci === 0 || ci === 15 ? 600 : 400,
                      textAlign: ci > 2 ? 'center' : 'left',
                      whiteSpace: 'nowrap'
                    }}>{v}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "6px 24px", fontSize: 12, color: "var(--text2)" }}>
          <div>• <strong>Fila 1–3:</strong> título y cabeceras — no modificar</div>
          <div>• <strong>Col A:</strong> SKU exacto del catálogo DCIC</div>
          <div>• <strong>Fila 4+:</strong> un SKU por fila</div>
          <div>• <strong>Col D–O:</strong> cantidades enteras ≥ 0 (Ene→Dic)</div>
          <div>• <strong>Meses sin venta:</strong> dejar en 0, no vacío</div>
          <div>• <strong>Col C:</strong> Temporada con dropdown validado</div>
        </div>
      </div>

      {/* Opciones de carga ──────────────────────────────────── */}
      <div className="card" style={{ padding: "16px 22px" }}>
        <div style={{ display: "flex", gap: 20, alignItems: "flex-end" }}>
          <div className="form-group" style={{ minWidth: 120 }}>
            <label className="form-label">Año del forecast</label>
            <select className="form-select" value={anio}
              onChange={e => setAnio(Number(e.target.value))}>
              <option value={2025}>2025</option>
              <option value={2026}>2026</option>
              <option value={2027}>2027</option>
            </select>
          </div>
          <div style={{ fontSize: 12, color: "var(--text2)", paddingBottom: 10 }}>
            Los datos del Excel se cargarán para el año <strong style={{ color: "var(--accent)" }}>{anio}</strong>.
            Si ya existe un valor para un SKU/mes lo sobreescribe.
          </div>
        </div>
      </div>

      {/* Drop zone ──────────────────────────────────────────── */}
      <div
        className={`upload-zone ${drag ? "drag" : ""}`}
        onClick={() => inputRef.current?.click()}
        onDragOver={e => { e.preventDefault(); setDrag(true) }}
        onDragLeave={() => setDrag(false)}
        onDrop={e => { e.preventDefault(); setDrag(false); seleccionar(e.dataTransfer.files[0]) }}
      >
        <div className="upload-icon">{archivo ? "📊" : "📂"}</div>
        <div className="upload-text">
          {archivo ? "Archivo listo para cargar" : "Arrastra la plantilla Excel aquí"}
        </div>
        <div className="upload-hint">
          {archivo ? "Haz clic en Cargar para procesar" : "o haz clic para seleccionar · Solo .xlsx"}
        </div>
        {archivo && (
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginTop: 10 }}>
            <div className="upload-filename">✓ {archivo.name}</div>
            <button
              className="btn btn-secondary btn-sm"
              onClick={e => { e.stopPropagation(); limpiar() }}
              style={{ padding: "3px 10px", fontSize: 11 }}
            >✕ Quitar</button>
          </div>
        )}
        <input ref={inputRef} type="file" accept=".xlsx" style={{ display: "none" }}
          onChange={e => seleccionar(e.target.files[0])} />
      </div>

      {error && <div className="alert alert-error">⚠ {error}</div>}

      {/* Resultado ──────────────────────────────────────────── */}
      {resultado && (
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {/* Stats */}
          <div className="stats-row" style={{ marginBottom: 0 }}>
            <div className="stat-card">
              <div className="stat-value">{resultado.procesados}</div>
              <div className="stat-label">Registros procesados</div>
            </div>
            <div className="stat-card">
              <div className="stat-value" style={{ color: "var(--accent2)" }}>{resultado.creados}</div>
              <div className="stat-label">Creados</div>
            </div>
            <div className="stat-card">
              <div className="stat-value" style={{ color: "var(--accent)" }}>{resultado.actualizados}</div>
              <div className="stat-label">Actualizados</div>
            </div>
            <div className="stat-card">
              <div className="stat-value" style={{ color: "var(--text3)" }}>{resultado.sin_cambio}</div>
              <div className="stat-label">Sin cambio</div>
            </div>
          </div>

          {/* Mensaje de éxito */}
          {resultado.creados + resultado.actualizados > 0 && (
            <div className="alert alert-success">
              ✓ Forecast {anio} cargado correctamente —&nbsp;
              {resultado.creados > 0 && `${resultado.creados} filas nuevas`}
              {resultado.creados > 0 && resultado.actualizados > 0 && ", "}
              {resultado.actualizados > 0 && `${resultado.actualizados} actualizadas`}.
            </div>
          )}

          {/* Errores */}
          {resultado.errores?.length > 0 && (
            <div className="card" style={{ padding: "14px 18px" }}>
              <div style={{ fontWeight: 600, color: "var(--warn)", marginBottom: 10, fontSize: 13 }}>
                ⚠ {resultado.errores.length} advertencia{resultado.errores.length > 1 ? "s" : ""} durante la carga
              </div>
              <div style={{ maxHeight: 200, overflowY: "auto", display: "flex", flexDirection: "column", gap: 4 }}>
                {resultado.errores.map((e, i) => (
                  <div key={i} style={{
                    fontSize: 12, padding: "5px 10px",
                    background: "rgba(255,184,77,0.08)", borderRadius: 5,
                    borderLeft: "3px solid var(--warn)", color: "var(--text2)"
                  }}>{e}</div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Botón cargar */}
      <div style={{ display: "flex", justifyContent: "flex-end", gap: 10 }}>
        {resultado && (
          <button className="btn btn-secondary" onClick={limpiar}>
            ↺ Cargar otro archivo
          </button>
        )}
        <button
          className="btn btn-primary"
          onClick={cargar}
          disabled={!archivo || loading}
          style={{ minWidth: 160 }}
        >
          {loading
            ? <><span className="spinner" /> Procesando...</>
            : <> ⬆ Cargar Forecast {anio}</>
          }
        </button>
      </div>
    </div>
  )
}
