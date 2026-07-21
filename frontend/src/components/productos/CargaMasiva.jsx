import { useState, useRef } from "react"
import { cargaMasivaProductos } from "../../services/api"

const MODOS = {
  nuevo: {
    label: "Nuevos productos",
    desc: "Crea productos que no existen. Error si el SKU ya está registrado.",
    cols: ["SKU","Marca","Categoria","Temporada","Descripcion","Precio_Bruto"],
    ejemplo: ["R3357","Acqui","Calefacción","1","Camilla Masajes 3 Cuerpos","89990"],
    nota: "Todos los campos son obligatorios. Temporada: número ID.",
  },
  actualizar: {
    label: "Actualizar existentes",
    desc: "Modifica productos ya registrados. Solo se actualizan las columnas incluidas en el archivo.",
    cols: ["SKU","Marca","Categoria","Temporada","Descripcion","Precio_Bruto","Comentario","Activo"],
    ejemplo: ["R3357","","","","Nueva descripción","94990","",""],
    nota: "Solo SKU es obligatorio. Las celdas vacías no modifican el campo. Activo: 1/0 o Sí/No.",
  },
  upsert: {
    label: "Crear o actualizar",
    desc: "Crea si el SKU no existe, actualiza si ya existe.",
    cols: ["SKU","Marca","Categoria","Temporada","Descripcion","Precio_Bruto"],
    ejemplo: ["R3357","Acqui","Calefacción","1","Camilla Masajes 3 Cuerpos","89990"],
    nota: "Todos los campos son obligatorios.",
  },
}

export default function CargaMasiva({ onExito }) {
  const [modo, setModo]       = useState("nuevo")
  const [archivo, setArchivo] = useState(null)
  const [drag, setDrag]       = useState(false)
  const [loading, setLoading] = useState(false)
  const [resultado, setResultado] = useState(null)
  const [error, setError]     = useState("")
  const inputRef = useRef()

  const seleccionar = (file) => {
    if (!file) return
    if (!file.name.match(/\.(xlsx|xls)$/i)) { setError("Solo se aceptan archivos .xlsx o .xls"); return }
    setArchivo(file); setError(""); setResultado(null)
  }

  const handleCargar = async () => {
    if (!archivo) return
    setLoading(true); setError(""); setResultado(null)
    try {
      const res = await cargaMasivaProductos(archivo, modo)
      setResultado(res)
      if (res.creados > 0 || res.actualizados > 0) onExito()
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const cfg = MODOS[modo]

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>

      {/* Selector de modo */}
      <div className="card" style={{ padding: "16px 20px" }}>
        <div style={{ fontWeight: 500, marginBottom: 12, color: "var(--text)" }}>¿Qué deseas hacer?</div>
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
          {Object.entries(MODOS).map(([key, m]) => (
            <button
              key={key}
              onClick={() => { setModo(key); setArchivo(null); setResultado(null); setError("") }}
              style={{
                padding: "8px 18px", borderRadius: 8, fontSize: 13, fontWeight: 600, cursor: "pointer",
                border: modo === key ? "2px solid var(--accent)" : "1px solid #2a3a50",
                background: modo === key ? "rgba(99,179,237,0.12)" : "transparent",
                color: modo === key ? "var(--accent)" : "var(--text2)",
                transition: "all .15s",
              }}
            >{m.label}</button>
          ))}
        </div>
        <div style={{ fontSize: 12, color: "var(--text2)", marginTop: 10 }}>{cfg.desc}</div>
      </div>

      {/* Formato */}
      <div className="card" style={{ padding: "16px 20px" }}>
        <div style={{ fontWeight: 500, marginBottom: 10, color: "var(--text)" }}>Formato del Excel</div>
        <div style={{ overflowX: "auto" }}>
          <table style={{ fontSize: 12, width: "auto" }}>
            <thead>
              <tr>
                {cfg.cols.map(c => (
                  <th key={c} style={{ background: "var(--bg3)", padding: "6px 14px",
                    color: c === "SKU" ? "var(--accent)" : "var(--text)" }}>{c}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              <tr>
                {cfg.ejemplo.map((v, i) => (
                  <td key={i} style={{ padding: "6px 14px", fontFamily: "var(--mono)", fontSize: 12,
                    color: v === "" ? "var(--text3)" : "var(--text)" }}>{v || "—"}</td>
                ))}
              </tr>
            </tbody>
          </table>
        </div>
        <div style={{ fontSize: 11, color: "var(--text3)", marginTop: 10 }}>• {cfg.nota}</div>
      </div>

      {/* Drop zone */}
      <div
        className={`upload-zone ${drag ? "drag" : ""}`}
        onClick={() => inputRef.current?.click()}
        onDragOver={e => { e.preventDefault(); setDrag(true) }}
        onDragLeave={() => setDrag(false)}
        onDrop={e => { e.preventDefault(); setDrag(false); seleccionar(e.dataTransfer.files[0]) }}
      >
        <div className="upload-icon">📂</div>
        <div className="upload-text">Arrastra tu archivo Excel aquí</div>
        <div className="upload-hint">o haz clic para seleccionar</div>
        {archivo && <div className="upload-filename">✓ {archivo.name}</div>}
        <input ref={inputRef} type="file" accept=".xlsx,.xls" style={{ display: "none" }}
          onChange={e => seleccionar(e.target.files[0])} />
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      {resultado && (
        <div className="alert alert-success">
          <strong>Carga completada:</strong> {resultado.creados} creados · {resultado.actualizados} actualizados
          {resultado.errores?.length > 0 && (
            <div style={{ marginTop: 8 }}>
              <strong>Filas con error ({resultado.errores.length}):</strong>
              {resultado.errores.map((e, i) => (
                <div key={i} style={{ fontSize: 12, marginTop: 4 }}>Fila {e.fila}: {e.error}</div>
              ))}
            </div>
          )}
        </div>
      )}

      <div style={{ display: "flex", justifyContent: "flex-end" }}>
        <button className="btn btn-primary" onClick={handleCargar} disabled={!archivo || loading}>
          {loading ? <><span className="spinner"/> Cargando...</> : `⬆ ${cfg.label}`}
        </button>
      </div>
    </div>
  )
}
