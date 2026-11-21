import { useState } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { apiRequest } from '../api/client'
import { useAuth } from '../auth/useAuth'

export default function AuthPage({ mode }) {
  const isRegister = mode === 'register'
  const [phoneNumber, setPhoneNumber] = useState('')
  const [otp, setOtp] = useState('')
  const [otpRequested, setOtpRequested] = useState(false)
  const [simulationCode, setSimulationCode] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const { isAuthenticated, signIn } = useAuth()
  const navigate = useNavigate()

  if (isAuthenticated) return <Navigate to="/" replace />

  async function requestOtp(event) {
    event.preventDefault()
    setError('')
    setLoading(true)
    try {
      const response = await apiRequest('/auth/register', {
        method: 'POST',
        body: { phone_number: phoneNumber },
        auth: false,
      })
      setSimulationCode(response.simulation_code)
      setOtpRequested(true)
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setLoading(false)
    }
  }

  async function verifyOtp(event) {
    event.preventDefault()
    setError('')
    setLoading(true)
    try {
      const tokens = await apiRequest('/auth/verify-otp', {
        method: 'POST',
        body: { phone_number: phoneNumber, otp },
        auth: false,
      })
      signIn(tokens)
      navigate('/')
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="auth-page">
      <section className="panel auth-panel">
        <Link className="brand" to="/">
          KahveCell
        </Link>
        <h1>{isRegister ? 'Kayıt ol' : 'Giriş yap'}</h1>
        <p>Telefon numaranızla devam edin. SMS doğrulaması test amaçlıdır.</p>

        {!otpRequested ? (
          <form className="form-stack" onSubmit={requestOtp}>
            <label htmlFor="phone">GSM numarası</label>
            <input
              autoComplete="tel"
              id="phone"
              onChange={(event) => setPhoneNumber(event.target.value)}
              placeholder="05XXXXXXXXX"
              required
              value={phoneNumber}
            />
            <button className="button" disabled={loading} type="submit">
              {loading ? 'İstek gönderiliyor…' : 'Doğrulama kodu iste'}
            </button>
          </form>
        ) : (
          <form className="form-stack" onSubmit={verifyOtp}>
            <p className="notice">
              Simülasyon kodu: <strong>{simulationCode}</strong>
            </p>
            <label htmlFor="otp">4 haneli doğrulama kodu</label>
            <input
              autoComplete="one-time-code"
              id="otp"
              inputMode="numeric"
              maxLength={4}
              onChange={(event) => setOtp(event.target.value)}
              pattern="[0-9]{4}"
              required
              value={otp}
            />
            <button className="button" disabled={loading} type="submit">
              {loading ? 'Doğrulanıyor…' : 'Doğrula ve devam et'}
            </button>
            <button
              className="button button-quiet"
              onClick={() => setOtpRequested(false)}
              type="button"
            >
              Numarayı değiştir
            </button>
          </form>
        )}

        {error && <p className="error-message">{error}</p>}
        <p className="auth-switch">
          {isRegister ? 'Zaten hesabınız var mı?' : 'İlk kez mi geliyorsunuz?'}{' '}
          <Link to={isRegister ? '/login' : '/register'}>
            {isRegister ? 'Giriş yap' : 'Kayıt ol'}
          </Link>
        </p>
      </section>
    </main>
  )
}
