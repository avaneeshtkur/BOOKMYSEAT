from django.urls import path
from . import views

app_name = "movies"

urlpatterns = [
    # ── Movie Browsing ──
    path("", views.movie_list, name="movie_list"),
    path("<int:movie_id>/", views.movie_detail, name="movie_detail"),
    path("show/<int:show_id>/seats/", views.select_seats, name="select_seats"),

    # ── Payment Flow ──
    # Step 1: User arrives at payment page (seats validated)
    path("payment/", views.payment_page, name="payment"),
    # Step 2: Single Dummy Endpoint
    path("payment/process-dummy/", views.process_dummy_payment, name="process_dummy_payment"),
    # Step 3: Razorpay Checkout Endpoints
    path("payment/create-order/", views.create_razorpay_order, name="create_razorpay_order"),
    path("payment/verify/", views.verify_razorpay_payment, name="verify_razorpay_payment"),
    path("payment/cancel/", views.cancel_payment, name="cancel_payment"),

    # ── Seat Locking (Phase 8) ──
    path("seats/lock/", views.lock_seats, name="lock_seats"),
    path("seats/status/<int:show_id>/", views.get_seat_status, name="get_seat_status"),
    path("seats/release/", views.release_seats, name="release_seats"),

    # ── Booking History ──
    path("booking/<int:booking_id>/", views.booking_confirmation, name="booking_confirmation"),
    path("my-bookings/", views.booking_history, name="booking_history"),
]
