import os
import base64
import jwt
from fastapi import Request, HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()

# Require JWT_SECRET from environment variable
JWT_SECRET_B64 = os.environ.get("JWT_SECRET")
if not JWT_SECRET_B64:
    raise RuntimeError("JWT_SECRET environment variable is not set!")
JWT_SECRET_B64 = JWT_SECRET_B64.strip()

try:
    # Add padding if necessary
    padded_b64 = JWT_SECRET_B64 + "=" * ((4 - len(JWT_SECRET_B64) % 4) % 4)
    # Decode base64 to get the actual bytes used for HS256/384/512
    JWT_SECRET_BYTES = base64.b64decode(padded_b64)
except Exception:
    # Fallback to string encode if invalid base64 (just in case)
    JWT_SECRET_BYTES = JWT_SECRET_B64.encode('utf-8')

async def verify_token(credentials: HTTPAuthorizationCredentials = Security(security)):
    token = credentials.credentials
    try:
        # Verify the token using PyJWT (Spring Boot might use HS384 or HS512 depending on key length)
        payload = jwt.decode(token, JWT_SECRET_BYTES, algorithms=["HS256", "HS384", "HS512"])
        return payload
    except jwt.ExpiredSignatureError:
        print("Token expired error")
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError as e:
        print(f"Invalid token error: {str(e)}")
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")
    except Exception as e:
        print(f"Other token error: {str(e)}")
        raise HTTPException(status_code=401, detail="Unauthorized")
