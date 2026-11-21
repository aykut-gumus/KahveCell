import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiRequest } from '../api/client'

export default function HistoryPage() {
  const [orders, setOrders] = useState([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let active = true
    apiRequest('/orders/me')
      .then((data) => {
        if (active) setOrders(data)
      })
      .catch((requestError) => {
        if (active) setError(requestError.message)
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [])

  return (
    <section className="page-stack">
      <h1>Sipariş geçmişi</h1>
      {error && <p className="error-message">{error}</p>}
      {loading ? (
        <p className="page-message">Siparişler yükleniyor…</p>
      ) : orders.length ? (
        <div className="list-stack">
          {orders.map((order) => (
            <article className="panel order-row" key={order.id}>
              <div>
                <h2>{order.product_name}</h2>
                <p>
                  Sipariş #{order.id} · {order.status}
                </p>
                <p>{new Date(order.created_at).toLocaleString('tr-TR')}</p>
              </div>
              <Link className="button button-secondary" to={`/orders/${order.id}/qr`}>
                QR kodu aç
              </Link>
            </article>
          ))}
        </div>
      ) : (
        <p>Henüz siparişiniz yok.</p>
      )}
    </section>
  )
}
