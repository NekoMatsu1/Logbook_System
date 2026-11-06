import re
import unicodedata

STUDENT_ID_ERROR = 'Student ID must be exactly 10 digits (0-9). Letters, spaces and symbols are not allowed.'
STUDENT_NAME_ERROR = 'Enter the full name as Surname, FirstName, Middle Name. Example: Dela Cruz, Juan, Santos.'
STUDENT_PASSWORD_ERROR = 'Password must be 10-128 characters and contain at least one letter and one number.'

def valid_student_id(value):
    return isinstance(value, str) and re.fullmatch(r'[0-9]{10}', value) is not None


def valid_student_name(value):
    if not isinstance(value, str) or len(value)>128:
        return False
    parts = value.split(', ')
    if len(parts)!=3 or ', '.join(parts)!=value:
        return False
    for part in parts:
        if not part or part!=part.strip() or sum(c.isalpha() for c in part)<2:
            return False
        if not part[0].isalpha() or unicodedata.category(part[-1])[0] not in ('L','M'):
            return False
        previous_separator = False
        for char in part:
            if unicodedata.category(char)[0] in ('L','M'):
                previous_separator = False
            elif char in (" ", "-", "'", '’') and not previous_separator:
                previous_separator = True
            else:
                return False
    return True


def valid_student_password(value):
    return (isinstance(value, str) and 10 <= len(value) <= 128
            and not any(ord(char) < 32 for char in value)
            and any(char.isalpha() for char in value)
            and any(char.isdigit() for char in value))

DEFAULTS = dict(inactivity_seconds=300, logout_warning_seconds=60,
                shutdown_wait_seconds=600, shutdown_warning_seconds=60,
                identification_timeout_seconds=60, heartbeat_timeout_seconds=45,
                auto_logout=True, auto_shutdown=True)
