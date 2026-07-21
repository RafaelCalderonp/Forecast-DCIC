import { useState, useRef, useEffect } from 'react'

/**
 * MultiSelect — dropdown con checkboxes para selección múltiple.
 * Props:
 *   options: string[]          opciones disponibles
 *   value:   string[]          seleccionados
 *   onChange: (string[]) => void
 *   placeholder: string        texto cuando no hay selección
 *   dark: bool                 tema oscuro (para tablas)
 *   style: object              estilos extra del trigger
 */
export default function MultiSelect({ options = [], value = [], onChange, placeholder = '▼ Todos', dark = false, style = {} }) {
  const [open, setOpen] = useState(false)
  const [search, setSearch] = useState('')
  const ref = useRef()

  useEffect(() => {
    function handler(e) { if (ref.current && !ref.current.contains(e.target)) setOpen(false) }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const filtered = options.filter(o => o.toLowerCase().includes(search.toLowerCase()))

  function toggle(op) {
    onChange(value.includes(op) ? value.filter(v => v !== op) : [...value, op])
  }

  function toggleAll() {
    onChange(value.length === options.length ? [] : [...options])
  }

  const label = value.length === 0 ? placeholder
    : value.length === 1 ? value[0]
    : `${value.length} selec.`

  const active = value.length > 0

  const bg      = dark ? '#1a2235' : '#fff'
  const bgDrop  = dark ? '#1a2235' : '#fff'
  const border  = dark ? (active ? '#3d7eff' : '#2a3348') : (active ? '#3d7eff' : '#d1d5db')
  const color   = dark ? (active ? '#3d7eff' : '#8891aa') : (active ? '#1d4ed8' : '#374151')
  const itemHov = dark ? '#0f1623' : '#f3f4f6'

  return (
    <div ref={ref} style={{ position: 'relative', ...style }}>
      {/* Trigger */}
      <div
        onClick={() => setOpen(o => !o)}
        style={{
          width: '100%', cursor: 'pointer', userSelect: 'none',
          fontSize: dark ? 10 : 12, padding: dark ? '2px 4px' : '6px 10px',
          background: bg, color, border: `1px solid ${border}`, borderRadius: 4,
          whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 4,
        }}>
        <span style={{ overflow: 'hidden', textOverflow: 'ellipsis' }}>{label}</span>
        <span style={{ fontSize: 8, opacity: 0.7, flexShrink: 0 }}>{open ? '▲' : '▼'}</span>
      </div>

      {/* Dropdown */}
      {open && (
        <div style={{
          position: 'absolute', top: '100%', left: 0, zIndex: 1000,
          minWidth: 200, maxWidth: 280, maxHeight: 280, overflowY: 'auto',
          background: bgDrop, border: `1px solid ${border}`, borderRadius: 4,
          boxShadow: '0 4px 16px rgba(0,0,0,0.35)', marginTop: 2,
        }}>
          {/* Buscar */}
          {options.length > 8 && (
            <div style={{ padding: '6px 8px', borderBottom: `1px solid ${border}` }}>
              <input
                autoFocus
                value={search}
                onChange={e => setSearch(e.target.value)}
                placeholder="Buscar…"
                style={{
                  width: '100%', fontSize: 11, padding: '3px 6px',
                  background: dark ? '#111827' : '#f9fafb',
                  color: dark ? '#e2e8f0' : '#111',
                  border: `1px solid ${border}`, borderRadius: 3, outline: 'none',
                  boxSizing: 'border-box',
                }}
              />
            </div>
          )}

          {/* Seleccionar todos */}
          <div
            onClick={toggleAll}
            style={{
              padding: '5px 10px', fontSize: 10, cursor: 'pointer', fontWeight: 700,
              color: dark ? '#8891aa' : '#6b7280',
              borderBottom: `1px solid ${border}`,
              background: 'transparent',
            }}
            onMouseEnter={e => e.currentTarget.style.background = itemHov}
            onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
          >
            {value.length === options.length ? '☐ Deseleccionar todo' : '☑ Seleccionar todo'}
          </div>

          {/* Opciones */}
          {filtered.map(op => {
            const checked = value.includes(op)
            return (
              <div
                key={op}
                onClick={() => toggle(op)}
                style={{
                  padding: '5px 10px', fontSize: 11, cursor: 'pointer',
                  display: 'flex', alignItems: 'center', gap: 8,
                  color: checked ? (dark ? '#3d7eff' : '#1d4ed8') : (dark ? '#e2e8f0' : '#111'),
                  background: 'transparent',
                }}
                onMouseEnter={e => e.currentTarget.style.background = itemHov}
                onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
              >
                <span style={{ fontSize: 12, flexShrink: 0 }}>{checked ? '☑' : '☐'}</span>
                <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{op}</span>
              </div>
            )
          })}

          {filtered.length === 0 && (
            <div style={{ padding: '8px 10px', fontSize: 11, color: dark ? '#4b5563' : '#9ca3af' }}>Sin resultados</div>
          )}
        </div>
      )}
    </div>
  )
}
