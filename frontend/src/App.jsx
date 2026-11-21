import { Route, Routes } from 'react-router-dom'
import AppLayout from './components/AppLayout'
import ProtectedRoute from './components/ProtectedRoute'
import AuthPage from './pages/AuthPage'
import HistoryPage from './pages/HistoryPage'
import HomePage from './pages/HomePage'
import NotFoundPage from './pages/NotFoundPage'
import OrderPage from './pages/OrderPage'
import QrPage from './pages/QrPage'
import ShopDetailsPage from './pages/ShopDetailsPage'
import SubscriptionPage from './pages/SubscriptionPage'
import './App.css'

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<AuthPage mode="login" />} />
      <Route path="/register" element={<AuthPage mode="register" />} />
      <Route element={<ProtectedRoute />}>
        <Route element={<AppLayout />}>
          <Route index element={<HomePage />} />
          <Route path="shops/:shopId" element={<ShopDetailsPage />} />
          <Route path="shops/:shopId/order" element={<OrderPage />} />
          <Route path="orders/:orderId/qr" element={<QrPage />} />
          <Route path="history" element={<HistoryPage />} />
          <Route path="subscription" element={<SubscriptionPage />} />
        </Route>
      </Route>
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  )
}
