import random

# All available verification templates
ALL_VERIFICATION_TEMPLATES = [
    "verify.html",
    "verify_v2.html",
    "verify_v3.html",
    "verify_v4.html",
    "verify_v5.html",
    "verify_v6.html",
    "verify_v7.html",
    "verify_v8.html",
    "verify_v9.html",
    "verify_v10.html",
    "verify_v11.html",
    "verify_v12.html",
]

def get_random_verification_template() -> str:
    """
    Randomly select one of the available verification templates.
    """
    return random.choice(ALL_VERIFICATION_TEMPLATES)
