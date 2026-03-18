from django.urls import path
from . import views

app_name = "movies"

urlpatterns = [
    path("", views.movie_list, name="movie_list"),
    path("<int:movie_id>/", views.movie_detail, name="movie_detail"),
    path("show/<int:show_id>/seats/", views.select_seats, name="select_seats"),
    path("payment/", views.payment, name="payment"),
    path("book/", views.book_seats, name="book_seats"),
    path("booking/<int:booking_id>/", views.booking_confirmation, name="booking_confirmation"),
    path("my-bookings/", views.booking_history, name="booking_history"),
]
