from services.weather import WeatherService
from services.price import PriceService
from services.optimizer import OptimizerService

class AgentTools:
    """
    Tools exposed to the WatsonX Agent.
    """
    def __init__(self):
        self.weather = WeatherService()
        self.price = PriceService()
        self.optimizer = OptimizerService("http://localhost:8000")

    def get_weather(self, location: str):
        return self.weather.get_generation_forecast(location)

    def get_prices(self, country: str):
        return self.price.get_market_prices(country)

    def optimize(self, weather_data, price_data):
        # This would need more complex logic to gather inputs
        pass
