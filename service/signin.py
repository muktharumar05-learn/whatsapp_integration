from fastapi import HTTPException, status, Request
from fastapi.responses import RedirectResponse
from database.retrieve_data import fetch_user_by_username
from service.security import verify_password

async def authenticate_user(username: str, password: str):
    user = await fetch_user_by_username(username)

    # Generic error message for better security
    invalid_cred_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid phone number or password",
    )

    if not user:
        raise invalid_cred_exception

    # Use the key 'password_hash' because that's what we named it in your DB init!
    if not verify_password(password, user["password_hash"]):
        raise invalid_cred_exception

    return user

from fastapi.responses import RedirectResponse
from starlette import status

def login_required(request: Request):
    user = request.session.get("user")
    if not user:
        # ✅ Return the redirect object if not logged in
        return RedirectResponse(
            url="/login", 
            status_code=status.HTTP_303_SEE_OTHER
        )
    return None # ✅ Return None if they are authorized