from passlib.context import CryptContext
import bcrypt

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def test_auth():
    password = "password123"
    print(f"Testing with password: {password}")
    
    # Hash
    hashed = pwd_context.hash(password)
    print(f"Hashed: {hashed}")
    
    # Verify
    is_valid = pwd_context.verify(password, hashed)
    print(f"Verification: {is_valid}")
    
    # Direct bcrypt test
    if isinstance(hashed, str):
        hashed_bytes = hashed.encode('utf-8')
    else:
        hashed_bytes = hashed
        
    is_valid_bcrypt = bcrypt.checkpw(password.encode('utf-8'), hashed_bytes)
    print(f"Direct Bcrypt Verification: {is_valid_bcrypt}")

if __name__ == "__main__":
    test_auth()
