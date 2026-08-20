"""Create all database tables. Run with: python -m database.init_db"""

from __future__ import annotations

from database.base import create_all, get_engine


def main() -> None:
    create_all()
    print(f"Tables created on {get_engine().url}")


if __name__ == "__main__":
    main()
