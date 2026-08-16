import os
import sys
sys.path.append(
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..")
    )
)
from api.holidays import Holiday_API
holiday_api = Holiday_API()
holiday = holiday_api.is_holiday(
    date='2026-12-25',
    country='US'
)
print(holiday)