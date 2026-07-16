import asyncio
import sqlite3
from dataclasses import dataclass

from app.core.config import Settings
from app.core.security import (
    create_access_token,
    create_opaque_token,
    expires_at,
    hash_password,
    hash_token,
    verify_password,
)
from app.db.sql.crud import SQLClient, UserRecord


class EmailAlreadyRegisteredError(Exception):
    pass


class InvalidCredentialsError(Exception):
    pass


class EmailNotVerifiedError(Exception):
    pass


class InactiveUserError(Exception):
    pass


class InvalidTokenError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class IssuedTokens:
    access_token: str
    refresh_token: str
    expires_in: int
    user: UserRecord


class AuthService:
    def __init__(self, database: SQLClient, settings: Settings) -> None:
        self.database = database
        self.settings = settings

    async def register(self, email: str, password: str) -> tuple[UserRecord, str]:
        normalized_email = email.strip().lower()
        password_hash = await asyncio.to_thread(hash_password, password)
        try:
            user = await self.database.create_user(
                normalized_email,
                password_hash,
                is_admin=normalized_email in self.settings.admin_emails,
            )
        except sqlite3.IntegrityError as exc:
            raise EmailAlreadyRegisteredError(normalized_email) from exc
        token = create_opaque_token()
        await self.database.store_action_token(
            user.id,
            "verify_email",
            hash_token(token),
            expires_at(hours=self.settings.email_verification_hours),
        )
        return user, token

    async def authenticate(self, email: str, password: str) -> IssuedTokens:
        user = await self.database.get_user_by_email(email.strip().lower())
        if user is None or not await asyncio.to_thread(
            verify_password,
            user.password_hash,
            password,
        ):
            raise InvalidCredentialsError
        self._ensure_login_allowed(user)
        return await self.issue_tokens(user)

    async def issue_tokens(self, user: UserRecord) -> IssuedTokens:
        access_token, expires_in = create_access_token(user.id, self.settings)
        refresh_token = create_opaque_token()
        await self.database.store_refresh_token(
            user.id,
            hash_token(refresh_token),
            expires_at(days=self.settings.refresh_token_days),
        )
        return IssuedTokens(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=expires_in,
            user=user,
        )

    async def rotate_refresh_token(self, refresh_token: str) -> IssuedTokens:
        user = await self.database.consume_refresh_token(hash_token(refresh_token))
        if user is None:
            raise InvalidTokenError
        self._ensure_login_allowed(user)
        return await self.issue_tokens(user)

    async def logout(self, refresh_token: str) -> None:
        await self.database.revoke_refresh_token(hash_token(refresh_token))

    async def verify_email(self, token: str) -> UserRecord:
        user = await self.database.consume_action_token("verify_email", hash_token(token))
        if user is None:
            raise InvalidTokenError
        verified = await self.database.mark_email_verified(user.id)
        if verified is None:
            raise InvalidTokenError
        return verified

    async def request_password_reset(self, email: str) -> str | None:
        user = await self.database.get_user_by_email(email.strip().lower())
        if user is None or not user.is_active:
            return None
        token = create_opaque_token()
        await self.database.store_action_token(
            user.id,
            "password_reset",
            hash_token(token),
            expires_at(minutes=self.settings.password_reset_minutes),
        )
        return token

    async def reset_password(self, token: str, new_password: str) -> None:
        user = await self.database.consume_action_token("password_reset", hash_token(token))
        if user is None:
            raise InvalidTokenError
        password_hash = await asyncio.to_thread(hash_password, new_password)
        await self.database.update_password(user.id, password_hash)

    @staticmethod
    def _ensure_login_allowed(user: UserRecord) -> None:
        if not user.is_active:
            raise InactiveUserError
        if not user.email_verified:
            raise EmailNotVerifiedError
