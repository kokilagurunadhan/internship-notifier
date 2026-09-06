import asyncio

from app.services.notification_grouper import (
    get_pending_internships_grouped_by_user
)


async def main():

    print()
    print("=" * 70)
    print("PENDING INTERNSHIP GROUPING TEST")
    print("=" * 70)

    grouped = await get_pending_internships_grouped_by_user()

    print(
        f"👥 Users with pending internships: "
        f"{len(grouped)}"
    )

    for email, internships in grouped.items():

        print()
        print("-" * 70)

        print(f"📧 User: {email}")
        print(
            f"📦 Pending internships: "
            f"{len(internships)}"
        )

        for internship in internships:

            print(
                f"   • {internship.company} | "
                f"{internship.title} | "
                f"email_sent={internship.email_sent}"
            )

    print()
    print("=" * 70)
    print("✅ GROUPING TEST COMPLETED")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())