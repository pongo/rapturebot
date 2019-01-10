# noqa: E402

import unittest
import sys

from unittest.mock import MagicMock

sys.modules['telegram'] = MagicMock()
sys.modules['telegram.ext'] = MagicMock()
sys.modules['src.handlers'] = MagicMock()
sys.modules['src.config'] = MagicMock()
sys.modules['src.config.CONFIG'] = MagicMock()
sys.modules['src.modules.khaleesi'] = MagicMock()
sys.modules['src.utils.handlers_helpers'] = MagicMock()
sys.modules['src.utils.cache'] = MagicMock()
sys.modules['src.utils.logger'] = MagicMock()

from src.modules.weather import parse_temp, get_wind


class Wind(unittest.TestCase):
    def test_empty(self):
        self.assertEqual('', get_wind(0, 0))
        self.assertEqual('порывы ветра до 10 м/с', get_wind(0, 10))

    def test_normal(self):
        self.assertEqual('5 м/с', get_wind(4.73, 0))
        self.assertEqual('5 м/с', get_wind(4.73, 7))
        self.assertEqual('5 м/с (порывы до 10 м/с)', get_wind(4.73, 10))

@unittest.skip
class Temp(unittest.TestCase):
    def test_temp(self):
        data = {
            "time": 1521370035,
            "summary": "Ясно",
            "icon": "clear-day",
            "precipIntensity": 0,
            "precipProbability": 0,
            "temperature": -6.37,
            "apparentTemperature": -12.68,
            "dewPoint": -15.76,
            "humidity": 0.47,
            "pressure": 1018.37,
            "windSpeed": 4.73,
            "windGust": 5.32,
            "windBearing": 280,
            "cloudCover": 0,
            "uvIndex": 2,
            "visibility": 10.01,
            "ozone": 431.87
        }
        self.assertEqual('', parse_temp(data))
