from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from .forms import UserRegisterForm, UserUpdateForm
from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.models import User
from django.db.models import Sum, Count
from movies.models import Movie, Booking, Show, Theater, SeatBooking


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


@staff_member_required
def admin_dashboard(request):
    """Dashboard for superusers to view all platform data."""
    total_users = User.objects.count()
    total_movies = Movie.objects.count()
    total_bookings = Booking.objects.filter(status="confirmed").count()
    total_revenue = Booking.objects.filter(status="confirmed").aggregate(
        total=Sum("total_price")
    )["total"] or 0
    total_shows = Show.objects.count()
    total_theaters = Theater.objects.count()

    recent_bookings = (
        Booking.objects.select_related(
            "user", "show__movie", "show__screen", "show__screen__theater"
        )
        .prefetch_related("seats")
        .order_by("-booking_time")[:20]
    )

    all_users = User.objects.all().order_by("-date_joined")
    user_booking_stats = []
    for u in all_users:
        user_bookings = Booking.objects.filter(user=u, status="confirmed")
        user_revenue = user_bookings.aggregate(total=Sum("total_price"))["total"] or 0
        user_booking_stats.append({
            "user": u,
            "booking_count": user_bookings.count(),
            "total_spent": user_revenue,
        })

    all_movies_data = Movie.objects.annotate(
        booking_count=Count("shows__bookings", distinct=True)
    ).order_by("-booking_count")

    context = {
        "total_users": total_users,
        "total_movies": total_movies,
        "total_bookings": total_bookings,
        "total_revenue": total_revenue,
        "total_shows": total_shows,
        "total_theaters": total_theaters,
        "recent_bookings": recent_bookings,
        "user_booking_stats": user_booking_stats,
        "all_movies_data": all_movies_data,
    }
    return render(request, "users/admin_dashboard.html", context)
