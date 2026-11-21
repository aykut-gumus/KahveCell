import { useEffect, useState } from 'react'
import { QRCodeSVG } from 'qrcode.react'
import { Link, useLocation, useParams } from 'react-router-dom'
import { apiRequest } from '../api/client'

export default function QrPage() {
  const { orderId } = useParams()
  const location = useLocation()
  const [order, setOrder] = useState(location.state?.order || null)
  const [error, setError] = useState('')

  useEffect(() => {
    if (location.state?.order) return
    let active = true
    apiRequest('/orders/me')
      .then((orders) => {
        const found = orders.find((item) => String(item.id) === orderId)
        if (active && found) setOrder(found)
        if (active && !found) setError('Sipariş bulunamadı.')
      })
      .catch((requestError) => {
        if (active) setError(requestError.message)
      })
    return () => {
      active = false
    }
  }, [location.state, orderId])

  const qrCode = location.state?.qrCode || order?.qr_code
  if (error) return <p className="error-message">{error}</p>
  if (!order || !qrCode) {
    return <p className="page-message">Sipariş yükleniyor…</p>
  }

  return (
    <section className="page-stack narrow-page">
      <Link to="/history">← Sipariş geçmişi</Link>
      <h1>Sipariş #{order.id}</h1>
      <p>Durum: {order.status}</p>
      <section className="panel qr-panel">
        <QRCodeSVG value={JSON.stringify(qrCode)} size={240} />
        <p>Dükkânda göstermek için bu QR kodu kullanın.</p>
        <details>
          <summary>QR verisini göster</summary>
          <pre>{JSON.stringify(qrCode, null, 2)}</pre>
        </details>
      </section>
    </section>
  )
}
