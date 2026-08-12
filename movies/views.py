import json
import uuid
import logging
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
from django.db.models import Count
from django.core.paginator import Paginator
from django.utils import timezone
from django.conf import settings
from .models import Movie, Show, Booking, SeatBooking, Payment, SeatLock
from .tasks import send_booking_confirmation_email
from . import payments as payment_utils

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────
#  MOVIE BROWSING VIEWS (unchanged)
# ─────────────────────────────────────────────────────────────────

def movie_list(request):
    sort_param = request.GET.get("sort", "-release_date")
    valid_sorts = ["-release_date", "release_date", "-rating", "rating", "title", "-title"]
    
    if sort_param in valid_sorts:
        movies = Movie.objects.all().order_by(sort_param)
    else:
        movies = Movie.objects.all().order_by("-release_date")
        sort_param = "-release_date"
    
    selected_genres = [g for g in request.GET.getlist("genre") if g]
    selected_languages = [l for l in request.GET.getlist("language") if l]
    base_qs = movies

    if selected_genres:
        movies = movies.filter(genre__in=selected_genres)
    if selected_languages:
        movies = movies.filter(language__in=selected_languages)
        
    genre_counts_qs = base_qs
    if selected_languages:
        genre_counts_qs = genre_counts_qs.filter(language__in=selected_languages)
    genre_counts = dict(genre_counts_qs.values_list("genre").annotate(c=Count("id")))

    language_counts_qs = base_qs
    if selected_genres:
        language_counts_qs = language_counts_qs.filter(genre__in=selected_genres)
    language_counts = dict(language_counts_qs.values_list("language").annotate(c=Count("id")))

    genres_with_counts = [
        {"value": code, "label": label, "count": genre_counts.get(code, 0)}
        for code, label in Movie.GENRE_CHOICES
    ]
    languages_with_counts = [
        {"value": code, "label": label, "count": language_counts.get(code, 0)}
        for code, label in Movie.LANGUAGE_CHOICES
    ]
    
    paginator = Paginator(movies, 12)
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


# ─────────────────────────────────────────────────────────────────
#  SEAT SELECTION (updated to use SeatLock for blocked display)
# ─────────────────────────────────────────────────────────────────

@login_required
def select_seats(request, show_id):
    show = get_object_or_404(
        Show.objects.select_related("movie", "screen", "screen__theater"),
        pk=show_id,
    )
    screen = show.screen

    # Confirmed booked seats
    booked_seats = set()
    for sb in SeatBooking.objects.filter(
        booking__show=show, booking__status="confirmed"
    ):
        booked_seats.add((sb.row_letter, sb.seat_number))

    # Phase 8: Temporarily locked seats (exclude own user's locks so they can still pay)
    locked_seats = set()
    for lock in SeatLock.objects.filter(show=show, expires_at__gt=timezone.now()).exclude(user=request.user):
        locked_seats.add((lock.row_letter, lock.seat_number))

    rows = []
    for r in range(screen.total_rows):
        row_letter = chr(65 + r)
        seats = []
        for s in range(1, screen.seats_per_row + 1):
            key = (row_letter, s)
            seats.append({
                "number": s,
                "booked": key in booked_seats,
                "locked": key in locked_seats,  # shows as "held" in UI
            })
        rows.append({"letter": row_letter, "seats": seats})

    return render(request, "movies/select_seats.html", {
        "show": show,
        "rows": rows,
        "price": float(show.price),
    })


# ─────────────────────────────────────────────────────────────────
#  PHASE 8: SEAT LOCKING ENDPOINT
# ─────────────────────────────────────────────────────────────────

@login_required
@require_POST
def lock_seats(request):
    """
    API: Temporarily lock the selected seats for 2 minutes while user pays.
    CORE: Uses Database-level concurrency control (atomic transactions).
    """
    try:
        data = json.loads(request.body)
        show_id = data.get("show_id")
        seats_data = data.get("seats", [])
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid request body."}, status=400)

    if not show_id or not seats_data:
        return JsonResponse({"error": "show_id and seats are required."}, status=400)

    show = get_object_or_404(Show, pk=show_id)
    now = timezone.now()

    try:
        with transaction.atomic():
            # 1. Lock the 'Show' record conceptually to serialize multiple lock requests for this show
            # (or use a more granular approach, but this is robust for SQLite/standard DBs)
            Show.objects.select_for_update().get(pk=show_id)

            # 2. Cleanup expired locks for this show immediately
            SeatLock.objects.filter(show=show, expires_at__lte=now).delete()

            # 3. Check for confirmed bookings
            booked = set(
                SeatBooking.objects.filter(booking__show=show, booking__status="confirmed")
                .values_list("row_letter", "seat_number")
            )

            # 4. Check for current active locks (excluding this user)
            currently_locked = set(
                SeatLock.objects.filter(show=show, expires_at__gt=now)
                .exclude(user=request.user)
                .values_list("row_letter", "seat_number")
            )

            conflicts = []
            new_locks = []
            for seat in seats_data:
                row = seat["row"]
                num = int(seat["number"])
                key = (row, num)
                
                if key in booked or key in currently_locked:
                    conflicts.append(f"{row}{num}")
                else:
                    new_locks.append(SeatLock(
                        show=show,
                        user=request.user,
                        row_letter=row,
                        seat_number=num,
                    ))

            # 5. Multi-seat Transaction Logic (Phase 7):
            # If any seat is unavailable, we fail the entire request.
            if conflicts:
                return JsonResponse({
                    "error": f"Seats {', '.join(conflicts)} are no longer available.",
                    "conflicts": conflicts,
                }, status=409)

            # 6. Release any existing locks ONLY for this user/show before creating new ones
            SeatLock.objects.filter(show=show, user=request.user).delete()

            # 7. Create all locks atomically
            SeatLock.objects.bulk_create(new_locks)
            
            # The bulk_create is part of the atomic transaction
            expiry = now + timezone.timedelta(minutes=2)

            logger.info(f"[Concurrency] User {request.user.username} locked {len(new_locks)} seats for show {show_id}")
            return JsonResponse({
                "success": True,
                "lock_expiry": expiry.isoformat(),
                "locked_count": len(new_locks),
            })

    except Exception as e:
        logger.error(f"[Concurrency] Seat locking failed: {str(e)}")
        return JsonResponse({"error": "An internal error occurred during seat reservation."}, status=500)


@login_required
def get_seat_status(request, show_id):
    """
    API: Returns the current status of all seats for a show.
    Used for real-time UI updates.
    """
    show = get_object_or_404(Show, pk=show_id)
    now = timezone.now()

    # Get all confirmed bookings
    booked = set(
        SeatBooking.objects.filter(booking__show=show, booking__status="confirmed")
        .values_list("row_letter", "seat_number")
    )

    # Get all active locks
    locked = {}
    for lock in SeatLock.objects.filter(show=show, expires_at__gt=now):
        key = f"{lock.row_letter}{lock.seat_number}"
        locked[key] = {
            "user": lock.user.username,
            "is_mine": lock.user == request.user,
            "expires_in": int((lock.expires_at - now).total_seconds())
        }

    return JsonResponse({
        "show_id": show_id,
        "booked": [f"{r}{n}" for r, n in booked],
        "locked": locked,
    })


@login_required
@require_POST
def release_seats(request):
    """
    API: Manually release seats locked by the current user.
    Useful if the user cancels or navigates away.
    """
    try:
        data = json.loads(request.body)
        show_id = data.get("show_id")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid request."}, status=400)

    if not show_id:
        return JsonResponse({"error": "show_id is required."}, status=400)

    deleted_count, _ = SeatLock.objects.filter(show_id=show_id, user=request.user).delete()
    
    return JsonResponse({
        "success": True,
        "released_count": deleted_count
    })


# ─────────────────────────────────────────────────────────────────
#  PHASE 1 & 4: PAYMENT ORDER CREATION
# ─────────────────────────────────────────────────────────────────

@login_required
@require_POST
def payment_page(request):
    """
    Step 1: User selects seats → POST here.
    Validates seats, locks them for 10 minutes in DB, and renders the payment page.
    """
    show_id = request.POST.get("show_id")
    seats_json = request.POST.get("seats", "[]")

    try:
        selected_seats = json.loads(seats_json)
    except json.JSONDecodeError:
        selected_seats = []

    if not selected_seats or not show_id:
        return redirect("movies:movie_list")

    show = get_object_or_404(Show, pk=show_id)
    now = timezone.now()

    with transaction.atomic():
        # Cleanup expired locks for this show
        SeatLock.objects.filter(show=show, expires_at__lte=now).delete()

        # Confirmed booked seats
        booked = set(
            SeatBooking.objects.filter(booking__show=show, booking__status="confirmed")
            .values_list("row_letter", "seat_number")
        )

        # Active locks by OTHER users
        locked_by_others = set(
            SeatLock.objects.filter(show=show, expires_at__gt=now)
            .exclude(user=request.user)
            .values_list("row_letter", "seat_number")
        )

        valid_seats = []
        conflicts = []
        for seat in selected_seats:
            key = (seat["row"], int(seat["number"]))
            if key in booked or key in locked_by_others:
                conflicts.append(f"{seat['row']}{seat['number']}")
            else:
                valid_seats.append(key)

        if conflicts or not valid_seats:
            from django.contrib import messages
            messages.error(
                request,
                f"Seats {', '.join(conflicts)} are currently held or booked by another user. Please select available seats."
            )
            return redirect("movies:select_seats", show_id=show.pk)

        # Create/Renew 10-minute locks for request.user on this show
        SeatLock.objects.filter(show=show, user=request.user).delete()
        new_locks = [
            SeatLock(
                show=show,
                user=request.user,
                row_letter=r,
                seat_number=n,
                expires_at=now + timedelta(minutes=10),
            )
            for r, n in valid_seats
        ]
        SeatLock.objects.bulk_create(new_locks)

    total_price = len(valid_seats) * show.price

    return render(request, "movies/payment.html", {
        "show": show,
        "valid_seats": valid_seats,
        "total_price": total_price,
        "seats_json": json.dumps([{"row": r, "number": n} for r, n in valid_seats]),
        "show_id": show_id,
    })


@login_required
@require_POST
def process_dummy_payment(request):
    """
    Dummy Payment Gateway:
    Takes show_id and seats. Directly creates confirmed booking + dummy payment.
    """
    try:
        data = json.loads(request.body)
        show_id = data.get("show_id")
        seats = data.get("seats", [])
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid request."}, status=400)

    if not show_id or not seats:
        return JsonResponse({"error": "show_id and seats are required."}, status=400)

    show = get_object_or_404(Show, pk=show_id)
    total_price = len(seats) * float(show.price)
    order_id = f"dummy_order_{uuid.uuid4().hex[:8]}"

    try:
        with transaction.atomic():
            booking = Booking.objects.create(
                user=request.user,
                show=show,
                total_price=total_price,
                status="confirmed",
                razorpay_order_id=order_id,
            )
            # Save seats
            for seat in seats:
                SeatBooking.objects.create(
                    booking=booking,
                    row_letter=seat["row"],
                    seat_number=int(seat["number"]),
                )
            # Create Dummy Payment
            Payment.objects.create(
                booking=booking,
                razorpay_order_id=order_id,
                razorpay_payment_id=f"pay_dummy_{uuid.uuid4().hex[:8]}",
                amount=int(total_price * 100),
                currency="INR",
                idempotency_key=uuid.uuid4(),
                status="success",
                signature_verified=True,
            )

            # Release seat locks
            SeatLock.objects.filter(show=show, user=request.user).delete()

            # Schedule email
            try:
                send_booking_confirmation_email.delay(booking.pk)
            except Exception as e:
                logger.error(f"[Email] Failed to queue confirmation email: {e}")

        logger.info(f"[Payment] ✅ Dummy Booking #{booking.pk} CONFIRMED.")
        return JsonResponse({
            "success": True,
            "booking_id": booking.pk,
            "redirect_url": f"/movies/booking/{booking.pk}/",
        })


    except Exception as e:
        logger.error(f"[Payment] Dummy Payment failed: {e}")
        return JsonResponse({"error": "Payment processing failed."}, status=500)


@login_required
@require_POST
def create_razorpay_order(request):
    """
    Phase 1 Step 1: Create a Razorpay order.
    Validates seats, creates a pending Booking, creates the Razorpay order via SDK,
    and returns {order_id, amount, currency, key} to the frontend.
    """
    import razorpay as _razorpay
    import os
    _key_id     = os.environ.get('RAZORPAY_KEY_ID')
    _key_secret = os.environ.get('RAZORPAY_KEY_SECRET')
    client = _razorpay.Client(auth=(_key_id, _key_secret))

    try:
        data    = json.loads(request.body)
        show_id = data.get('show_id')
        seats   = data.get('seats', [])
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid request.'}, status=400)

    if not show_id or not seats:
        return JsonResponse({'error': 'show_id and seats are required.'}, status=400)

    show = get_object_or_404(Show, pk=show_id)

    # Revalidate seats against confirmed bookings
    booked = set(
        SeatBooking.objects.filter(booking__show=show, booking__status='confirmed')
        .values_list('row_letter', 'seat_number')
    )
    for seat in seats:
        if (seat['row'], int(seat['number'])) in booked:
            return JsonResponse({'error': f"Seat {seat['row']}{seat['number']} is already booked."}, status=400)

    total_price  = len(seats) * float(show.price)
    amount_paise = int(total_price * 100)  # Razorpay uses paise

    try:
        with transaction.atomic():
            # Create pending Booking
            booking = Booking.objects.create(
                user=request.user,
                show=show,
                total_price=total_price,
                status='pending',
            )
            # Save seats
            for seat in seats:
                SeatBooking.objects.create(
                    booking=booking,
                    row_letter=seat['row'],
                    seat_number=int(seat['number']),
                )

            # Create Razorpay order via SDK
            order = client.order.create({
                'amount':          amount_paise,
                'currency':        'INR',
                'payment_capture': 1,
            })

            # Attach order ID to booking
            booking.razorpay_order_id = order['id']
            booking.save()

            # Create Payment record
            Payment.objects.create(
                booking=booking,
                razorpay_order_id=order['id'],
                amount=order['amount'],
                currency=order['currency'],
                status='created',
            )

        return JsonResponse({
            'order_id':   order['id'],
            'booking_id': booking.pk,
            'amount':     order['amount'],
            'currency':   order['currency'],
            'key':        _key_id,
        })

    except Exception as e:
        logger.error(f'[Payment] create_razorpay_order failed: {e}')
        return JsonResponse({'error': 'Failed to create payment order.'}, status=500)


from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import redirect
from django.contrib.auth import login

@csrf_exempt
@require_POST
def verify_razorpay_payment(request):
    """
    Phase 1 Step 2: Verify Razorpay payment signature via callback_url.
    Supports form-urlencoded POST from Razorpay.
    """
    import razorpay as _razorpay
    import os
    _key_id     = os.environ.get('RAZORPAY_KEY_ID')
    _key_secret = os.environ.get('RAZORPAY_KEY_SECRET')
    client = _razorpay.Client(auth=(_key_id, _key_secret))

    payment_id = request.POST.get('razorpay_payment_id')
    order_id   = request.POST.get('razorpay_order_id')
    signature  = request.POST.get('razorpay_signature')

    if not all([payment_id, order_id, signature]):
        logger.error('[Payment] Missing verification parameters in callback.')
        return redirect('movies:movie_list')

    # Verify signature using the official SDK utility
    try:
        client.utility.verify_payment_signature({
            'razorpay_order_id':   order_id,
            'razorpay_payment_id': payment_id,
            'razorpay_signature':  signature,
        })
        is_valid = True
    except Exception:
        is_valid = False

    # Look up Booking by Razorpay Order ID (request.user may be anonymous due to SameSite cookie drops)
    booking = get_object_or_404(Booking, razorpay_order_id=order_id)
    payment = get_object_or_404(Payment, razorpay_order_id=order_id, booking=booking)

    try:
        if is_valid:
            with transaction.atomic():
                booking.status = 'confirmed'
                booking.save()
                payment.razorpay_payment_id = payment_id
                payment.razorpay_signature  = signature
                payment.status              = 'success'
                payment.signature_verified  = True
                payment.save()
                SeatLock.objects.filter(show=booking.show).delete()
                try:
                    send_booking_confirmation_email.delay(booking.pk)
                except Exception as e:
                    logger.error(f'[Email] Failed to queue confirmation email: {e}')

            # Authenticate the user manually if session was dropped
            if not request.user.is_authenticated:
                login(request, booking.user)

            logger.info(f'[Payment] ✅ Razorpay Booking #{booking.pk} CONFIRMED.')
            return redirect('movies:booking_confirmation', booking_id=booking.id)
        else:
            with transaction.atomic():
                booking.status = 'failed'
                booking.save()
                payment.status = 'failed'
                payment.save()
            logger.error('[Payment] Signature verification failed in callback.')
            return redirect('movies:movie_list')

    except Exception as e:
        logger.error(f'[Payment] verify_razorpay_payment failed: {e}')
        return redirect('movies:movie_list')



@require_POST
@login_required
def cancel_payment(request):
    try:
        data = json.loads(request.body)
        booking_id = data.get('booking_id')
        if booking_id:
            try:
                booking = Booking.objects.get(id=booking_id, user=request.user)
            except (Booking.DoesNotExist, ValueError):
                booking = Booking.objects.get(razorpay_order_id=booking_id, user=request.user)
            booking.status = 'cancelled'
            booking.save()
            # Release the seats back to available
            try:
                booking.seats.update(is_booked=False)
            except Exception:
                pass
            SeatLock.objects.filter(show=booking.show, user=request.user).delete()
    except Exception:
        pass
    return JsonResponse({'status': 'cancelled'})


# ─────────────────────────────────────────────────────────────────
#  BOOKING HISTORY & CONFIRMATION (updated for new status types)
# ─────────────────────────────────────────────────────────────────

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
