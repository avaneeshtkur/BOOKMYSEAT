# BookMySeat — Payment gateway fix

Django movie booking app with Razorpay test-mode checkout.

## Setup

```bash
cd fix-payment-newsletter-gateway
python -m venv .venv && source .venv/bin/activate
pip install django razorpay python-dotenv
python manage.py migrate
python manage.py seed_data   # optional demo data
python manage.py runserver
```

Set Razorpay test credentials (or use defaults in `bookmyseat/settings.py` for local dev):

```bash
export RAZORPAY_KEY_ID=rzp_test_...
export RAZORPAY_KEY_SECRET=...
```

## Payment verification (manual)

1. Log in, pick a movie show, select seats, and proceed to payment.
2. On the payment page, confirm the network tab loads `https://checkout.razorpay.com/v1/checkout.js` (status 200, no CSP block).
3. Confirm the page shows a valid `order_id` (Razorpay `order_...`) from the server-rendered summary.
4. Click **Pay ₹… Securely** — the Razorpay popup should open (not a mock QR or OTP screen).
5. Complete a test payment (e.g. UPI `success@razorpay` or Razorpay test card).
6. After success, the browser should POST to `/movies/verify-payment/` and redirect to the booking confirmation page (same tab, not a blank window).
7. Cancel or fail payment — you should land on the payment-failed page with an error message.

## Troubleshooting

| Symptom | Check |
|--------|--------|
| “Payment gateway unavailable” banner | `checkout.js` blocked or failed to load; ad blocker / offline network |
| Order creation error on seat submit | `razorpay` package installed; valid `RAZORPAY_KEY_ID` / `RAZORPAY_KEY_SECRET` |
| Signature verification failed | Order ID on page must match the order used in the popup; do not refresh payment page after order is created |

Mock checkout UI (`process-mock-payment`, fake QR, OTP) has been removed from the normal flow. The `process_mock_payment` endpoint remains for legacy tests only.
