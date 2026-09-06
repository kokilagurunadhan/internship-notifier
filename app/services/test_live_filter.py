from app.services.internship_filter import is_internship


titles = [
    "Software Engineer Intern",
    "Software Engineering Intern",
    "Machine Learning Intern",
    "Embedded Intern",
    "QA Intern",
    "Backend Developer Intern",
    "Summer Internship",
    "Graduate Trainee",
    "Industrial Trainee",
    "Apprentice - Software Development",
    "Senior Software Engineer",
    "Backend Developer",
    "Software Engineer",
    "Engineering Manager",
]


print("=" * 70)
print("LIVE INTERNSHIP FILTER TEST")
print("=" * 70)

for title in titles:

    result = is_internship(title)

    print(
        f"{'✅' if result else '❌'} "
        f"{title}"
    )

print("=" * 70)