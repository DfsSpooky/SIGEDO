from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from cryptography.fernet import Fernet, InvalidToken
import base64

# Initialize Fernet with the key from settings
# The key must be url-safe base64-encoded 32 bytes.
try:
    cipher_suite = Fernet(settings.ID_ENCRYPTION_KEY)
except Exception as e:
    # Handle cases where the key is not configured or invalid
    # You might want to log this error or raise a specific exception
    raise ImproperlyConfigured("ID_ENCRYPTION_KEY is missing or invalid in settings.py") from e

def encrypt_id(id_integer):
    """
    Encrypts an integer ID, returning a URL-safe string.
    """
    if id_integer is None:
        return None
    try:
        # Fernet expects bytes, so we convert the integer to a string and then to bytes
        id_bytes = str(id_integer).encode('utf-8')
        encrypted_bytes = cipher_suite.encrypt(id_bytes)
        # The result is already URL-safe base64, but we decode to a string for URLs
        return encrypted_bytes.decode('utf-8')
    except Exception as e:
        # Handle potential encryption errors
        # Log the error for debugging
        return None

def decrypt_id(encrypted_string):
    """
    Decrypts a string, returning an integer ID.
    Returns None if the token is invalid or expired.
    """
    if encrypted_string is None:
        return None
    try:
        # The input must be bytes
        encrypted_bytes = encrypted_string.encode('utf-8')
        decrypted_bytes = cipher_suite.decrypt(encrypted_bytes)
        # Convert the decrypted bytes back to an integer
        return int(decrypted_bytes.decode('utf-8'))
    except (InvalidToken, TypeError, ValueError) as e:
        # InvalidToken is raised if the token is invalid or tampered with.
        # TypeError/ValueError can happen if the decrypted string is not a valid integer.
        # Log the error for debugging purposes
        return None
