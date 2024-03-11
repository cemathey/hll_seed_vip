from datetime import datetime, timezone
from typing import Final

API_KEY = "API_KEY"
API_KEY_FORMAT = "Bearer: {api_key}"

INDEFINITE_VIP_DATE: Final = datetime(
    year=3000,
    month=1,
    day=1,
    tzinfo=timezone.utc,
)
