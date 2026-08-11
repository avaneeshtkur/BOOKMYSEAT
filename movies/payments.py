"""
payments.py — Razorpay Client & Security Utilities (Phase 4 & 5)

Responsibilities:
  - Create Razorpay orders (server-side only, key_secret never touches frontend)
  - Verify HMAC SHA256 payment signatures (prevents fraud)
  - Verify webhook signatures (prevents spoofed webhook calls)
"""
import hmac
import hashlib
import logging
import razorpay
from django.conf import settings

logger = logging.getLogger(__name__)


def get_razorpay_client():
    """Returns an authenticated Razorpay client instance."""
    return razorpay.Client(
        auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
    )


def create_razorpay_order(amount_inr: float, receipt: str, notes: dict = None) -> dict:
    """
    Phase 4: Create a Razorpay payment order on the server side.
    
    Args:
        amount_inr: Amount in Indian Rupees (e.g., 400.00)
        receipt:    Unique booking receipt identifier (e.g., "booking_42")
        notes:      Optional dict of metadata to attach to the order
    
    Returns:
        Razorpay order dict with 'id', 'amount', 'currency', etc.
    
    Raises:
        Exception: If Razorpay API call fails
    """
    client = get_razorpay_client()
    amount_paise = int(amount_inr * 100)  # Razorpay uses paise

    order_data = {
        "amount": amount_paise,
        "currency": "INR",
        "receipt": receipt,
        "payment_capture": 1,  # Auto-capture on payment success
        "notes": notes or {},
    }

    try:
        order = client.order.create(data=order_data)
        logger.info(f"[Payment] Razorpay order created: {order['id']} for ₹{amount_inr}")
        return order
    except Exception as e:
        logger.error(f"[Payment] Failed to create Razorpay order: {e}")
        raise


def verify_razorpay_signature(order_id: str, payment_id: str, signature: str) -> bool:
    """
    Phase 5 (CRITICAL): Verify the HMAC SHA256 signature from Razorpay.
    
    Razorpay signs payments using:
        HMAC_SHA256(order_id + "|" + payment_id, key_secret)
    
    This is the ONLY way to confirm a payment is genuine.
    NEVER trust frontend payment success without this verification.
    
    Returns:
        True if signature is valid, False otherwise
    """
    key_secret = settings.RAZORPAY_KEY_SECRET.encode("utf-8")
    msg = f"{order_id}|{payment_id}".encode("utf-8")

    expected = hmac.new(key_secret, msg, hashlib.sha256).hexdigest()
    is_valid = hmac.compare_digest(expected, signature)

    if is_valid:
        logger.info(f"[Payment] Signature verified ✓ for order: {order_id}")
    else:
        logger.warning(f"[Payment] INVALID signature for order: {order_id} — possible fraud attempt!")

    return is_valid


def verify_webhook_signature(payload_body: bytes, signature: str) -> bool:
    """
    Phase 6: Verify Razorpay webhook requests.
    
    Razorpay sends an 'X-Razorpay-Signature' header with each webhook.
    We verify it using the webhook secret to ensure the request is genuine.
    
    Args:
        payload_body: Raw request body bytes
        signature:    Value from 'X-Razorpay-Signature' header
    
    Returns:
        True if webhook is authentic
    """
    webhook_secret = settings.RAZORPAY_WEBHOOK_SECRET.encode("utf-8")
    expected = hmac.new(webhook_secret, payload_body, hashlib.sha256).hexdigest()
    is_valid = hmac.compare_digest(expected, signature)

    if not is_valid:
        logger.warning("[Webhook] Invalid webhook signature — ignoring request.")

    return is_valid
