import random
import string

async def generate_code() -> str:
    length = random.randint(4, 8)
    characters = string.ascii_letters + string.digits
    shortcode = ''.join(random.choice(characters) for i in range(length))

    return shortcode