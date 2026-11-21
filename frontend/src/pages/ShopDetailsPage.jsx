import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { apiRequest } from '../api/client'

export default function ShopDetailsPage() {
  const { shopId } = useParams()
  const [shop, setShop] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    apiRequest(`/shops/${shopId}`, { auth: false })
      .then((data) => {
        if (active) setShop(data)
      })
      .catch((requestError) => {
        if (active) setError(requestError.message)
      })
    return () => {
      active = false
    }
  }, [shopId])

  if (error) return <p className="error-message">{error}</p>
  if (!shop) return <p className="page-message">Dükkân yükleniyor…</p>

  return (
    <section className="page-stack">
      <Link to="/">← Dükkânlara dön</Link>
      <div className="page-heading">
        <div>
          <h1>{shop.name}</h1>
          <p>{shop.address}</p>
        </div>
        <Link className="button" to={`/shops/${shop.id}/order`}>
          Sipariş ver
        </Link>
      </div>
      <section className="panel">
        <h2>Menü</h2>
        <div className="menu-list">
          {shop.menu.map((product) => (
            <div className="menu-item" key={product.id}>
              <div>
                <strong>{product.name}</strong>
                {product.description && <p>{product.description}</p>}
              </div>
              <span>{(product.price_cents / 100).toFixed(2)} TL</span>
            </div>
          ))}
        </div>
      </section>
    </section>
  )
}
