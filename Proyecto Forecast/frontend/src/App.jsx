import { useState, useEffect, Component } from "react"
import { BrowserRouter, Routes, Route, useLocation, useNavigate } from "react-router-dom"

class ErrorBoundary extends Component {
  constructor(props) { super(props); this.state = { error: null } }
  static getDerivedStateFromError(e) { return { error: e } }
  render() {
    if (this.state.error) {
      return (
        <div style={{ padding: 24, color: '#ef4444', background: '#0d1520', fontFamily: 'monospace', fontSize: 13, lineHeight: 1.6, borderRadius: 8, margin: 12 }}>
          <div style={{ fontWeight: 700, marginBottom: 8 }}>Error en Forecast 2027</div>
          <pre style={{ whiteSpace: 'pre-wrap', color: '#f87171' }}>{String(this.state.error)}</pre>
          <button onClick={() => this.setState({ error: null })} style={{ marginTop: 12, padding: '6px 14px', background: '#3d7eff', color: '#fff', border: 'none', borderRadius: 6, cursor: 'pointer' }}>Reintentar</button>
        </div>
      )
    }
    return this.props.children
  }
}
import { AuthProvider, useAuth } from "./context/AuthContext"
import LoginPage      from "./components/auth/LoginPage"
import ProductosPage  from "./components/productos/ProductosPage"
import ForecastPage   from "./components/forecast/ForecastPage"
import AlertasPage    from "./components/alertas/AlertasPage"
import ReporteCompras from "./components/compras/ReporteCompras"
import VentasPage      from "./components/ventas/VentasPage"
import Forecast2027Page from "./components/forecast/Forecast2027Page"
import StockPage from "./components/stock/StockPage"
import ListaPreciosPage from "./components/precios/ListaPreciosPage"
import ForecastDinamicoPage from "./components/forecast/ForecastDinamicoPage"
import "./App.css"

const NAV = [
  { id: "compras",      icon: "🛒", label: "Compras",        activo: true  },
  { id: "forecast",     icon: "📊", label: "Forecast 26",    activo: true  },
  { id: "forecast_hw",  icon: "⚡", label: "Forecast HW",    activo: true  },
  { id: "forecast27",   icon: "📈", label: "Forecast 27",    activo: true  },
  { id: "alertas",      icon: "🔔", label: "Alertas",        activo: true  },
  { id: "productos",    icon: "📦", label: "Productos",      activo: true  },
  { id: "ventas",       icon: "💰", label: "Ventas",         activo: true  },
  { id: "stock",        icon: "🏭", label: "Stock",          activo: true  },
  { id: "precios",      icon: "💲", label: "Lista Precios",  activo: true  },
  { id: "packs",        icon: "📋", label: "Packs",          activo: false },
]

const IDS_VALIDOS = NAV.map(n => n.id)

function AppShell() {
  const { user, logout, isAdmin } = useAuth()
  const location = useLocation()
  const navigate = useNavigate()
  const path = location.pathname.slice(1)
  const seccion = IDS_VALIDOS.includes(path) ? path : "compras"
  const [sidebarOpen, setSidebarOpen] = useState(true)
  // Secciones visitadas: se montan la primera vez y permanecen en DOM (preserva filtros/estado)
  const [visitadas, setVisitadas] = useState({ compras: true })

  useEffect(() => {
    setVisitadas(v => (v[seccion] ? v : { ...v, [seccion]: true }))
  }, [seccion])

  // Normaliza URLs inválidas o la raíz "/" a la sección por defecto
  useEffect(() => {
    if (path !== seccion) navigate("/" + seccion, { replace: true })
  }, [path, seccion, navigate])

  const irA = (id) => navigate("/" + id)

  if (!user) return <LoginPage />

  return (
    <div className="app">
      <aside className={`sidebar${sidebarOpen ? "" : " sidebar-collapsed"}`}>

        {/* Logo DCIC GROUP */}
        <div className="sidebar-logo">
          {sidebarOpen ? (
            <img src="/dcic-logo.svg" alt="DCIC Group" className="sidebar-logo-img" />
          ) : (
            <img src="/dcic-logo.svg" alt="DCIC" className="sidebar-logo-collapsed" />
          )}
        </div>

        {/* Navegación */}
        <nav className="sidebar-nav">
          {NAV.map(n => (
            <button
              key={n.id}
              className={`nav-item${seccion === n.id ? " active" : ""}`}
              onClick={() => irA(n.id)}
              disabled={!n.activo}
              title={!sidebarOpen ? n.label : undefined}
            >
              <span className="nav-icon">{n.icon}</span>
              <span className="nav-label">{n.label}</span>
              {n.id === "alertas" && <span className="nav-badge-dot" />}
            </button>
          ))}
        </nav>

        {/* Footer: usuario + logout */}
        <div className="sidebar-footer">
          <div className="sidebar-footer-info">
            <div className="sidebar-user-name">{user.nombre || user.email}</div>
            <span className={`sidebar-user-rol ${isAdmin ? "rol-admin" : user.rol === "editor" ? "rol-editor" : "rol-viewer"}`}>
              {user.rol}
            </span>
          </div>
          <button className="sidebar-logout" onClick={logout} title="Cerrar sesión">✕</button>
        </div>

        {/* Botón colapsar */}
        <button
          className="sidebar-collapse-btn"
          onClick={() => setSidebarOpen(o => !o)}
          title={sidebarOpen ? "Colapsar menú" : "Expandir menú"}
        >
          {sidebarOpen ? "◀" : "▶"}
        </button>

      </aside>

      <main className="main-content">
        {/* Top bar — logo DCIC + sección activa */}
        <div className="topbar">
          <img src="/dcic-logo.svg" alt="DCIC Group" className="topbar-logo" />
          <div className="topbar-divider" />
          <span className="topbar-section">
            {NAV.find(n => n.id === seccion)?.label ?? ""}
          </span>
        </div>

        {/* Área de páginas — scroll aquí */}
        <div className="pages-area">
          {visitadas.compras     && <div style={{ display: seccion === "compras"     ? "" : "none" }}><ReporteCompras /></div>}
          {visitadas.forecast    && <div style={{ display: seccion === "forecast"    ? "" : "none" }}><ForecastPage /></div>}
          {visitadas.forecast_hw && <div style={{ display: seccion === "forecast_hw" ? "" : "none" }}><ForecastDinamicoPage /></div>}
          {visitadas.forecast27  && <div style={{ display: seccion === "forecast27"  ? "" : "none" }}><ErrorBoundary><Forecast2027Page /></ErrorBoundary></div>}
          {visitadas.alertas    && <div style={{ display: seccion === "alertas"    ? "" : "none" }}><AlertasPage /></div>}
          {visitadas.productos  && <div style={{ display: seccion === "productos"  ? "" : "none" }}><ProductosPage /></div>}
          {visitadas.ventas     && <div style={{ display: seccion === "ventas"     ? "" : "none" }}><VentasPage /></div>}
          {visitadas.stock      && <div style={{ display: seccion === "stock"      ? "" : "none" }}><StockPage /></div>}
          {visitadas.precios    && <div style={{ display: seccion === "precios"    ? "" : "none" }}><ListaPreciosPage /></div>}
        </div>
      </main>
    </div>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/*" element={<AppShell />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}
