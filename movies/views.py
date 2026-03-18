import json
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db.models import Count
from django.core.paginator import Paginator
from .models import Movie, Show, Booking, SeatBooking
from .tasks import send_booking_confirmation_email


def movie_list(request):
    sort_param = request.GET.get("sort", "-release_date")
    valid_sorts = ["-release_date", "release_date", "-rating", "rating", "title", "-title"]
    
    if sort_param in valid_sorts:
        movies = Movie.objects.all().order_by(sort_param)
    else:
        movies = Movie.objects.all().order_by("-release_date")
        sort_param = "-release_date"
    
    # Support for multi-select filtering
    selected_genres = request.GET.getlist("genre")
    selected_languages = request.GET.getlist("language")
    
    # Base queryset for faceting (aggregation)
    base_qs = movies

    if selected_genres:
        movies = movies.filter(genre__in=selected_genres)
    if selected_languages:
        movies = movies.filter(language__in=selected_languages)
        
    # Dynamic Faceting (Counts)
    # How many movies exist for each genre based on current language filters?
    genre_counts_qs = base_qs
    if selected_languages:
        genre_counts_qs = genre_counts_qs.filter(language__in=selected_languages)
    genre_counts = dict(genre_counts_qs.values_list("genre").annotate(c=Count("id")))

    # How many movies exist for each language based on current genre filters?
    language_counts_qs = base_qs
    if selected_genres:
        language_counts_qs = language_counts_qs.filter(genre__in=selected_genres)
    language_counts = dict(language_counts_qs.values_list("language").annotate(c=Count("id")))

    # Build final list of choices with dynamic counts
    genres_with_counts = [
        {"value": code, "label": label, "count": genre_counts.get(code, 0)}
        for code, label in Movie.GENRE_CHOICES
    ]
    languages_with_counts = [
        {"value": code, "label": label, "count": language_counts.get(code, 0)}
        for code, label in Movie.LANGUAGE_CHOICES
    ]
    
    # Pagination configuration
    paginator = Paginator(movies, 12)  # 12 movies per page
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    return render(request, "movies/movie_list.html", {
        "page_obj": page_obj,
        "genres": genres_with_counts,
        "languages": languages_with_counts,
        "selected_genres": selected_genres,
        "selected_languages": selected_languages,
        "selected_sort": sort_param,
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
def payment(request):
    show_id = request.POST.get("show_id")
    seats_json = request.POST.get("seats", "[]")

    try:
        selected_seats = json.loads(seats_json)
    except json.JSONDecodeError:
        selected_seats = []

    if not selected_seats or not show_id:
        return redirect("movies:movie_list")

    show = get_object_or_404(Show, pk=show_id)

    # Re-verify seats aren't booked
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
        return redirect("movies:select_seats", show_id=show.pk)

    total_price = len(valid_seats) * show.price

    # Pass the validated data forward to the hidden form on payment page
    return render(request, "movies/payment.html", {
        "show": show,
        "valid_seats": valid_seats,
        "total_price": total_price,
        "seats_json": json.dumps([{"row": r, "number": n} for r, n in valid_seats]),
        "show_id": show_id,
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
        return redirect("movies:movie_list")

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
        return redirect("movies:select_seats", show_id=show.pk)

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

    # Trigger background email immediately after booking is fully created
    send_booking_confirmation_email.delay(booking.pk)

    return redirect("movies:booking_confirmation", booking_id=booking.pk)


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
