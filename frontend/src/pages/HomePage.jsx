import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiRequest } from '../api/client'
import ShopMap from '../components/ShopMap'

const DEFAULT_LOCATION = [39.9208, 32.8541]

export default function HomePage() {
  const [shops, setShops] = useState([])
  const [searchInput, setSearchInput] = useState('')
  const [search, setSearch] = useState('')
  const [location, setLocation] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const params = new URLSearchParams()
    if (search) params.set('search', search)
    if (location) {
      params.set('latitude', location.latitude)
      params.set('longitude', location.longitude)
    }

    let active = true
    const query = params.toString()
    apiRequest(`/shops${query ? `?${query}` : ''}`, { auth: false })
      .then((data) => {
        if (active) {
          setShops(data)
          setError('')
        }
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
  }, [search, location])

  function useCurrentLocation() {
    if (!navigator.geolocation) {
      setError('Tarayıcınız konum bilgisini desteklemiyor.')
      return
    }
    navigator.geolocation.getCurrentPosition(
      ({ coords }) => {
        setLoading(true)
        setLocation({
          latitude: coords.latitude,
          longitude: coords.longitude,
        })
      },
      () => setError('Konum alınamadı; konum iznini kontrol edin.'),
    )
  }

  return (
    <section className="page-stack">
      <div className="page-heading">
        <div>
          <h1>Dükkânlar</h1>
          <p>Yakınındaki kahve dükkânlarını keşfet.</p>
        </div>
        <button className="button button-secondary" onClick={useCurrentLocation}>
          Konumuma göre sırala
        </button>
      </div>

      <form
        className="search-form"
        onSubmit={(event) => {
          event.preventDefault()
          const nextSearch = searchInput.trim()
          if (nextSearch !== search) setLoading(true)
          setSearch(nextSearch)
        }}
      >
        <input
          aria-label="Dükkân adı veya adresi"
          onChange={(event) => setSearchInput(event.target.value)}
          placeholder="Dükkân adı veya adresi"
          value={searchInput}
        />
        <button className="button" type="submit">
          Ara
        </button>
      </form>

      {error && <p className="error-message">{error}</p>}
      {loading ? (
        <p className="page-message">Dükkânlar yükleniyor…</p>
      ) : (
        <>
          <ShopMap
            center={
              location
                ? [location.latitude, location.longitude]
                : DEFAULT_LOCATION
            }
            key={
              location
                ? `${location.latitude},${location.longitude}`
                : 'default'
            }
            shops={shops}
          />
          <div className="shop-grid">
            {shops.map((shop) => (
              <article className="panel shop-card" key={shop.id}>
                <h2>
                  <Link to={`/shops/${shop.id}`}>{shop.name}</Link>
                </h2>
                <p>{shop.address}</p>
                {shop.distance_km !== null && (
                  <p>{shop.distance_km.toFixed(2)} km uzaklıkta</p>
                )}
              </article>
            ))}
            {shops.length === 0 && <p>Aramanızla eşleşen dükkân bulunamadı.</p>}
          </div>
        </>
      )}
    </section>
  )
}
