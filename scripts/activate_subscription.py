"""
scripts/activate_subscription.py

DEV-ONLY utility to manually activate a user's subscription for testing.
In production, this would be replaced by a payment gateway webhook
(e.g. Stripe) that flips subscription_active automatically on successful
payment -- not a manually-run script.

Usage (run from the project root, ilm-o-maarifat-api/):
    python -m scripts.activate_subscription user@example.com
    python -m scripts.activate_subscription user@example.com --days 30
"""

import sys
import argparse
from datetime import datetime, timedelta

sys.path.append(".")  # allow running from project root

from app.database import SessionLocal
from app import models


def activate_subscription(email: str, days: int = 30):
    db = SessionLocal()
    try:
        user = db.query(models.User).filter(models.User.email == email).first()
        if not user:
            print(f"No user found with email: {email}")
            return

        user.subscription_active = True
        user.subscription_expiry = datetime.utcnow() + timedelta(days=days)
        db.commit()

        print(f"Subscription activated for {email} until {user.subscription_expiry}")
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Manually activate a user's subscription (dev only).")
    parser.add_argument("email", help="Email of the user to activate")
    parser.add_argument("--days", type=int, default=30, help="Subscription validity in days (default: 30)")
    args = parser.parse_args()

    activate_subscription(args.email, args.days)
