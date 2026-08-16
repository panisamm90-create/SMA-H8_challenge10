import requests
class HolidayAPI:
    BASE_URL = 'https://date.nager.at/api/v3/PublicHolidays'
    def __init__(self):
        self.session = requests.Session()
    def is_holiday(self,date, country='US'):
        year = date[:4]
        url = f'{self.BASE_URL}/{year}/{country}'
        try:
            response = self.session.get(
                    url,
                    timeout=10
            )
            response.raise_for_status()
            holidays = response.json()
            for holiday in holidays:
                if holiday['date'] == date:
                    return {
                    "is_holiday": True,
                    "holiday_name": holiday['localName'],
                    "country": "US",
                    "date": date
                    }
            return {
                "is_holiday": False,
                "holiday_name": None,
                "country": "US",
                "date": date
                }
        except requests.exceptions.RequestException as e:
            print(f"[HolidayAPI] Request Error: {e}")
            return None
        except KeyError as e:
            print(f"[HolidayAPI] Invalid Response: Missing {e}")
            return None
