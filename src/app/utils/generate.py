import random
import string

async def generate_code(start: int, end: int) -> str:
    length = random.randint(start, end)
    characters = string.ascii_letters + string.digits
    shortcode = ''.join(random.choice(characters) for i in range(length))

    return shortcode