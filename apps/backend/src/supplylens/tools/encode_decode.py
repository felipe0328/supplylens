import jwt

from supplylens.config import get_jwt_settings

ALGORITHM = "HS256"


def encode_jwt(payload: dict) -> str:
    settings = get_jwt_settings()
    return jwt.encode(payload, settings.secret, algorithm=ALGORITHM)


def decode_jwt(token: str) -> dict:
    settings = get_jwt_settings()
    return jwt.decode(
        token,
        settings.secret,
        algorithms=[ALGORITHM],
        options={"require": ["exp", "sub", "role"]},
    )
