"""Authentication routes: register, login, refresh token, user info"""

import logging
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, status, Depends, Request
from sqlalchemy.orm import Session
from email_validator import validate_email, EmailNotValidError

from .database import (
    get_db,
    create_user,
    get_user_by_email,
    get_user_by_id,
    update_failed_login_attempts,
)
from .auth import (
    hash_password,
    verify_password,
    create_tokens,
    decode_token,
    create_access_token,
    ACCESS_TOKEN_EXPIRE_HOURS,
)
from .schemas import (
    UserRegister,
    UserLogin,
    TokenResponse,
    UserResponse,
    TokenRefresh,
)
from .dependencies import get_current_user, limiter

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])

# Account lockout settings
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 15


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def register(
    user_data: UserRegister,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Register a new user account.

    Rate limited to 10 requests per minute per IP address.
    """
    try:
        # Validate email format (do not check deliverability so test/example emails work)
        validate_email(user_data.email, check_deliverability=False)
    except EmailNotValidError as e:
        logger.warning(f"Invalid email format: {user_data.email}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid email format: {str(e)}"
        )

    # Check if email already exists
    existing_user = get_user_by_email(db, user_data.email)
    if existing_user:
        logger.warning(f"Registration attempt with existing email: {user_data.email}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered"
        )

    # Validate password strength (at least 8 chars, mix of upper/lower/numbers)
    password = user_data.password
    if len(password) < 8:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Password must be at least 8 characters"
        )

    if not any(c.isupper() for c in password):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Password must contain at least one uppercase letter"
        )

    if not any(c.islower() for c in password):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Password must contain at least one lowercase letter"
        )

    if not any(c.isdigit() for c in password):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Password must contain at least one number"
        )

    # Hash password and create user
    password_hash = hash_password(password)
    user = create_user(db, user_data.email, user_data.username, password_hash)

    logger.info(f"New user registered: {user.email}")
    return user


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
async def login(
    credentials: UserLogin,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Authenticate user and return access and refresh tokens.

    Rate limited to 10 requests per minute per IP address.
    Account locks after 5 failed attempts for 15 minutes.
    """
    # Get user by email
    user = get_user_by_email(db, credentials.email)

    if not user:
        logger.warning(f"Login attempt for non-existent user: {credentials.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    if not user.is_active:
        logger.warning(f"Login attempt for inactive user: {credentials.email}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive"
        )

    # Check if account is locked
    if user.locked_until and datetime.utcnow() < user.locked_until:
        remaining_minutes = (user.locked_until - datetime.utcnow()).total_seconds() / 60
        logger.warning(f"Login attempt for locked account: {credentials.email}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Account locked. Try again in {int(remaining_minutes)} minutes"
        )

    # Verify password
    if not verify_password(credentials.password, user.password_hash):
        # Increment failed attempts
        update_failed_login_attempts(db, user.id, increment=True)

        # Check if we should lock the account
        user = get_user_by_id(db, user.id)
        if user.failed_login_attempts >= MAX_LOGIN_ATTEMPTS:
            user.locked_until = datetime.utcnow() + timedelta(minutes=LOCKOUT_DURATION_MINUTES)
            db.commit()
            logger.warning(f"Account locked after {MAX_LOGIN_ATTEMPTS} failed attempts: {credentials.email}")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Account locked after {MAX_LOGIN_ATTEMPTS} failed login attempts. Try again in {LOCKOUT_DURATION_MINUTES} minutes"
            )

        logger.warning(f"Failed login attempt for user: {credentials.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    # Reset failed attempts on successful login
    update_failed_login_attempts(db, user.id, increment=False)
    user.locked_until = None
    db.commit()

    # Create tokens
    access_token, refresh_token = create_tokens(user.id)

    logger.info(f"User logged in successfully: {user.email}")
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=ACCESS_TOKEN_EXPIRE_HOURS * 3600
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    token_data: TokenRefresh,
    db: Session = Depends(get_db)
):
    """
    Refresh an access token using a refresh token.
    """
    # Decode refresh token
    payload = decode_token(token_data.refresh_token)
    if payload is None:
        logger.warning("Token refresh attempt with invalid token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token"
        )

    # Check token type
    if payload.get("type") != "refresh":
        logger.warning("Token refresh attempt with non-refresh token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type"
        )

    user_id = payload.get("sub")
    user = get_user_by_id(db, int(user_id))

    if not user or not user.is_active:
        logger.warning(f"Token refresh attempt for inactive/missing user: {user_id}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive"
        )

    # Create new access token (refresh token remains the same)
    access_token, _ = create_tokens(user.id)

    logger.info(f"Token refreshed for user: {user.email}")
    return TokenResponse(
        access_token=access_token,
        refresh_token=token_data.refresh_token,
        expires_in=ACCESS_TOKEN_EXPIRE_HOURS * 3600
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user = Depends(get_current_user)
):
    """
    Get current authenticated user information.
    """
    return current_user
