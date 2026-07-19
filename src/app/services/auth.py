import asyncio
import secrets
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


class CurrentPasswordInvalidError(Exception):
    pass


class EmailAlreadyInUseError(Exception):
    pass


class EmailDeliveryUnavailableError(Exception):
    pass


class TwoFactorRequiredError(Exception):
    def __init__(self, login_token: str, debug_code: str | None, expires_in: int) -> None:
        self.login_token = login_token
        self.debug_code = debug_code
        self.expires_in = expires_in


class InvalidTwoFactorCodeError(Exception):
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

    async def register(self, email: str, password: str) -> tuple[UserRecord, str | None]:
        normalized_email = email.strip().lower()
        password_hash = await asyncio.to_thread(hash_password, password)
        try:
            user = await self.database.create_user(
                normalized_email,
                password_hash,
                is_admin=normalized_email in self.settings.admin_emails,
                email_verified=not self.settings.email_verification_required,
            )
        except sqlite3.IntegrityError as exc:
            raise EmailAlreadyRegisteredError(normalized_email) from exc
        if not self.settings.email_verification_required:
            return user, None
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
        if user.two_factor_enabled:
            login_token = create_opaque_token()
            debug_code = self._generate_2fa_code()
            await self.database.create_two_factor_challenge(
                user.id,
                "login",
                hash_token(debug_code),
                expires_at(minutes=self.settings.email_2fa_code_minutes),
                login_token_hash=hash_token(login_token),
            )
            raise TwoFactorRequiredError(
                login_token=login_token,
                debug_code=(
                    debug_code if self.settings.environment.lower() != "production" else None
                ),
                expires_in=self.settings.email_2fa_code_minutes * 60,
            )
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
        consumed = await self.database.consume_refresh_token(hash_token(refresh_token))
        if consumed is None:
            raise InvalidTokenError
        user, _ = consumed
        self._ensure_login_allowed(user)
        return await self.issue_tokens(user)

    async def logout(self, refresh_token: str | None) -> None:
        if refresh_token:
            await self.database.revoke_refresh_token(hash_token(refresh_token))

    async def verify_email(self, token: str) -> UserRecord:
        record = await self.database.consume_action_token("verify_email", hash_token(token))
        if record is None:
            raise InvalidTokenError
        user = record.user
        if record.payload.get("pending_email"):
            try:
                updated = await self.database.apply_pending_email(user.id)
            except sqlite3.IntegrityError as exc:
                raise EmailAlreadyInUseError from exc
            if updated is None:
                raise InvalidTokenError
            await self.database.create_notification(
                user.id,
                kind="security",
                key="email_changed",
                payload={"email": updated.email},
            )
            return updated
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
        record = await self.database.consume_action_token("password_reset", hash_token(token))
        if record is None:
            raise InvalidTokenError
        password_hash = await asyncio.to_thread(hash_password, new_password)
        await self.database.update_password(record.user.id, password_hash)

    async def change_password(
        self,
        user: UserRecord,
        current_password: str,
        new_password: str,
        current_refresh_token: str | None,
    ) -> None:
        if not await asyncio.to_thread(verify_password, user.password_hash, current_password):
            raise CurrentPasswordInvalidError
        password_hash = await asyncio.to_thread(hash_password, new_password)
        keep_hash = hash_token(current_refresh_token) if current_refresh_token else None
        await self.database.update_password(
            user.id,
            password_hash,
            keep_refresh_token_hash=keep_hash,
        )
        await self.database.create_notification(
            user.id,
            kind="security",
            key="password_changed",
            payload={},
        )

    async def request_email_change(self, user: UserRecord, email: str) -> str:
        normalized = email.strip().lower()
        existing = await self.database.get_user_by_email(normalized)
        if existing is not None and existing.id != user.id:
            raise EmailAlreadyInUseError
        updated = await self.database.update_profile(
            user.id,
            pending_email=normalized,
            set_pending_email=True,
        )
        if updated is None:
            raise InvalidTokenError
        token = create_opaque_token()
        await self.database.store_action_token(
            user.id,
            "verify_email",
            hash_token(token),
            expires_at(hours=self.settings.email_verification_hours),
            payload={"pending_email": normalized},
        )
        await self.database.create_notification(
            user.id,
            kind="security",
            key="email_change_requested",
            payload={"pending_email": normalized},
        )
        return token

    async def request_enable_email_2fa(self, user: UserRecord) -> str:
        if (
            self.settings.environment.lower() == "production"
            and not self.settings.email_provider_configured
        ):
            raise EmailDeliveryUnavailableError
        code = self._generate_2fa_code()
        await self.database.create_two_factor_challenge(
            user.id,
            "enable",
            hash_token(code),
            expires_at(minutes=self.settings.email_2fa_code_minutes),
        )
        return code

    async def confirm_enable_email_2fa(self, user: UserRecord, code: str) -> UserRecord:
        challenge = await self.database.consume_two_factor_challenge(
            "enable",
            hash_token(code),
        )
        if challenge is None or challenge.user_id != user.id:
            raise InvalidTwoFactorCodeError
        updated = await self.database.set_two_factor_enabled(user.id, True)
        assert updated is not None
        await self.database.create_notification(
            user.id,
            kind="security",
            key="two_factor_enabled",
            payload={},
        )
        return updated

    async def disable_email_2fa(self, user: UserRecord) -> UserRecord:
        updated = await self.database.set_two_factor_enabled(user.id, False)
        assert updated is not None
        await self.database.create_notification(
            user.id,
            kind="security",
            key="two_factor_disabled",
            payload={},
        )
        return updated

    async def verify_login_two_factor(self, login_token: str, code: str) -> IssuedTokens:
        challenge = await self.database.consume_two_factor_challenge(
            "login",
            hash_token(code),
            login_token_hash=hash_token(login_token),
        )
        if challenge is None:
            raise InvalidTwoFactorCodeError
        user = await self.database.get_user_by_id(challenge.user_id)
        if user is None:
            raise InvalidTwoFactorCodeError
        self._ensure_login_allowed(user)
        return await self.issue_tokens(user)

    @staticmethod
    def _generate_2fa_code() -> str:
        return f"{secrets.randbelow(1_000_000):06d}"

    def _ensure_login_allowed(self, user: UserRecord) -> None:
        if not user.is_active or user.deleted_at is not None:
            raise InactiveUserError
        if self.settings.email_verification_required and not user.email_verified:
            raise EmailNotVerifiedError
