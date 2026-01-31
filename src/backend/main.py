from fastapi import FastAPI, Query
from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime

from services.weather import WeatherService, AssetConfig, GenerationForecast
from services.price import PriceService
from services.battery import BatteryService
from services.optimizer import OptimizerService
from agent.client import WatsonXAgent
import config

app = FastAPI(
    title="GridKey BESS Optimizer API",
    description="Energy optimization API with Weather, Price, Battery, and Optimizer services",
    version="1.0.0",
    servers=[
        {"url": "https://superindulgent-francine-nonpessimistic.ngrok-free.dev", "description": "ngrok tunnel"},
    ]
)

# Initialize Services
api_key = config.OPENWEATHER_API_KEY or "demo_key"
weather_service = WeatherService(api_key=api_key)
price_service = PriceService()
battery_service = BatteryService()
optimizer_service = OptimizerService(api_url="http://localhost:8000")
agent = WatsonXAgent()


# ============================================================================
# Response Models (for OpenAPI spec)
# ============================================================================

class GenerationPointResponse(BaseModel):
    timestamp: datetime
    pv_output_kw: float
    wind_output_kw: float
    total_output_kw: float

class WeatherForecastResponse(BaseModel):
    location: str
    generated_at: datetime
    timeline: List[GenerationPointResponse]


# ============================================================================
# Health & Root
# ============================================================================

@app.get("/")
def read_root():
    return {"message": "Welcome to GridKey BESS Optimizer API"}

@app.get("/health")
def health_check():
    return {"status": "ok"}


# ============================================================================
# Weather Service Endpoints
# ============================================================================

@app.get("/weather/forecast", response_model=WeatherForecastResponse, tags=["Weather"])
def get_weather_forecast(
    location: str = Query("Munich", description="City name (Munich, Berlin, Shanghai) or coordinates"),
    hours: int = Query(24, description="Forecast hours (1-120)", ge=1, le=120),
    pv_capacity_kw: float = Query(10.0, description="PV capacity in kW"),
    wind_capacity_kw: float = Query(50.0, description="Wind turbine capacity in kW")
):
    """
    Get weather-based renewable energy generation forecast.
    
    Returns hourly PV and Wind generation predictions for the specified location.
    """
    asset_config = AssetConfig(
        pv_capacity_kw=pv_capacity_kw,
        wind_capacity_kw=wind_capacity_kw
    )
    
    forecast = weather_service.get_generation_forecast(
        location=location,
        forecast_hours=hours,
        asset_config=asset_config
    )
    
    return forecast


# ============================================================================
# Price Service Endpoints
# ============================================================================

@app.get("/price/forecast", tags=["Price"])
def get_price_forecast(
    country: str = Query("DE_LU", description="Country/Bidding zone (DE_LU, AT, CH, HU, CZ)"),
    hours: int = Query(48, description="Forecast hours (1-168)", ge=1, le=168)
):
    """
    Get electricity market prices for all markets.
    
    Returns Day-Ahead, FCR, aFRR Capacity, and aFRR Energy prices for the specified country.
    """
    prices = price_service.get_market_prices(
        country=country,
        forecast_hours=hours
    )
    
    return {
        "country": prices.country,
        "forecast_hours": prices.forecast_hours,
        "retrieved_at": prices.retrieved_at.isoformat(),
        "day_ahead": prices.day_ahead.to_gridkey_format() if prices.day_ahead else None,
        "fcr": prices.fcr.to_gridkey_format() if prices.fcr else None,
        "afrr_capacity": prices.afrr_capacity.to_gridkey_format() if prices.afrr_capacity else None,
        "afrr_energy": prices.afrr_energy.to_gridkey_format() if prices.afrr_energy else None,
    }

