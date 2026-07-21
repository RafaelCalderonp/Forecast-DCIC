import { useState } from 'react'
import { useAuth } from '../../context/AuthContext'

export default function LoginPage() {
  const { login } = useAuth()
  const [email,    setEmail]    = useState('')
  const [password, setPassword] = useState('')
  const [error,    setError]    = useState('')
  const [loading,  setLoading]  = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await login(email, password)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{
      minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
      background: 'linear-gradient(160deg, #0F172A 0%, #1C2436 55%, #0D2B2B 100%)',
    }}>
      <div style={{
        background: '#fff', borderRadius: 16, padding: '48px 40px',
        width: 400, boxShadow: '0 25px 60px rgba(0,0,0,.45)',
      }}>
        <div style={{ textAlign: 'center', marginBottom: 32 }}>
          <div style={{
            display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
            background: '#1C2436', borderRadius: 10, padding: '12px 24px', marginBottom: 12,
          }}>
            <img src="/dcic-logo.svg" alt="DCIC Group" style={{ height: 32, display: 'block' }} />
          </div>
          <div style={{ fontSize: 13, color: '#64748b', marginTop: 4 }}>Sistema de Forecast</div>
        </div>

        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: 16 }}>
            <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: '#475569', marginBottom: 6 }}>
              Email
            </label>
            <input
              type="email" value={email} onChange={e => setEmail(e.target.value)}
              placeholder="usuario@dcic.cl" required autoFocus
              style={{
                width: '100%', padding: '10px 14px', border: '1.5px solid #e2e8f0',
                borderRadius: 8, fontSize: 14, outline: 'none', boxSizing: 'border-box',
              }}
            />
          </div>
          <div style={{ marginBottom: 24 }}>
            <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: '#475569', marginBottom: 6 }}>
              Contraseña
            </label>
            <input
              type="password" value={password} onChange={e => setPassword(e.target.value)}
              placeholder="••••••••" required
              style={{
                width: '100%', padding: '10px 14px', border: '1.5px solid #e2e8f0',
                borderRadius: 8, fontSize: 14, outline: 'none', boxSizing: 'border-box',
              }}
            />
          </div>

          {error && (
            <div style={{
              background: '#fee2e2', color: '#991b1b', padding: '10px 14px',
              borderRadius: 8, fontSize: 13, marginBottom: 16,
            }}>{error}</div>
          )}

          <button
            type="submit" disabled={loading}
            style={{
              width: '100%', padding: '12px', background: loading ? '#5eead4' : '#0D9488',
              color: '#fff', border: 'none', borderRadius: 8, fontSize: 15,
              fontWeight: 700, cursor: loading ? 'not-allowed' : 'pointer',
              transition: 'background .2s',
            }}
          >
            {loading ? 'Ingresando…' : 'Ingresar'}
          </button>
        </form>

        <div style={{ marginTop: 24, textAlign: 'center', fontSize: 11, color: '#94a3b8' }}>
          IMPORTADORA DCIC SPA — Forecast 2026
        </div>
      </div>
    </div>
  )
}
