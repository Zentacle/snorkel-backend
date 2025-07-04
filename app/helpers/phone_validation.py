import re
from typing import Optional

def format_phone_to_e164(phone: str) -> Optional[str]:
    """
    Format a phone number to E.164 format.

    Args:
        phone: Phone number string (can be in various formats)

    Returns:
        E.164 formatted phone number or None if invalid
    """
    if not phone:
        return None

    # Remove all non-digit characters
    digits_only = re.sub(r'\D', '', phone)

    # Handle US/Canada numbers (assuming +1 if no country code)
    if len(digits_only) == 10:
        return f"+1{digits_only}"
    elif len(digits_only) == 11 and digits_only.startswith('1'):
        return f"+{digits_only}"
    elif len(digits_only) >= 10 and len(digits_only) <= 15:
        # If it starts with a country code, add +
        if not phone.startswith('+'):
            return f"+{digits_only}"
        else:
            return phone

    return None

def validate_phone_format(phone: str) -> bool:
    """
    Validate if a phone number is in a valid format.

    Args:
        phone: Phone number string

    Returns:
        True if valid, False otherwise
    """
    if not phone:
        return True  # Phone is optional

    formatted = format_phone_to_e164(phone)
    return formatted is not None