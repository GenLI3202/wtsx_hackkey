from fastapi import FastAPI
from services.weather import WeatherService
from services.price import PriceService
from services.battery import BatteryService
from services.optimizer import OptimizerService
from agent.client import WatsonXAgent
import config

app = FastAPI(title="GridKey BESS Optimizer API")

# Initialize Services
weather_service = WeatherService()
price_service = PriceService()
battery_service = BatteryService()
optimizer_service = OptimizerService(api_url="http://localhost:8000") # Placeholder
agent = WatsonXAgent()

@app.get("/")
def read_root():
    return {"message": "Welcome to GridKey BESS Optimizer API"}

@app.get("/health")
def health_check():
    return {"status": "ok"}
