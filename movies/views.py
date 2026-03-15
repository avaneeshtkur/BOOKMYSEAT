import json
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from .models import Movie, Show, Booking, SeatBooking


def movie_list(request):
    movies = Movie.objects.all().order_by("-release_date")
    genre = request.GET.get("genre")
    language = request.GET.get("language")
    if genre:
        movies = movies.filter(genre=genre)
    if language:
        movies = movies.filter(language=language)
    return render(request, "movies/movie_list.html", {
        "movies": movies,
        "genres": Movie.GENRE_CHOICES,
        "languages": Movie.LANGUAGE_CHOICES,
        "selected_genre": genre or "",
        "selected_language": language or "",
    })


def movie_detail(request, movie_id):
    movie = get_object_or_404(Movie, pk=movie_id)
    shows = movie.shows.select_related("screen", "screen__theater").order_by("show_date", "show_time")
    return render(request, "movies/movie_detail.html", {
        "movie": movie,
        "shows": shows,
    })


@login_required
def select_seats(request, show_id):
    show = get_object_or_404(
        Show.objects.select_related("movie", "screen", "screen__theater"),
        pk=show_id,
    )
    screen = show.screen
    rows = []
    # Build seat map
    booked_seats = set()
    for sb in SeatBooking.objects.filter(
        booking__show=show, booking__status="confirmed"
    ):
        booked_seats.add((sb.row_letter, sb.seat_number))

    for r in range(screen.total_rows):
        row_letter = chr(65 + r)  # A, B, C, …
        seats = []
        for s in range(1, screen.seats_per_row + 1):
            seats.append({
                "number": s,
                "booked": (row_letter, s) in booked_seats,
            })
        rows.append({"letter": row_letter, "seats": seats})

    return render(request, "movies/select_seats.html", {
        "show": show,
        "rows": rows,
        "price": float(show.price),
    })


@login_required
@require_POST
def book_seats(request):
    show_id = request.POST.get("show_id")
    seats_json = request.POST.get("seats", "[]")

    try:
        selected_seats = json.loads(seats_json)
    except json.JSONDecodeError:
        selected_seats = []

    if not selected_seats or not show_id:
        return redirect("movie_list")

    show = get_object_or_404(Show, pk=show_id)

    # Check if any of the selected seats are already booked
    booked = set()
    for sb in SeatBooking.objects.filter(
        booking__show=show, booking__status="confirmed"
    ):
        booked.add((sb.row_letter, sb.seat_number))

    valid_seats = []
    for seat in selected_seats:
        key = (seat["row"], int(seat["number"]))
        if key not in booked:
            valid_seats.append(key)

    if not valid_seats:
        return redirect("select_seats", show_id=show.pk)

    total_price = len(valid_seats) * show.price

    booking = Booking.objects.create(
        user=request.user,
        show=show,
        total_price=total_price,
        status="confirmed",
    )
    for row_letter, seat_number in valid_seats:
        SeatBooking.objects.create(
            booking=booking,
            row_letter=row_letter,
            seat_number=seat_number,
        )

    return redirect("booking_confirmation", booking_id=booking.pk)


@login_required
def booking_confirmation(request, booking_id):
    booking = get_object_or_404(
        Booking.objects.select_related("show__movie", "show__screen", "show__screen__theater"),
        pk=booking_id,
        user=request.user,
    )
    seats = booking.seats.all().order_by("row_letter", "seat_number")
    return render(request, "movies/booking_confirmation.html", {
        "booking": booking,
        "seats": seats,
    })


@login_required
def booking_history(request):
    bookings = (
        Booking.objects.filter(user=request.user)
        .select_related("show__movie", "show__screen", "show__screen__theater")
        .prefetch_related("seats")
        .order_by("-booking_time")
    )
    return render(request, "movies/booking_history.html", {"bookings": bookings})
