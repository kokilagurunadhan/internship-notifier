from sqlalchemy import text

from app.database.database import engine


print("=" * 60)
print("NOTIFICATION TABLE MIGRATION")
print("=" * 60)


with engine.connect() as connection:

    # ========================================================
    # CHECK WHETHER TABLE EXISTS
    # ========================================================

    result = connection.execute(
        text(
            """
            SELECT name
            FROM sqlite_master
            WHERE type='table'
            AND name='notifications'
            """
        )
    )

    table_exists = result.fetchone()


    # ========================================================
    # CREATE TABLE IF IT DOES NOT EXIST
    # ========================================================

    if not table_exists:

        connection.execute(
            text(
                """
                CREATE TABLE notifications (

                    id INTEGER PRIMARY KEY,

                    subscription_id INTEGER,

                    user_email VARCHAR NOT NULL,

                    job_id INTEGER NOT NULL,

                    status VARCHAR NOT NULL
                        DEFAULT 'PENDING',

                    relevance_score FLOAT,

                    created_at DATETIME,

                    sent_at DATETIME,

                    retry_count INTEGER
                        DEFAULT 0,

                    error_message VARCHAR,

                    FOREIGN KEY(subscription_id)
                        REFERENCES subscriptions(id),

                    FOREIGN KEY(job_id)
                        REFERENCES internships(id)
                )
                """
            )
        )

        connection.commit()

        print(
            "✅ notifications table created successfully!"
        )


    # ========================================================
    # TABLE ALREADY EXISTS
    # ========================================================

    else:

        print(
            "⚠️ notifications table already exists."
        )


        # ----------------------------------------------------
        # CHECK WHETHER subscription_id EXISTS
        # ----------------------------------------------------

        columns = connection.execute(
            text(
                """
                PRAGMA table_info(notifications)
                """
            )
        ).fetchall()


        column_names = [
            column[1]
            for column in columns
        ]


        # ----------------------------------------------------
        # ADD subscription_id
        # ----------------------------------------------------

        if "subscription_id" not in column_names:

            connection.execute(
                text(
                    """
                    ALTER TABLE notifications
                    ADD COLUMN subscription_id INTEGER
                    """
                )
            )

            connection.commit()

            print(
                "✅ Added subscription_id column."
            )

        else:

            print(
                "✅ subscription_id column already exists."
            )


print("=" * 60)
print("✅ MIGRATION COMPLETED")
print("=" * 60)