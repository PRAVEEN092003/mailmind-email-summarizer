"""FastAPI dependency providers for authentication and database sessions."""

from typing import Optional
from fastapi import Depends, Header, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.core.errors import AuthenticationError
from app.core.security import decode_access_token
from app.models.database import get_db, User

security_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
    db: Session = Depends(get_db),
) -> User:
    """Dependency verifying JWT token and returning authenticated User."""
    if not credentials or not credentials.credentials:
        raise AuthenticationError("Authentication required. Please log in to continue.")

    token = credentials.credentials
    payload = decode_access_token(token)
    user_id = payload.get("sub")
    if not user_id:
        raise AuthenticationError("Invalid token payload: missing user identity.")

    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user:
        raise AuthenticationError("User account associated with this token no longer exists.")

    return user


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """Dependency returning authenticated User if valid token is provided, or None."""
    if not credentials or not credentials.credentials:
        return None

    try:
        token = credentials.credentials
        payload = decode_access_token(token)
        user_id = payload.get("sub")
        if not user_id:
            return None
        return db.query(User).filter(User.id == int(user_id)).first()
    except Exception:
        return None
