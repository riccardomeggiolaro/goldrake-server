from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Callable
import jwt
import traceback
from datetime import datetime, timedelta
from pydantic import BaseModel

class TokenData(BaseModel):
    sub: str 
    exp: datetime

class AuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, secret_key: str):
        super().__init__(app)
        self.secret_key = secret_key
        self.algorithm = "HS256"

    async def dispatch(self, request: Request, call_next: Callable):
        # Skip authentication for specific routes
        if request.url.path in ["/login", "/login.html", "/docs", "/openapi.json"]:
            return await call_next(request)

        try:
            # Check Authorization header
            auth_header = request.headers.get("Authorization")
            if not auth_header:
                return JSONResponse(
                    status_code=401, 
                    content={"detail": "Authentication required"}
                )

            # Extract token
            try:
                scheme, token = auth_header.split()
            except ValueError:
                return JSONResponse(
                    status_code=401, 
                    content={"detail": "Invalid Authorization header"}
                )

            if scheme.lower() != "bearer":
                return JSONResponse(
                    status_code=401, 
                    content={"detail": "Invalid authentication scheme"}
                )

            # Decode token
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            token_data = TokenData(**payload)

            # Check token expiration
            if token_data.exp < datetime.utcnow():
                return JSONResponse(
                    status_code=401, 
                    content={"detail": "Token expired"}
                )

            # Attach user data to request
            request.state.user = token_data

            # Continue with request
            response = await call_next(request)
            return response

        except jwt.PyJWTError:
            return JSONResponse(
                status_code=401, 
                content={"detail": "Invalid token"}
            )
        except Exception as e:
            print(f"Unexpected error: {traceback.format_exc()}")
            return JSONResponse(
                status_code=500, 
                content={"detail": "Internal authentication error"}
            )

def create_access_token(data: dict, secret_key: str, expires_delta: timedelta = timedelta(hours=1)):
    to_encode = data.copy()
    expire = datetime.utcnow() + expires_delta
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, secret_key, algorithm="HS256")