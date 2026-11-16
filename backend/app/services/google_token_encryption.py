import os

from cryptography.fernet import Fernet

# Encrypt and decrypt Google refresh tokens for database storage.
_FERNET = Fernet(
    os.environ["GOOGLE_TOKEN_ENCRYPTION_KEY"].encode("ascii")
)


# Encrypt a refresh token before saving it.
def encrypt_refresh_token(refresh_token: str) -> str:
    encrypted_token = _FERNET.encrypt(refresh_token.encode("utf-8"))
    return encrypted_token.decode("ascii")


# Decrypt a refresh token after loading it from the database.
def decrypt_refresh_token(encrypted_token: str) -> str:
    token = _FERNET.decrypt(encrypted_token.encode("ascii"))
    return token.decode("utf-8")