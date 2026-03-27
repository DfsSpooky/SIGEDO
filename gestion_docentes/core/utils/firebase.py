import os
import json
import logging
import firebase_admin
from firebase_admin import credentials
from django.conf import settings

logger = logging.getLogger(__name__)

def initialize_firebase():
    """
    Centralized Firebase initialization.
    Order of precedence:
    1. FIREBASE_SERVICE_ACCOUNT_JSON (Environment variable with JSON content)
    2. FIREBASE_SERVICE_ACCOUNT_PATH (Environment variable with path to JSON file)
    3. serviceAccountKey.json in BASE_DIR (Default file path)
    """
    if firebase_admin._apps:
        return True

    try:
        # 1. Check for JSON content in environment variable
        cert_json = os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON")
        if cert_json:
            cert_dict = json.loads(cert_json)
            cred = credentials.Certificate(cert_dict)
            firebase_admin.initialize_app(cred)
            logger.info("Firebase initialized via FIREBASE_SERVICE_ACCOUNT_JSON")
            return True

        # 2. Check for path in environment variable
        cert_path = os.environ.get("FIREBASE_SERVICE_ACCOUNT_PATH")
        if cert_path and os.path.exists(cert_path):
            cred = credentials.Certificate(cert_path)
            firebase_admin.initialize_app(cred)
            logger.info(f"Firebase initialized via path: {cert_path}")
            return True

        # 3. Fallback to default path (solo desarrollo/local)
        default_path = os.path.join(settings.BASE_DIR, "serviceAccountKey.json")
        if getattr(settings, "ALLOW_LOCAL_FIREBASE_FILE", False) and os.path.exists(
            default_path
        ):
            cred = credentials.Certificate(default_path)
            firebase_admin.initialize_app(cred)
            logger.info("Firebase initialized via default local path")
            return True

        logger.warning(
            "Firebase credentials not found. Push notifications will be disabled."
        )
        return False

    except Exception as e:
        logger.error(f"Error initializing Firebase: {e}")
        return False
