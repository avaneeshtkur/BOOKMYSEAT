import datetime
import os
from django.core.management.base import BaseCommand
from movies.models import Movie, Theater, Screen, Show


class Command(BaseCommand):
    help = "Seed the database with sample movies, theaters, screens, and shows"

    def handle(self, *args, **options):
        self.stdout.write("Seeding database...")

        # ── Theaters & Screens ──────────────────────────────────────
        theaters_data = [
            {"name": "PVR Cinemas", "location": "Connaught Place, Delhi"},
            {"name": "INOX Multiplex", "location": "Phoenix Mall, Mumbai"},
            {"name": "Cinepolis", "location": "DLF Mall, Gurugram"},
        ]
        for td in theaters_data:
            theater, _ = Theater.objects.get_or_create(**td)
            for i in range(1, 4):
                Screen.objects.get_or_create(
                    theater=theater,
                    name=f"Screen {i}",
                    defaults={"total_rows": 8, "seats_per_row": 10},
                )
            self.stdout.write(f"  ✓ Theater: {theater.name}")

        # ── Poster filename mapping ─────────────────────────────────
        poster_map = {
            "The Dark Knight": "dark_knight.png",
            "Inception": "inception.png",
            "3 Idiots": "3 _idiots.png",
            "Interstellar": "interstellar.png",
            "Dangal": "dangal.png",
            "The Conjuring": "conjuring.png",
            "Titanic": "titanic.png",
            "Spider-Man: No Way Home": "spiderman.png",
            "Coco": "coco.png",
            "K.G.F: Chapter 2": "kgf2.png",
            "Sultan": "sultan.png",
        }

        # ── Trailer URL mapping ──────────────────────────────────────
        trailer_map = {
            "The Dark Knight": "https://www.youtube.com/watch?v=EXeTwQWrcwY",
            "Inception": "https://www.youtube.com/watch?v=YoHD9XEInc0",
            "3 Idiots": "https://www.youtube.com/watch?v=xvszmNXdM4w",
            "Interstellar": "https://www.youtube.com/watch?v=zSWdZVtXT7E",
            "Dangal": "https://www.youtube.com/watch?v=x_7YlGv9u1g",
            "The Conjuring": "https://www.youtube.com/watch?v=k10ETZ41q5o",
            "Titanic": "https://www.youtube.com/watch?v=kVrqfYjkTdQ",
            "Spider-Man: No Way Home": "https://www.youtube.com/watch?v=JfVOs4VSpmA",
            "Coco": "https://www.youtube.com/watch?v=Rvr68u6k5sI",
            "K.G.F: Chapter 2": "https://www.youtube.com/watch?v=JKa05nyUmuQ",
            "Sultan": "https://www.youtube.com/watch?v=ude2-o23WkA",
        }

        # ── Movies ──────────────────────────────────────────────────
        movies_data = [
            {
                "title": "The Dark Knight",
                "description": "When the menace known as the Joker wreaks havoc on Gotham, Batman must accept one of the greatest psychological tests of his ability to fight injustice.",
                "genre": "action",
                "language": "english",
                "duration_minutes": 152,
                "rating": 9.0,
                "release_date": datetime.date(2024, 7, 18),
            },
            {
                "title": "Inception",
                "description": "A thief who steals corporate secrets through dream-sharing technology is given the inverse task of planting an idea into the mind of a C.E.O.",
                "genre": "scifi",
                "language": "english",
                "duration_minutes": 148,
                "rating": 8.8,
                "release_date": datetime.date(2024, 7, 16),
            },
            {
                "title": "3 Idiots",
                "description": "Two friends are searching for their long lost companion. They revisit their college days and recall the memories of their friend who inspired them.",
                "genre": "comedy",
                "language": "hindi",
                "duration_minutes": 170,
                "rating": 8.4,
                "release_date": datetime.date(2024, 12, 25),
            },
            {
                "title": "Interstellar",
                "description": "A team of explorers travel through a wormhole in space in an attempt to ensure humanity's survival.",
                "genre": "scifi",
                "language": "english",
                "duration_minutes": 169,
                "rating": 8.7,
                "release_date": datetime.date(2024, 11, 7),
            },
            {
                "title": "Dangal",
                "description": "Former wrestler Mahavir Singh Phogat trains his daughters to become world-class wrestlers.",
                "genre": "drama",
                "language": "hindi",
                "duration_minutes": 161,
                "rating": 8.3,
                "release_date": datetime.date(2024, 12, 23),
            },
            {
                "title": "The Conjuring",
                "description": "Paranormal investigators Ed and Lorraine Warren work to help a family terrorized by a dark presence in their farmhouse.",
                "genre": "horror",
                "language": "english",
                "duration_minutes": 112,
                "rating": 7.5,
                "release_date": datetime.date(2025, 7, 19),
            },
            {
                "title": "Titanic",
                "description": "A seventeen-year-old aristocrat falls in love with a kind but poor artist aboard the luxurious, ill-fated R.M.S. Titanic.",
                "genre": "romance",
                "language": "english",
                "duration_minutes": 195,
                "rating": 7.9,
                "release_date": datetime.date(2025, 1, 1),
            },
            {
                "title": "Spider-Man: No Way Home",
                "description": "With Spider-Man's identity now revealed, Peter asks Doctor Strange for help. When a spell goes wrong, dangerous foes from other worlds appear.",
                "genre": "action",
                "language": "english",
                "duration_minutes": 148,
                "rating": 8.2,
                "release_date": datetime.date(2025, 12, 17),
            },
            {
                "title": "Coco",
                "description": "Aspiring musician Miguel, confronted with his family's ancestral ban on music, enters the Land of the Dead to find his great-great-grandfather.",
                "genre": "animation",
                "language": "english",
                "duration_minutes": 105,
                "rating": 8.4,
                "release_date": datetime.date(2025, 11, 22),
            },
            {
                "title": "K.G.F: Chapter 2",
                "description": "In the blood-soaked Kolar Gold Fields, Rocky's rising power makes the government tremble, and his enemies conspire to destroy him.",
                "genre": "action",
                "language": "others",
                "duration_minutes": 168,
                "rating": 7.8,
                "release_date": datetime.date(2025, 4, 14),
            },
            {
                "title": "Sultan",
                "description": "Sultan is a classic underdog story about a local wrestling champion who falls in love and must rediscover his fighting spirit to regain his lost glory.",
                "genre": "action",
                "language": "hindi",
                "duration_minutes": 170,
                "rating": 8.0,
                "release_date": datetime.date(2025, 7, 6),
            },
        ]

        for md in movies_data:
            movie, created = Movie.objects.get_or_create(
                title=md["title"], defaults=md
            )
            # Assign poster and trailer if available (always update, even for existing movies)
            updated_fields = []
            poster_file = poster_map.get(md["title"])
            if poster_file:
                movie.poster = f"posters/{poster_file}"
                updated_fields.append("poster")
            trailer_url = trailer_map.get(md["title"])
            if trailer_url:
                movie.trailer_url = trailer_url
                updated_fields.append("trailer_url")
            if updated_fields:
                movie.save(update_fields=updated_fields)

            if created:
                self.stdout.write(f"  ✓ Movie: {movie.title} (poster: {poster_file or 'none'}, trailer: {'yes' if trailer_url else 'no'})")
            else:
                self.stdout.write(f"  → Movie already exists: {movie.title} (updated: poster={poster_file or 'none'}, trailer={'yes' if trailer_url else 'no'})")

        # ── Shows ───────────────────────────────────────────────────
        screens = list(Screen.objects.all())
        movies = list(Movie.objects.all())
        times = [
            datetime.time(10, 0),
            datetime.time(13, 30),
            datetime.time(17, 0),
            datetime.time(21, 0),
        ]
        today = datetime.date.today()
        dates = [today + datetime.timedelta(days=d) for d in range(7)]

        show_count = 0
        for movie in movies:
            for i, screen in enumerate(screens[:3]):
                show_date = dates[i % len(dates)]
                for t in times[:2]:  # 2 shows per screen per movie
                    _, created = Show.objects.get_or_create(
                        movie=movie,
                        screen=screen,
                        show_date=show_date,
                        show_time=t,
                        defaults={"price": 250.00},
                    )
        # ── Admin User ──────────────────────────────────────────────
        from django.contrib.auth.models import User
        admin_user, admin_created = User.objects.get_or_create(
            username="admin",
            defaults={
                "email": "thakuravaneesh58@gmail.com",
                "is_staff": True,
                "is_superuser": True,
            }
        )
        admin_user.set_password("admin123")
        admin_user.is_staff = True
        admin_user.is_superuser = True
        admin_user.save()
        self.stdout.write("  ✓ Admin User: admin (password: admin123)")

        self.stdout.write(f"  ✓ Created {show_count} new shows")
        self.stdout.write(self.style.SUCCESS("Database seeded successfully!"))
