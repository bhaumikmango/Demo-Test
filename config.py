import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY')
    if os.environ.get('FLASK_ENV') == 'production' and SECRET_KEY is None:
        raise ValueError("SECRET_KEY is not set in production environment variables!")
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

    HIGH_SCHOOL_SUBJECTS = [
        "Physics", "Chemistry", "Biology", "Mathematics", "Computer Science",
        "English Literature", "History", "Geography", "Economics", "Political Science",
        "Psychology", "Sociology", "Art", "Music", "Physical Education", "Other"
    ]
    
    RESPONSE_TONES = ["Professional", "Funny", "Excited", "Casual", "Witty", "Sarcastic", "Masculine", "Feminine", "Bold", "Dramatic", "Grumpy", "Secretive"]