from sqlalchemy import text

from app.database.database import engine


with engine.connect() as connection:

    # ============================================================
    # ADD via COLUMN
    # ============================================================

    try:
        connection.execute(
            text(
                "ALTER TABLE internships "
                "ADD COLUMN via VARCHAR"
            )
        )
        print("✅ Added via column")

    except Exception:
        print("ℹ️ via column already exists")


    # ============================================================
    # ADD relevance_score COLUMN
    # ============================================================

    try:
        connection.execute(
            text(
                "ALTER TABLE internships "
                "ADD COLUMN relevance_score INTEGER"
            )
        )
        print("✅ Added relevance_score column")

    except Exception:
        print("ℹ️ relevance_score column already exists")


    # ============================================================
    # ADD email_sent COLUMN
    # ============================================================

    try:
        connection.execute(
            text(
                "ALTER TABLE internships "
                "ADD COLUMN email_sent BOOLEAN DEFAULT 0 NOT NULL"
            )
        )
        print("✅ Added email_sent column")

    except Exception:
        print("ℹ️ email_sent column already exists")


    # ============================================================
    # ADD passed_filter COLUMN
    # ============================================================

    try:
        connection.execute(
            text(
                "ALTER TABLE internships "
                "ADD COLUMN passed_filter BOOLEAN DEFAULT 0 NOT NULL"
            )
        )
        print("✅ Added passed_filter column")

    except Exception:
        print("ℹ️ passed_filter column already exists")


    # ============================================================
    # ADD status COLUMN
    # ============================================================

    try:
        connection.execute(
            text(
                "ALTER TABLE internships "
                "ADD COLUMN status VARCHAR DEFAULT 'NEW' NOT NULL"
            )
        )
        print("✅ Added status column")

    except Exception:
        print("ℹ️ status column already exists")


    # ============================================================
    # COMMIT
    # ============================================================

    connection.commit()


print()
print("🎯 Database migration completed!")