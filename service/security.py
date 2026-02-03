import bcrypt
import hashlib

def hash_password(password: str) -> str:
    # 1. Pre-hash with SHA-256 to handle any length
    # This turns any password into a 64-character string
    pw_hash = hashlib.sha256(password.encode('utf-8')).hexdigest()
    
    # 2. Hash with bcrypt (now it will NEVER exceed 72 bytes)
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(pw_hash.encode('utf-8'), salt)
    
    return hashed.decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    # Use the same SHA-256 step before checking
    pw_hash = hashlib.sha256(plain_password.encode('utf-8')).hexdigest()
    return bcrypt.checkpw(pw_hash.encode('utf-8'), hashed_password.encode('utf-8'))