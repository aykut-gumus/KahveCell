# KahveCell

FastAPI ve SQLite tabanlı kahve abonelik backend'i. GSM/OTP ile giriş, abonelik ve simüle ödeme, konuma göre dükkân keşfi, abonelik hakkıyla sipariş ve HMAC imzalı QR doğrulaması sağlar.

Backend'i `backend` klasöründe başlatın:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

Swagger: <http://localhost:8000/docs>

## Frontend

React 19, Vite, React Router, Leaflet ve QR kod bileşeni kullanılır. Backend API adresi varsayılan olarak `http://localhost:8000/api/v1` değerindedir; farklıysa `frontend/.env.example` dosyasını `.env.local` olarak kopyalayıp `VITE_API_BASE_URL` değerini güncelleyin.

```powershell
cd frontend
npm install
npm run dev
```

Tarayıcı: <http://localhost:5173>

## API

**19 adet `/api/v1` endpoint'i** ve ayrıca `/` sağlık kontrolü bulunur.

| Method | Endpoint | İşlev |
|---|---|---|
| POST | `/api/v1/auth/register` | GSM ile kayıt/giriş için OTP iste (simülasyon kodu: `1234`) |
| POST | `/api/v1/auth/verify-otp` | OTP doğrula, access ve refresh token al |
| POST | `/api/v1/auth/refresh` | Refresh token'ı döndürerek oturumu yenile |
| GET, PATCH | `/api/v1/auth/me` | Profil ve kahve tercihlerini görüntüle/güncelle |
| PATCH | `/api/v1/admin/users/{user_id}/role` | Kullanıcı rolünü değiştir |
| GET | `/api/v1/subscriptions/plans` | Starter, Premium ve Unlimited paketlerini listele |
| GET | `/api/v1/subscriptions/me` | Aktif abonelik ve kalan kahve hakkı |
| POST | `/api/v1/subscriptions/cancel` | Aktif aboneliği iptal et |
| POST | `/api/v1/payments/process` | Mock kartla abonelik satın al/yükselt/yenile |
| GET | `/api/v1/payments/history` | Kullanıcının ödeme geçmişi |
| GET | `/api/v1/shops` | Dükkânları listele; `search`, `latitude`, `longitude` ile ara/sırala |
| GET | `/api/v1/shops/{shop_id}` | Dükkân detayını ve menüsünü getir |
| POST | `/api/v1/orders` | Aktif abonelik hakkıyla sipariş oluştur ve QR üret |
| GET | `/api/v1/orders/me` | Müşterinin sipariş geçmişi ve durumları |
| POST | `/api/v1/orders/verify-qr` | Dükkân sahibi için QR imzasını doğrula |
| GET | `/api/v1/shops/{shop_id}/orders` | Yetkili dükkânın siparişlerini listele |
| PATCH | `/api/v1/shops/{shop_id}/orders/{order_id}/status` | Siparişi sırayla kabul et, hazırla ve teslim et |
| PUT | `/api/v1/admin/shops/{shop_id}/owner` | Dükkâna dükkân sahibi ata |

`/` sağlık kontrolü API v1 endpoint sayısına dahil değildir. Ödeme simülasyonunda `4242-4242-4242-4242` başarılı, `4000-0000-0000-0002` başarısızdır.

## Veritabanı

SQLite veritabanında **9 tablo** bulunur:

| Tablo | Tutulan veriler |
|---|---|
| `users` | GSM, profil, rol ve kahve tercihleri |
| `otp_challenges` | OTP özeti, deneme sayısı ve geçerlilik süresi |
| `refresh_sessions` | Kullanıcı oturumu, bitiş ve iptal bilgisi |
| `subscriptions` | Paket, fiyat, kahve hakkı, durum ve dönem |
| `payments` | İşlem kimliği, paket, tutar, sonuç ve abonelik bağlantısı; kart numarası saklanmaz |
| `shops` | Dükkân adı, adres, koordinat, saatler ve puan |
| `shop_ownerships` | Dükkân ile yetkili sahibi arasındaki atama |
| `products` | Dükkân menüsü, fiyat ve uygunluk |
| `orders` | Müşteri, dükkân, ürün, durum, özelleştirme ve imzalı QR JSON'u |
