from django.contrib import admin
from .models import Movie, Theater, Screen, Show, Booking, SeatBooking


class SeatBookingInline(admin.TabularInline):
    model = SeatBooking
    extra = 0
    readonly_fields = ("row_letter", "seat_number")


@admin.register(Movie)
class MovieAdmin(admin.ModelAdmin):
    list_display = ("title", "genre", "language", "duration_minutes", "rating", "release_date")
    list_filter = ("genre", "language")
    search_fields = ("title",)


@admin.register(Theater)
class TheaterAdmin(admin.ModelAdmin):
    list_display = ("name", "location")
    search_fields = ("name", "location")


@admin.register(Screen)
class ScreenAdmin(admin.ModelAdmin):
    list_display = ("name", "theater", "total_rows", "seats_per_row")
    list_filter = ("theater",)


@admin.register(Show)
class ShowAdmin(admin.ModelAdmin):
    list_display = ("movie", "screen", "show_date", "show_time", "price")
    list_filter = ("show_date", "movie", "screen__theater")
    search_fields = ("movie__title",)


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "show", "booking_time", "total_price", "status")
    list_filter = ("status",)
    search_fields = ("user__username", "show__movie__title")
    inlines = [SeatBookingInline]


@admin.register(SeatBooking)
class SeatBookingAdmin(admin.ModelAdmin):
    list_display = ("booking", "row_letter", "seat_number")
