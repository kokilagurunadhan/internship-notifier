from app.services.email_service import send_internship_email


send_internship_email(
    recipient_email="kokilasudha9363@gmail.com",
    company="Test Company",
    title="Python Developer Intern",
    location="Salem, India",
    url="https://example.com"
)