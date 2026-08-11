from django.contrib import admin
from django.utils.html import format_html
from .models import Movie, Theater, Screen, Show, Booking, SeatBooking, Payment, SeatLock


@admin.register(Movie)
class MovieAdmin(admin.ModelAdmin):
    list_display = ("title", "genre", "language", "rating", "release_date")
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
    list_filter = ("show_date", "movie")
    date_hierarchy = "show_date"


class SeatBookingInline(admin.TabularInline):
    model = SeatBooking
    extra = 0
    readonly_fields = ("row_letter", "seat_number")


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "show", "status_badge", "total_price", "booking_time")
    list_filter = ("status", "booking_time")
    search_fields = ("user__username", "razorpay_order_id")
    readonly_fields = ("booking_time", "razorpay_order_id")
    inlines = [SeatBookingInline]
    date_hierarchy = "booking_time"

    def status_badge(self, obj):
        colors = {
            "confirmed": "#10b981",
            "pending": "#f59e0b",
            "failed": "#ef4444",
            "cancelled": "#6b7280",
        }
        color = colors.get(obj.status, "#6b7280")
        return format_html(
            '<span style="background:{};color:#fff;padding:3px 10px;border-radius:20px;font-size:0.8rem;">{}</span>',
            color,
            obj.get_status_display(),
        )
    status_badge.short_description = "Status"


# ── BONUS: Payment Admin — Full Transaction Log ──────────────────

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "id", "booking_link", "razorpay_order_id", "amount_display",
        "status_badge", "signature_verified", "created_at",
    )
    list_filter = ("status", "signature_verified", "created_at")
    search_fields = ("razorpay_order_id", "razorpay_payment_id", "booking__user__username")
    readonly_fields = (
        "booking", "razorpay_order_id", "razorpay_payment_id",
        "razorpay_signature", "idempotency_key", "created_at", "updated_at",
        "signature_verified",
    )
    date_hierarchy = "created_at"

    def booking_link(self, obj):
        return format_html(
            '<a href="/admin/movies/booking/{}/change/">Booking #{}</a>',
            obj.booking_id, obj.booking_id,
        )
    booking_link.short_description = "Booking"

    def amount_display(self, obj):
        return f"₹{obj.amount / 100:.2f}"
    amount_display.short_description = "Amount"

    def status_badge(self, obj):
        colors = {
            "created": "#6b7280",
            "success": "#10b981",
            "failed": "#ef4444",
            "timeout": "#f59e0b",
        }
        color = colors.get(obj.status, "#6b7280")
        return format_html(
            '<span style="background:{};color:#fff;padding:3px 10px;border-radius:20px;font-size:0.8rem;">{}</span>',
            color,
            obj.get_status_display(),
        )
    status_badge.short_description = "Status"


@admin.register(SeatLock)
class SeatLockAdmin(admin.ModelAdmin):
    list_display = ("show", "user", "row_letter", "seat_number", "expires_at", "is_expired")
    list_filter = ("show",)
    readonly_fields = ("locked_at",)

    def is_expired(self, obj):
        expired = obj.is_expired()
        return format_html(
            '<span style="color:{};">●</span> {}',
            "#ef4444" if expired else "#10b981",
            "Expired" if expired else "Active",
        )
    is_expired.short_description = "Status"
