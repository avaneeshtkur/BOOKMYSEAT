from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
import uuid


class Movie(models.Model):
    GENRE_CHOICES = [
        ("action", "Action"),
        ("comedy", "Comedy"),
        ("drama", "Drama"),
        ("horror", "Horror"),
        ("romance", "Romance"),
        ("scifi", "Sci-Fi"),
        ("thriller", "Thriller"),
        ("animation", "Animation"),
    ]
    LANGUAGE_CHOICES = [
        ("english", "English"),
        ("hindi", "Hindi"),
        ("tamil", "Tamil"),
        ("telugu", "Telugu"),
        ("others", "Others"),
    ]
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    genre = models.CharField(max_length=20, choices=GENRE_CHOICES, default="action", db_index=True)
    language = models.CharField(max_length=20, choices=LANGUAGE_CHOICES, default="english", db_index=True)
    duration_minutes = models.PositiveIntegerField(default=120)
    release_date = models.DateField(null=True, blank=True)
    rating = models.DecimalField(max_digits=3, decimal_places=1, default=0.0)
    poster = models.ImageField(upload_to="posters/", blank=True, null=True)
    trailer_url = models.URLField(max_length=500, blank=True, null=True, help_text="YouTube trailer URL")

    def __str__(self):
        return self.title

    @property
    def poster_url(self):
        if self.poster:
            import os
            from django.templatetags.static import static
            name = os.path.basename(self.poster.name)
            return static(f"posters/{name}")
        return ""

    class Meta:
        indexes = [
            models.Index(fields=["genre", "language"]),
        ]


class Theater(models.Model):
    name = models.CharField(max_length=255)
    location = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.name} — {self.location}"


class Screen(models.Model):
    theater = models.ForeignKey(Theater, on_delete=models.CASCADE, related_name="screens")
    name = models.CharField(max_length=50)
    total_rows = models.PositiveIntegerField(default=8)
    seats_per_row = models.PositiveIntegerField(default=10)

    def __str__(self):
        return f"{self.name} @ {self.theater.name}"


class Show(models.Model):
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE, related_name="shows")
    screen = models.ForeignKey(Screen, on_delete=models.CASCADE, related_name="shows")
    show_date = models.DateField()
    show_time = models.TimeField()
    price = models.DecimalField(max_digits=8, decimal_places=2, default=200.00)

    class Meta:
        ordering = ["show_date", "show_time"]

    def __str__(self):
        return f"{self.movie.title} | {self.screen} | {self.show_date} {self.show_time}"


# ─────────────────────────────────────────────
# SEAT LOCKING — Phase 8
# Temporarily holds seats during payment (10 min TTL)
# ─────────────────────────────────────────────
def seat_lock_expiry():
    """Default: 2 minutes from now."""
    return timezone.now() + timedelta(minutes=2)


class SeatLock(models.Model):
    """
    Temporarily locks seats while the user is completing payment.
    Expired locks are automatically ignored when checking availability.
    """
    show = models.ForeignKey(Show, on_delete=models.CASCADE, related_name="seat_locks")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="seat_locks")
    row_letter = models.CharField(max_length=2)
    seat_number = models.PositiveIntegerField()
    locked_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(default=seat_lock_expiry)

    class Meta:
        unique_together = ("show", "row_letter", "seat_number")
        indexes = [
            models.Index(fields=["show", "expires_at"]),
        ]

    def is_expired(self):
        return timezone.now() > self.expires_at

    def __str__(self):
        return f"Lock: {self.row_letter}{self.seat_number} @ Show#{self.show_id} by {self.user.username}"


# ─────────────────────────────────────────────
# BOOKING MODEL — Updated with payment states
# ─────────────────────────────────────────────
class Booking(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending Payment"),
        ("confirmed", "Confirmed"),
        ("failed", "Payment Failed"),
        ("cancelled", "Cancelled"),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="bookings")
    show = models.ForeignKey(Show, on_delete=models.CASCADE, related_name="bookings")
    booking_time = models.DateTimeField(auto_now_add=True)
    total_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    # Razorpay order ID (set when order is created)
    razorpay_order_id = models.CharField(max_length=100, blank=True, null=True, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["razorpay_order_id"]),
            models.Index(fields=["status", "booking_time"]),
            models.Index(fields=["show", "status"]),
        ]

    def __str__(self):
        return f"Booking #{self.pk} — {self.user.username} — {self.show.movie.title} [{self.get_status_display()}]"


class SeatBooking(models.Model):
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name="seats")
    row_letter = models.CharField(max_length=2)
    seat_number = models.PositiveIntegerField()

    class Meta:
        unique_together = ("booking", "row_letter", "seat_number")

    def __str__(self):
        return f"{self.row_letter}{self.seat_number}"


# ─────────────────────────────────────────────
# PAYMENT MODEL — Phase 2 & 3
# Stores all payment attempts with idempotency key
# ─────────────────────────────────────────────
class Payment(models.Model):
    STATUS_CHOICES = [
        ("created", "Order Created"),
        ("success", "Payment Successful"),
        ("failed", "Payment Failed"),
        ("timeout", "Payment Timed Out"),
    ]

    booking = models.OneToOneField(Booking, on_delete=models.CASCADE, related_name="payment")
    # Razorpay identifiers
    razorpay_order_id = models.CharField(max_length=100, unique=True, db_index=True)
    razorpay_payment_id = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    razorpay_signature = models.CharField(max_length=256, blank=True, null=True)
    # Financial
    amount = models.PositiveIntegerField(help_text="Amount in paise (INR × 100)")
    currency = models.CharField(max_length=10, default="INR")
    # Status & security
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="created")
    signature_verified = models.BooleanField(default=False)
    # Idempotency — Phase 3
    idempotency_key = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True)
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["razorpay_order_id"]),
            models.Index(fields=["idempotency_key"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"Payment #{self.pk} | Order: {self.razorpay_order_id} | {self.get_status_display()}"
