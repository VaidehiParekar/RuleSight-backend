"""Set the sign-in password of the demo accounts from DEMO_USER_PASSWORD.

The password is read through Settings (environment or .env) and stored as a bcrypt hash. It is
never printed. Run from the backend folder:

    uv run python scripts/set_user_passwords.py                      # every user
    uv run python scripts/set_user_passwords.py --email priya@rulesight.bank
"""

import argparse
import sys
from pathlib import Path

from sqlalchemy import create_engine, text

# Allow `python scripts/set_user_passwords.py` from the backend folder (app is not installed).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.auth import hash_password  # noqa: E402
from app.core.config import get_settings  # noqa: E402

MIN_PASSWORD_LENGTH = 12


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--email", help="Only set the password for this user (case-insensitive).")
    args = parser.parse_args()

    settings = get_settings()
    if settings.demo_user_password is None:
        print("DEMO_USER_PASSWORD is not set (environment or .env).", file=sys.stderr)
        return 1
    password = settings.demo_user_password.get_secret_value()
    if len(password) < MIN_PASSWORD_LENGTH:
        print(
            f"DEMO_USER_PASSWORD must be at least {MIN_PASSWORD_LENGTH} characters.",
            file=sys.stderr,
        )
        return 1

    hashed = hash_password(password)
    engine = create_engine(settings.database_url.get_secret_value())
    try:
        with engine.begin() as conn:
            if args.email:
                result = conn.execute(
                    text("""
                        UPDATE users SET hashed_password = :hashed
                        WHERE LOWER(email) = LOWER(:email)
                        RETURNING email
                    """),
                    {"hashed": hashed, "email": args.email.strip()},
                )
            else:
                result = conn.execute(
                    text("UPDATE users SET hashed_password = :hashed RETURNING email"),
                    {"hashed": hashed},
                )
            emails = sorted(row[0] for row in result)
    finally:
        engine.dispose()

    if not emails:
        print("No matching user was found; nothing changed.", file=sys.stderr)
        return 1
    print(f"Password set for {len(emails)} user(s): {', '.join(emails)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
