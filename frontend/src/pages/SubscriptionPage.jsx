import { useEffect, useState } from 'react'
import { apiRequest } from '../api/client'

const PLAN_NAMES = {
  STARTER: 'Starter',
  PREMIUM: 'Premium',
  UNLIMITED: 'Unlimited',
}

export default function SubscriptionPage() {
  const [plans, setPlans] = useState([])
  const [subscription, setSubscription] = useState(null)
  const [cardToken, setCardToken] = useState('4242-4242-4242-4242')
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [reloadKey, setReloadKey] = useState(0)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let active = true
    Promise.all([
      apiRequest('/subscriptions/plans', { auth: false }),
      apiRequest('/subscriptions/me'),
    ])
      .then(([availablePlans, currentSubscription]) => {
        if (!active) return
        setPlans(availablePlans)
        setSubscription(currentSubscription)
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
  }, [reloadKey])

  async function purchase(planType) {
    setError('')
    setMessage('')
    try {
      const result = await apiRequest('/payments/process', {
        method: 'POST',
        body: { subscription_plan: planType, card_token: cardToken },
      })
      if (!result.success) {
        setError(result.message)
        return
      }
      setMessage(`${PLAN_NAMES[planType]} paketi etkinleştirildi.`)
      setReloadKey((value) => value + 1)
    } catch (requestError) {
      setError(requestError.message)
    }
  }

  async function cancelSubscription() {
    setError('')
    setMessage('')
    try {
      await apiRequest('/subscriptions/cancel', { method: 'POST' })
      setMessage('Aboneliğiniz iptal edildi.')
      setReloadKey((value) => value + 1)
    } catch (requestError) {
      setError(requestError.message)
    }
  }

  if (loading) return <p className="page-message">Abonelikler yükleniyor…</p>

  return (
    <section className="page-stack">
      <h1>Abonelik</h1>
      {error && <p className="error-message">{error}</p>}
      {message && <p className="notice">{message}</p>}

      <section className="panel form-stack">
        <strong>Test kartı</strong>
        <select
          aria-label="Test kartı"
          onChange={(event) => setCardToken(event.target.value)}
          value={cardToken}
        >
          <option value="4242-4242-4242-4242">
            4242-4242-4242-4242 — başarılı
          </option>
          <option value="4000-0000-0000-0002">
            4000-0000-0000-0002 — başarısız
          </option>
        </select>
      </section>

      <div className="plan-grid">
        {plans.map((plan) => (
          <article className="panel plan-card" key={plan.plan_type}>
            <h2>{PLAN_NAMES[plan.plan_type]}</h2>
            <p className="plan-price">
              {plan.monthly_price.toFixed(2)} TL / ay
            </p>
            <p>
              {plan.coffee_credits === null
                ? 'Sınırsız kahve'
                : `${plan.coffee_credits} kahve / ay`}
            </p>
            {plan.guest_credits > 0 && (
              <p>{plan.guest_credits} misafir hakkı</p>
            )}
            {plan.priority_service && <p>Öncelikli hizmet</p>}
            <button
              className="button"
              onClick={() => purchase(plan.plan_type)}
              type="button"
            >
              Paketi satın al / değiştir
            </button>
          </article>
        ))}
      </div>

      <section className="panel">
        <h2>Aktif aboneliğim</h2>
        {subscription ? (
          <div className="subscription-summary">
            <p>{PLAN_NAMES[subscription.plan_type]}</p>
            <p>
              Kalan kahve hakkı:{' '}
              {subscription.remaining_credits ?? 'Sınırsız'}
            </p>
            <p>
              Bitiş:{' '}
              {new Date(subscription.expires_at).toLocaleDateString('tr-TR')}
            </p>
            <button
              className="button button-secondary"
              onClick={cancelSubscription}
              type="button"
            >
              Aboneliği iptal et
            </button>
          </div>
        ) : (
          <p>Aktif aboneliğiniz yok.</p>
        )}
      </section>
    </section>
  )
}
