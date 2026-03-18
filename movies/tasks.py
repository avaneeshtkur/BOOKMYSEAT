import logging
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from .models import Booking

logger = logging.getLogger(__name__)

# Try to load Celery. If the user runs the server outside the virtual environment,
# we fallback to a dummy implementation so the server doesn't crash.
try:
    from celery import shared_task
    HAS_CELERY = True
except ImportError:
    HAS_CELERY = False

def _process_booking_email(booking_id, retries=None):
    """Core logic extracted so it can be run by Celery or synchronously as fallback"""
    try:
        booking = Booking.objects.select_related('user', 'show__movie', 'show__screen__theater').get(id=booking_id)
        
        # Get related seat objects
        seats = [f"{seat_booking.row_letter}{seat_booking.seat_number}" for seat_booking in booking.seats.all()]
        seats_str = ", ".join(seats)

        # Build context
        context = {
            'user_name': booking.user.get_full_name() or booking.user.username,
            'movie_name': booking.show.movie.title,
            'theater': booking.show.screen.theater.name,
            'show_time': f"{booking.show.show_date} at {booking.show.show_time.strftime('%I:%M %p')}",
            'seats': seats_str,
            'booking_id': str(booking.id),
            'payment_id': f"TXN-{booking.id}-BMS",
            'total_price': str(booking.total_price),
        }

        subject = f"Booking Confirmed: {booking.show.movie.title}"
        from_email = settings.DEFAULT_FROM_EMAIL
        to_email = booking.user.email

        if not to_email:
            logger.warning(f"Booking {booking_id} has a user with no email address.")
            return

        # Render HTML template
        html_content = render_to_string('emails/booking_confirmation.html', context)
        
        # Fallback text content
        text_content = (
            f"Your booking for {context['movie_name']} is confirmed.\n"
            f"Theater: {context['theater']}\n"
            f"Time: {context['show_time']}\n"
            f"Seats: {context['seats']}\n"
            f"Booking ID: {context['booking_id']}\n"
        )

        msg = EmailMultiAlternatives(subject, text_content, from_email, [to_email])
        msg.attach_alternative(html_content, "text/html")
        msg.send()

        logger.info(f"Booking confirmation email successfully sent to {to_email} for booking {booking_id}")
        return f"Email sent for booking {booking_id}"
        
    except Booking.DoesNotExist:
        logger.error(f"Failed to send email: Booking {booking_id} does not exist.")
    except Exception as e:
        logger.error(f"Failed to send email for booking {booking_id}. Error: {str(e)}")
        raise e

if HAS_CELERY:
    @shared_task(bind=True, max_retries=3, default_retry_delay=5)
    def send_booking_confirmation_email(self, booking_id):
        """Celery background task"""
        try:
            return _process_booking_email(booking_id, retries=self.request.retries)
        except Exception as e:
            logger.error(f"Retrying email for booking {booking_id}... ({self.request.retries}/3)")
            raise self.retry(exc=e)
else:
    # Dummy implementation that behaves like a celery task (has a .delay() method)
    # but executes synchronously.
    def send_booking_confirmation_email(booking_id):
        return _process_booking_email(booking_id)
    
    send_booking_confirmation_email.delay = lambda booking_id: _process_booking_email(booking_id)
