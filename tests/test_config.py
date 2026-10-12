from app.core.config import Settings


def test_render_database_url_is_normalized_for_asyncpg():
    settings = Settings(
        DATABASE_URL="postgresql://user:password@db.internal:5432/ackvia"
    )

    assert settings.DATABASE_URL == (
        "postgresql+asyncpg://user:password@db.internal:5432/ackvia"
    )


def test_asyncpg_database_url_is_unchanged():
    database_url = "postgresql+asyncpg://user:password@db:5432/ackvia"

    settings = Settings(DATABASE_URL=database_url)

    assert settings.DATABASE_URL == database_url
