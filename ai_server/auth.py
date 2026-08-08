import os
import base64
import jwt
from fastapi import Request, HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()

# Default secret from Spring Boot (Base64 encoded string)
JWT_SECRET_B64 = os.environ.get("JWT_SECRET", "VmFjYXRpb25KWRnZVNlY3JldEtleUZvckp3dEF1dGhlbnRpY2F0aW9uV2l0aFNwcmluZ1NlY3VyaXR5")

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
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=401, detail="Unauthorized")
