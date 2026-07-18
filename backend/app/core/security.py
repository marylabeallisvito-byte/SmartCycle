"""
SmartCycle — Authentication & Security Utilities
JWT token creation/verification, password hashing.

Graceful degradation: uses python-jose + passlib when available,
otherwise falls back to pure stdlib (hmac + hashlib + base64).

Supported algorithms (stdlib): HS256, HS384, HS512.
"""

import base64
import hashlib
import hmac
import json
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from app.core.config import settings

# ═══════════════════════════════════════════════════════════════
# Password Hashing — stdlib fallback (SHA-256 with salt)
# ═══════════════════════════════════════════════════════════════

_PBKDF2_ITERATIONS = 100_000
_HASH_ALGORITHM = "sha256"


def _generate_salt(length: int = 16) -> bytes:
    """Generate a cryptographically random salt."""
    return os.urandom(length)


def hash_password(plain: str) -> str:
    """Hash a password using PBKDF2-SHA256 (stdlib).

    Format: pbkdf2:sha256:<iterations>$<salt_b64>$<hash_b64>
    """
    try:
        from passlib.context import CryptContext
        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        return pwd_context.hash(plain)
    except ImportError:
        pass

    salt = _generate_salt()
    dk = hashlib.pbkdf2_hmac(
        _HASH_ALGORITHM,
        plain.encode("utf-8"),
        salt,
        _PBKDF2_ITERATIONS,
    )
    salt_b64 = base64.b64encode(salt).decode("ascii")
    hash_b64 = base64.b64encode(dk).decode("ascii")
    return f"pbkdf2:{_HASH_ALGORITHM}:{_PBKDF2_ITERATIONS}${salt_b64}${hash_b64}"


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a password against its hash."""
    try:
        from passlib.context import CryptContext
        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        return pwd_context.verify(plain, hashed)
    except ImportError:
        pass

    # Parse pbkdf2 format
    try:
        prefix, rest = hashed.split("$", 1)
        algo_part, salt_b64, hash_b64 = rest.split("$", 2)
        _, alg, iterations_str = algo_part.split(":", 2)
        iterations = int(iterations_str)

        salt = base64.b64decode(salt_b64)
        expected_hash = base64.b64decode(hash_b64)

        dk = hashlib.pbkdf2_hmac(alg, plain.encode("utf-8"), salt, iterations)
        return hmac.compare_digest(dk, expected_hash)
    except (ValueError, IndexError):
        return False


# ═══════════════════════════════════════════════════════════════
# JWT — stdlib fallback (HS256/HS384/HS512)
# ═══════════════════════════════════════════════════════════════

def _b64url_encode(data: bytes) -> str:
    """Base64url-encode (no padding)."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(s: str) -> bytes:
    """Base64url-decode (adds padding if needed)."""
    rem = len(s) % 4
    if rem:
        s += "=" * (4 - rem)
    return base64.urlsafe_b64decode(s)


def _hmac_sign(data: bytes, secret: str, algorithm: str = "HS256") -> bytes:
    """Sign data with HMAC using the algorithm implied by the JWT alg."""
    alg_map = {
        "HS256": "sha256",
        "HS384": "sha384",
        "HS512": "sha512",
    }
    hash_name = alg_map.get(algorithm, "sha256")
    return hmac.new(
        secret.encode("utf-8"),
        data,
        hash_name,  # pass digest name as string (hmac.new calls hashlib.new internally)
    ).digest()


class _JWTError(Exception):
    """JWT decode/validation error."""
    pass


def create_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None,
    secret: Optional[str] = None,
    algorithm: Optional[str] = None,
) -> str:
    """Create a JWT access token.

    Uses python-jose when available, otherwise pure stdlib HMAC.
    """
    try:
        from jose import jwt as jose_jwt
        to_encode = data.copy()
        expire = datetime.now(timezone.utc) + (
            expires_delta or timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
        )
        to_encode.update({"exp": expire})
        return jose_jwt.encode(
            to_encode,
            secret or settings.JWT_SECRET,
            algorithm=algorithm or settings.JWT_ALGORITHM,
        )
    except ImportError:
        pass

    # ── stdlib JWT encoding ──
    _secret = secret or settings.JWT_SECRET
    _algo = algorithm or settings.JWT_ALGORITHM

    header = {"alg": _algo, "typ": "JWT"}
    payload = data.copy()

    # Add standard claims
    now = int(time.time())
    payload.setdefault("iat", now)
    expire_seconds = int(
        (expires_delta or timedelta(minutes=settings.JWT_EXPIRE_MINUTES)).total_seconds()
    )
    payload["exp"] = now + expire_seconds

    # Encode header + payload
    header_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_b64}.{payload_b64}"

    # Sign
    signature = _hmac_sign(signing_input.encode("utf-8"), _secret, _algo)
    signature_b64 = _b64url_encode(signature)

    return f"{signing_input}.{signature_b64}"


def decode_access_token(
    token: str,
    secret: Optional[str] = None,
    algorithm: Optional[str] = None,
) -> Optional[dict]:
    """Decode and validate a JWT access token. Returns None if invalid."""
    try:
        from jose import JWTError, jwt as jose_jwt
        try:
            return jose_jwt.decode(
                token,
                secret or settings.JWT_SECRET,
                algorithms=[algorithm or settings.JWT_ALGORITHM],
            )
        except JWTError:
            return None
    except ImportError:
        pass

    # ── stdlib JWT decoding ──
    _secret = secret or settings.JWT_SECRET
    _algo = algorithm or settings.JWT_ALGORITHM

    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None

        header_b64, payload_b64, signature_b64 = parts

        # Verify signature
        signing_input = f"{header_b64}.{payload_b64}"
        expected_sig = _hmac_sign(signing_input.encode("utf-8"), _secret, _algo)
        actual_sig = _b64url_decode(signature_b64)

        if not hmac.compare_digest(expected_sig, actual_sig):
            return None

        # Decode payload
        payload_bytes = _b64url_decode(payload_b64)
        payload: Dict[str, Any] = json.loads(payload_bytes)

        # Check expiration
        exp = payload.get("exp", 0)
        if exp and int(time.time()) > exp:
            return None  # expired

        return payload
    except Exception:
        return None
