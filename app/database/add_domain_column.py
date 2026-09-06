import sqlite3


DATABASE = "internship.db"


connection = sqlite3.connect(DATABASE)

cursor = connection.cursor()

try:

    cursor.execute(
        """
        ALTER TABLE subscriptions
        ADD COLUMN domain TEXT
        """
    )

    connection.commit()

    print("✅ Added domain column")

except sqlite3.OperationalError as error:

    if "duplicate column name" in str(error).lower():

        print("ℹ️ Domain column already exists")

    else:

        raise

finally:

    connection.close()

print("🎯 Subscription migration completed!")