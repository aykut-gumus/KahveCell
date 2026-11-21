import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { apiRequest } from '../api/client'

export default function OrderPage() {
  const { shopId } = useParams()
  const navigate = useNavigate()
  const [shop, setShop] = useState(null)
  const [productId, setProductId] = useState('')
  const [customizations, setCustomizations] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    let active = true
    apiRequest(`/shops/${shopId}`, { auth: false })
      .then((data) => {
        if (active) {
          setShop(data)
          setProductId(String(data.menu[0]?.id || ''))
        }
      })
      .catch((requestError) => {
        if (active) setError(requestError.message)
      })
    return () => {
      active = false
    }
  }, [shopId])

  async function submitOrder(event) {
    event.preventDefault()
    setError('')
    setLoading(true)
    try {
      const order = await apiRequest('/orders', {
        method: 'POST',
        body: {
          shop_id: Number(shopId),
          product_id: Number(productId),
          customizations: customizations.trim()
            ? { note: customizations.trim() }
            : null,
        },
      })
      navigate(`/orders/${order.id}/qr`, {
        state: { order, qrCode: order.qr_code },
      })
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setLoading(false)
    }
  }

  if (!shop) {
    return <p className="page-message">{error || 'Dükkân yükleniyor…'}</p>
  }

  return (
    <section className="page-stack narrow-page">
      <Link to={`/shops/${shop.id}`}>← {shop.name}</Link>
      <h1>Sipariş ver</h1>
      <form className="panel form-stack" onSubmit={submitOrder}>
        <label htmlFor="product">Ürün</label>
        <select
          id="product"
          onChange={(event) => setProductId(event.target.value)}
          required
          value={productId}
        >
          {shop.menu
            .filter((product) => product.is_available)
            .map((product) => (
              <option key={product.id} value={product.id}>
                {product.name} — {(product.price_cents / 100).toFixed(2)} TL
              </option>
            ))}
        </select>
        <label htmlFor="customizations">Not (isteğe bağlı)</label>
        <textarea
          id="customizations"
          onChange={(event) => setCustomizations(event.target.value)}
          rows={3}
          value={customizations}
        />
        {error && <p className="error-message">{error}</p>}
        <button
          className="button"
          disabled={loading || !productId}
          type="submit"
        >
          {loading ? 'Sipariş veriliyor…' : 'Siparişi onayla'}
        </button>
      </form>
    </section>
  )
}
