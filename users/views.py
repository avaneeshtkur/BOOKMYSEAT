from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from .forms import UserRegisterForm, UserUpdateForm
from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.models import User
from django.db.models import Sum, Count, Q, F
from django.db.models.functions import TruncDay, TruncWeek, TruncMonth, ExtractHour
from django.core.cache import cache
from django.http import JsonResponse
from django.utils import timezone
from datetime import timedelta
import json
from movies.models import Movie, Booking, Show, Theater, SeatBooking, Screen


def home(request):
    movies = Movie.objects.all().order_by("-release_date")[:8]
    return render(request, "home.html", {"movies": movies})


def register(request):
    if request.method == "POST":
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            # If superuser toggle is on
            if request.POST.get("is_superuser") == "on":
                user.is_staff = True
                user.is_superuser = True
                user.save()

            # Log the user in with the correct backend specified
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            return redirect("profile")
    else:
        form = UserRegisterForm()
    return render(request, "users/register.html", {"form": form})


def login_view(request):
    if request.method == "POST":
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect("home")
    else:
        form = AuthenticationForm()
    return render(request, "users/login.html", {"form": form})


def index(request):
    if request.user.is_authenticated:
        return redirect("home")
    return redirect("login")


@login_required
def profile(request):
    bookings = (
        Booking.objects.filter(user=request.user)
        .select_related("show__movie", "show__screen", "show__screen__theater")
        .prefetch_related("seats")
        .order_by("-booking_time")[:5]
    )
    if request.method == "POST":
        u_form = UserUpdateForm(request.POST, instance=request.user)
        if u_form.is_valid():
            u_form.save()
            return redirect("profile")
    else:
        u_form = UserUpdateForm(instance=request.user)

    return render(request, "users/profile.html", {"u_form": u_form, "bookings": bookings})


@login_required
def reset_password(request):
    if request.method == "POST":
        form = PasswordChangeForm(user=request.user, data=request.POST)
        if form.is_valid():
            form.save()
            return redirect("login")
    else:
        form = PasswordChangeForm(user=request.user)
    return render(request, "users/reset_password.html", {"form": form})


def _compute_admin_analytics():
    """
    Computes all advanced admin analytics using DB-level aggregations.
    Optimized for large datasets (50,000+ bookings) without loading full tables into memory.
    """
    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    seven_days_ago = now - timedelta(days=7)
    four_weeks_ago = now - timedelta(days=28)
    six_months_ago = now - timedelta(days=180)

    # 1. Core KPIs
    total_users = User.objects.count()
    total_movies = Movie.objects.count()
    total_shows = Show.objects.count()
    total_theaters = Theater.objects.count()

    confirmed_qs = Booking.objects.filter(status="confirmed")
    total_confirmed_bookings = confirmed_qs.count()
    total_revenue = confirmed_qs.aggregate(total=Sum("total_price"))["total"] or 0

    today_revenue = confirmed_qs.filter(booking_time__gte=today_start).aggregate(
        total=Sum("total_price")
    )["total"] or 0

    # 2. Cancellation Rates
    all_bookings_count = Booking.objects.count()
    cancelled_count = Booking.objects.filter(status="cancelled").count()
    failed_count = Booking.objects.filter(status="failed").count()
    pending_count = Booking.objects.filter(status="pending").count()

    cancellation_rate = (
        round((cancelled_count / all_bookings_count) * 100, 1)
        if all_bookings_count > 0
        else 0.0
    )

    # 3. Time-Based Revenue Aggregations (Daily, Weekly, Monthly)
    # Daily Revenue (Last 7 Days)
    daily_revenue_qs = (
        confirmed_qs.filter(booking_time__gte=seven_days_ago)
        .annotate(period=TruncDay("booking_time"))
        .values("period")
        .annotate(revenue=Sum("total_price"), bookings=Count("id"))
        .order_by("period")
    )
    daily_labels = [item["period"].strftime("%b %d") for item in daily_revenue_qs]
    daily_data = [float(item["revenue"]) for item in daily_revenue_qs]

    # Weekly Revenue (Last 4 Weeks)
    weekly_revenue_qs = (
        confirmed_qs.filter(booking_time__gte=four_weeks_ago)
        .annotate(period=TruncWeek("booking_time"))
        .values("period")
        .annotate(revenue=Sum("total_price"), bookings=Count("id"))
        .order_by("period")
    )
    weekly_labels = [f"Week of {item['period'].strftime('%b %d')}" for item in weekly_revenue_qs]
    weekly_data = [float(item["revenue"]) for item in weekly_revenue_qs]

    # Monthly Revenue (Last 6 Months)
    monthly_revenue_qs = (
        confirmed_qs.filter(booking_time__gte=six_months_ago)
        .annotate(period=TruncMonth("booking_time"))
        .values("period")
        .annotate(revenue=Sum("total_price"), bookings=Count("id"))
        .order_by("period")
    )
    monthly_labels = [item["period"].strftime("%b %Y") for item in monthly_revenue_qs]
    monthly_data = [float(item["revenue"]) for item in monthly_revenue_qs]

    # 4. Most Popular Movies (based on confirmed bookings)
    popular_movies_qs = Movie.objects.annotate(
        booking_count=Count("shows__bookings", filter=Q(shows__bookings__status="confirmed")),
        revenue=Sum("shows__bookings__total_price", filter=Q(shows__bookings__status="confirmed"))
    ).order_by("-booking_count")[:5]

    popular_movies_list = [
        {
            "id": m.id,
            "title": m.title,
            "genre": m.get_genre_display(),
            "booking_count": m.booking_count,
            "revenue": float(m.revenue or 0),
        }
        for m in popular_movies_qs
    ]

    # 5. Busiest Theaters (Seat Occupancy Rate)
    # Total available capacity = sum(screen.total_rows * screen.seats_per_row) for each show
    # Booked seats = count of SeatBooking under confirmed bookings
    theaters = Theater.objects.prefetch_related("screens__shows").all()
    busiest_theaters = []
    for t in theaters:
        total_capacity = 0
        for screen in t.screens.all():
            show_count = screen.shows.count()
            total_capacity += (screen.total_rows * screen.seats_per_row) * show_count

        booked_seats_count = SeatBooking.objects.filter(
            booking__show__screen__theater=t,
            booking__status="confirmed"
        ).count()

        occupancy_rate = (
            round((booked_seats_count / total_capacity) * 100, 1)
            if total_capacity > 0
            else 0.0
        )

        busiest_theaters.append({
            "id": t.id,
            "name": t.name,
            "location": t.location,
            "booked_seats": booked_seats_count,
            "total_capacity": total_capacity,
            "occupancy_rate": occupancy_rate,
        })

    busiest_theaters.sort(key=lambda x: x["occupancy_rate"], reverse=True)

    # 6. Peak Booking Hours (0-23 Hour Distribution)
    peak_hours_qs = (
        confirmed_qs.annotate(hour=ExtractHour("booking_time"))
        .values("hour")
        .annotate(booking_count=Count("id"))
        .order_by("hour")
    )
    hour_map = {item["hour"]: item["booking_count"] for item in peak_hours_qs}
    peak_hours_labels = [f"{h:02d}:00" for h in range(24)]
    peak_hours_data = [hour_map.get(h, 0) for h in range(24)]

    # 7. User Spending Leaderboard (Fixes N+1 Query Problem via DB Annotation)
    user_stats = (
        User.objects.annotate(
            booking_count=Count("bookings", filter=Q(bookings__status="confirmed")),
            total_spent=Sum("bookings__total_price", filter=Q(bookings__status="confirmed"))
        )
        .filter(booking_count__gt=0)
        .order_by("-total_spent")[:10]
    )

    user_booking_stats = [
        {
            "username": u.username,
            "email": u.email,
            "booking_count": u.booking_count,
            "total_spent": float(u.total_spent or 0),
            "date_joined": u.date_joined.strftime("%b %d, %Y"),
        }
        for u in user_stats
    ]

    return {
        "total_users": total_users,
        "total_movies": total_movies,
        "total_bookings": total_confirmed_bookings,
        "total_all_bookings": all_bookings_count,
        "total_revenue": float(total_revenue),
        "today_revenue": float(today_revenue),
        "total_shows": total_shows,
        "total_theaters": total_theaters,
        "cancellation_rate": cancellation_rate,
        "cancelled_count": cancelled_count,
        "failed_count": failed_count,
        "pending_count": pending_count,
        "daily_labels": daily_labels,
        "daily_data": daily_data,
        "weekly_labels": weekly_labels,
        "weekly_data": weekly_data,
        "monthly_labels": monthly_labels,
        "monthly_data": monthly_data,
        "popular_movies_list": popular_movies_list,
        "busiest_theaters": busiest_theaters[:5],
        "peak_hours_labels": peak_hours_labels,
        "peak_hours_data": peak_hours_data,
        "user_booking_stats": user_booking_stats,
    }


@staff_member_required
def admin_dashboard(request):
    """
    Dashboard for staff/superusers with real-time analytics,
    optimized DB aggregations, and in-memory caching (5-min TTL).
    """
    CACHE_KEY = "admin_analytics_data_v2"
    data = cache.get(CACHE_KEY)
    if not data:
        data = _compute_admin_analytics()
        cache.set(CACHE_KEY, data, timeout=300)  # Cache for 5 minutes

    # Fetch recent 15 bookings dynamically (always real-time)
    recent_bookings = (
        Booking.objects.select_related(
            "user", "show__movie", "show__screen", "show__screen__theater"
        )
        .prefetch_related("seats")
        .order_by("-booking_time")[:15]
    )

    context = {
        "analytics": data,
        "recent_bookings": recent_bookings,
        "analytics_json": json.dumps(data),
    }
    return render(request, "users/admin_dashboard.html", context)


@staff_member_required
def admin_analytics_api(request):
    """
    JSON API endpoint for admin dashboard charts & real-time updates.
    """
    force_refresh = request.GET.get("refresh") == "1"
    CACHE_KEY = "admin_analytics_data_v2"

    if force_refresh:
        data = _compute_admin_analytics()
        cache.set(CACHE_KEY, data, timeout=300)
    else:
        data = cache.get(CACHE_KEY)
        if not data:
            data = _compute_admin_analytics()
            cache.set(CACHE_KEY, data, timeout=300)

    return JsonResponse(data)


from django.views.decorators.http import require_POST
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
import threading

@require_POST
def subscribe_newsletter(request):
    """
    API View to register a newsletter subscription.
    Sends a 'Thank you for subscribing' welcome email in a background thread.
    """
    email = request.POST.get("email", "").strip()
    if not email or "@" not in email:
        return JsonResponse({"success": False, "error": "Please provide a valid email address."}, status=400)

    # Email sending in a background thread to prevent blocking page response
    def send_welcome_email():
        try:
            subject = "Thank you for subscribing to our newsletter!"
            from_email = settings.DEFAULT_FROM_EMAIL
            
            context = {"email": email}
            html_content = render_to_string("emails/newsletter_welcome.html", context)
            text_content = "Thank you for subscribing to the BookMySeat newsletter."

            msg = EmailMultiAlternatives(subject, text_content, from_email, [email])
            msg.attach_alternative(html_content, "text/html")
            msg.send()
        except Exception as e:
            # Silently log/handle email dispatch errors so request doesn't crash
            import logging
            logging.getLogger(__name__).error(f"Newsletter subscription email failed for {email}: {e}")

    thread = threading.Thread(target=send_welcome_email)
    thread.daemon = True
    thread.start()

    return JsonResponse({"success": True, "message": "Thank you for subscribing!"})

