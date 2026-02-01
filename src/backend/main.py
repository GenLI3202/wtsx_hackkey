from fastapi import FastAPI, Query
from typing import Optional, List, Dict
from pydantic import BaseModel, Field
from datetime import datetime

from services.weather import WeatherService, AssetConfig, GenerationForecast
from services.price import PriceService
from services.battery import BatteryService
from services.battery import BatteryService
# OptimizerService imported later from src.backend.services.optimizer
from agent.client import WatsonXAgent
import env_config as config

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
battery_service = BatteryService()
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
# Optimizer Models
# ============================================================================

# Optimizer Models have been moved to services.optimizer


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
    
    # Helper to safely extract flat list from PriceData
    def get_price_list(p_data, cty, suffix=""):
        if not p_data or not p_data.prices:
            return []
        
        # Determine key (DE_LU vs DE)
        # Mock generators use "DE" for FCR/aFRR if input was DE_LU
        # DayAhead uses DE_LU
        key = cty
        if p_data.market_type != "day_ahead":
            key = cty.replace("_LU", "")
        
        target_key = f"{key}{suffix}"
        
        # Check specific key
        if target_key in p_data.prices:
            return p_data.prices[target_key]
        
        # Fallback to first available key if specific not found (e.g. simple mock)
        if p_data.prices:
            return list(p_data.prices.values())[0]
        return []

    return {
        "country": prices.country,
        "forecast_hours": prices.forecast_hours,
        "retrieved_at": prices.retrieved_at.isoformat(),
        
        # Flattened Arrays for Optimizer
        "day_ahead": get_price_list(prices.day_ahead, country),
        "fcr": get_price_list(prices.fcr, country),
        "afrr_energy_pos": get_price_list(prices.afrr_energy, country, "_Pos"),
        "afrr_energy_neg": get_price_list(prices.afrr_energy, country, "_Neg"),
        "afrr_capacity_pos": get_price_list(prices.afrr_capacity, country, "_Pos"),
        "afrr_capacity_neg": get_price_list(prices.afrr_capacity, country, "_Neg"),
    }


# ============================================================================
# Optimizer Service Endpoints
# ============================================================================

# --- Pure Optimizer API (Strict Guide Compliance) ---

# from src.backend.services.optimizer import OptimizerService, OptimizeRequest 
from services.optimizer import OptimizerService, OptimizeRequest, OptimizeResponse

@app.post("/api/v1/optimize", tags=["Optimizer"], summary="Flexible Horizon Optimization", response_model=OptimizeResponse)
def optimize_flexible(request: OptimizeRequest):
    """
    optimize_flexible
    
    Pure logic optimization. 
    Accepts market prices and renewable generation.
    Returns optimal schedule.
    """
    optimizer = OptimizerService()
    try:
        result = optimizer.run_optimization(request)
        return result
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Optimization error: {e}")
        raise HTTPException(status_code=500, detail="Internal Optimizer Error")

@app.post("/api/v1/optimize-mpc", tags=["Optimizer"], summary="MPC Rolling Horizon (12h)", response_model=OptimizeResponse)
def optimize_mpc(request: OptimizeRequest):
    """
    optimize_mpc
    
    Fixed 12h horizon using Rolling Horizon strategy.
    Requires 48 data points (15-min resolution).
    """
    optimizer = OptimizerService()
    
    # Enforce 12h data length
    if len(request.market_prices.day_ahead) != 48:
        raise HTTPException(status_code=422, detail="MPC endpoint requires exactly 48 data points (12h)")
        
    try:
        # For this hackathon, we alias MPC to the main logic but enforce the horizon
        request.time_horizon_hours = 12
        result = optimizer.run_optimization(request)
        return result
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"MPC Optimization error: {e}")
        raise HTTPException(status_code=500, detail="Internal Optimizer Error")


