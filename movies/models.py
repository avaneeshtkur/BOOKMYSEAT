from django.db import models
from django.contrib.auth.models import User


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
    genre = models.CharField(max_length=20, choices=GENRE_CHOICES, default="action")
    language = models.CharField(max_length=20, choices=LANGUAGE_CHOICES, default="english")
    duration_minutes = models.PositiveIntegerField(default=120)
    release_date = models.DateField(null=True, blank=True)
    rating = models.DecimalField(max_digits=3, decimal_places=1, default=0.0)
    poster = models.ImageField(upload_to="posters/", blank=True, null=True)

    def __str__(self):
        return self.title


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


class Booking(models.Model):
    STATUS_CHOICES = [
        ("confirmed", "Confirmed"),
        ("cancelled", "Cancelled"),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="bookings")
    show = models.ForeignKey(Show, on_delete=models.CASCADE, related_name="bookings")
    booking_time = models.DateTimeField(auto_now_add=True)
    total_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="confirmed")

    def __str__(self):
        return f"Booking #{self.pk} — {self.user.username} — {self.show.movie.title}"


class SeatBooking(models.Model):
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name="seats")
    row_letter = models.CharField(max_length=2)
    seat_number = models.PositiveIntegerField()

    class Meta:
        unique_together = ("booking", "row_letter", "seat_number")

    def __str__(self):
        return f"{self.row_letter}{self.seat_number}"
