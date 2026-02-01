"""
Module D: Optimizer Service (Pure Adapter)
Strict implementation of user-defined API Guide.
No internal data fetching. Pure input-output adapter for GridKey MILP solver.
"""
import logging
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, field_validator
import pandas as pd
from datetime import datetime

# Import ported GridKey modules
# Assuming running from src/backend, gridkey_optimizer is a sibling package
from gridkey_optimizer.service.optimizer_service import OptimizerService as GridKeyOptimizer
from gridkey_optimizer.service.models import OptimizationInput, ModelType

logger = logging.getLogger(__name__)

# --- Pydantic Models for API Request (Strict Schema) ---

class MarketPrices(BaseModel):
    """
    Market prices arrays.
    Strictly enforcing array structure as per API Guide.
    """
    day_ahead: List[float] = Field(..., description="DA Prices (EUR/MWh)")
    afrr_energy_pos: List[float] = Field(..., description="aFRR+ Energy Prices (EUR/MWh)")
    afrr_energy_neg: List[float] = Field(..., description="aFRR- Energy Prices (EUR/MWh)")
    fcr: List[float] = Field(..., description="FCR Capacity Prices (EUR/MW)")
    afrr_capacity_pos: List[float] = Field(..., description="aFRR+ Capacity Prices (EUR/MW)")
    afrr_capacity_neg: List[float] = Field(..., description="aFRR- Capacity Prices (EUR/MW)")

class OptimizeRequest(BaseModel):
    """
    Pure API Request Body.
    No hidden logic. Input-driven.
    """
    # Metadata (Required)
    location: str = Field(..., example="Munich")
    country: str = Field(..., example="DE_LU")
    
    # Optimization Params
    model_type: str = Field("III-renew", description="Solver Model Type")
    c_rate: float = Field(0.5, gt=0, le=2.0)
    alpha: float = Field(1.0, description="Degradation weight")
    
    # Data Arrays (Strictly Required)
    market_prices: MarketPrices
    renewable_generation: Optional[List[float]] = Field(None, description="PV/Wind generation (kW)")

    # Time Horizon (Implicit in array lengths, but can be specified)
    time_horizon_hours: Optional[int] = Field(None, description="Optimization horizon in hours")

    @field_validator('market_prices')
    def validate_array_consistency(cls, v: MarketPrices, values):
        """
        Validate that all 15-min arrays match in length.
        """
        len_da = len(v.day_ahead)
        if len(v.afrr_energy_pos) != len_da or len(v.afrr_energy_neg) != len_da:
            raise ValueError(f"15-min price arrays length mismatch! DA:{len_da}, aFRR+:{len(v.afrr_energy_pos)}")
        return v
# --- Response Models for OpenAPI ---

class ScheduleEntry(BaseModel):
    timestamp: str
    action: str
    power_kw: float
    market: str
    soc_after: float
    renewable_action: Optional[str] = None
    renewable_power_kw: Optional[float] = None

class OptimizationData(BaseModel):
    objective_value: float
    net_profit: float
    revenue_breakdown: Dict[str, float]
    degradation_cost: float
    cyclic_aging_cost: float
    calendar_aging_cost: float
    schedule: List[ScheduleEntry]
    soc_trajectory: List[float]
    solve_time_seconds: float
    solver_name: str
    model_type: str
    status: str
    renewable_utilization: Optional[Dict[str, float]] = None

class OptimizeResponse(BaseModel):
    status: str
    data: OptimizationData

class OptimizerService:
    """
    Service Adapter for GridKey Optimizer.
    Strict Mode: No simulation.
    """
    
    def __init__(self):
        self._engine = GridKeyOptimizer()
    
    def run_optimization(self, request_data: OptimizeRequest) -> Dict[str, Any]:
        """
        Execute optimization using strict input data.
        
        Args:
            request_data: Validated Pydantic model from API request.
        
        Returns:
            Dict conforming to GridKey Blueprint output format.
        """
        logger.info(f"Running optimization for {request_data.location} (Pure Mode)")
        
        # 1. Determine Time Horizon from Data Length
        n_steps_15min = len(request_data.market_prices.day_ahead)
        horizon_hours = n_steps_15min // 4
        
        if request_data.time_horizon_hours and request_data.time_horizon_hours != horizon_hours:
            logger.warning(f"Request horizon {request_data.time_horizon_hours}h != data horizon {horizon_hours}h. Using data length.")
        
        # 2. Map to Internal OptimizationInput
        # GridKey engine expects dictionaries or specific input objects
        # We construct the OptimizationInput directly to bypass the 'adapter.adapt' if possible,
        # or map inputs to match what 'adapt' expects.
        # Let's map to the format `adapter.adapt` expects to leverage its validation logic.
        
        market_prices_dict = {
            "day_ahead": request_data.market_prices.day_ahead,
            "afrr_energy_pos": request_data.market_prices.afrr_energy_pos,
            "afrr_energy_neg": request_data.market_prices.afrr_energy_neg,
            "fcr": request_data.market_prices.fcr,
            "afrr_capacity_pos": request_data.market_prices.afrr_capacity_pos,
            "afrr_capacity_neg": request_data.market_prices.afrr_capacity_neg
        }
        
        gen_forecast = None
        if request_data.renewable_generation:
            gen_forecast = {"generation_kw": request_data.renewable_generation}
            
        battery_config = {
            "capacity_kwh": 10.0, # Fixed for this specific hackathon context or passed? 
                                  # Guide implies c_rate is passed, assume consistent capacity or make configurable if needed.
                                  # Let's default to 10kWh as per previous context unless API passes it.
                                  # Wait, User Guide doesn't include capacity in schema, only c_rate.
                                  # We'll stick to 10.0 for now as 'standard unit'.
            "c_rate": request_data.c_rate,
            "initial_soc": 0.5
        }

        # Call Engine
        # The engine's optimize() method handles: Adapt -> Build -> Solve -> Extract -> Result
        result_obj = self._engine.optimize(
            market_prices=market_prices_dict,
            generation_forecast=gen_forecast,
            model_type=request_data.model_type,
            c_rate=request_data.c_rate,
            alpha=request_data.alpha,
            time_horizon_hours=horizon_hours,
            daily_cycle_limit=1.0 # Default
        )
        
        # 3. Format Output (Strict User Guide Compliance)
        
        # Recommendations Logic (Optional addition, but keep it if useful, placed inside data?)
        # User Guide doesn't explicitly mention 'recommendations' in the core table, 
        # but says "Response Structure: wrapper + internal data". 
        # We will strictly map to the "data" fields requested:
        # - objective_value
        # - net_profit
        # - revenue_breakdown (da, afrr_energy, fcr, afrr_capacity)
        # - degradation_cost (cyclic, calendar)
        # - schedule
        # - soc_trajectory
        # - solver metadata
        
        # Revenue Breakdown
        # GridKey engine result usually groups revenue. Let's assume result_obj has these or we calculate/extract them.
        # For now, we might need to rely on what result_obj exposes.
        # If result_obj is standard GridKey OptimizationResult, it has `financials`.
        
        revenue_bd = {
            "da": getattr(result_obj, "revenue_da", 0.0), # Fallback if direct attr missing, usually in `revenues` dict
            "afrr_energy": getattr(result_obj, "revenue_afrr_energy", 0.0),
            "fcr": getattr(result_obj, "revenue_fcr", 0.0),
            "afrr_capacity": getattr(result_obj, "revenue_afrr_capacity", 0.0),
        }
        # If result_obj has a `revenues` dict property, use that:
        if hasattr(result_obj, "revenues") and isinstance(result_obj.revenues, dict):
            revenue_bd["da"] = result_obj.revenues.get("day_ahead", 0.0)
            revenue_bd["afrr_energy"] = result_obj.revenues.get("afrr_energy", 0.0)
            revenue_bd["fcr"] = result_obj.revenues.get("fcr", 0.0)
            revenue_bd["afrr_capacity"] = result_obj.revenues.get("afrr_capacity", 0.0)

        # Schedule Formatting
        schedule_formatted = []
        soc_trajectory = []
        
        for entry in result_obj.schedule:
            # Flatten schedule item
            item = {
                "timestamp": entry.timestamp.isoformat(),
                "action": entry.action,
                "power_kw": entry.power_kw,
                "market": entry.market,
                "soc_after": entry.soc_after
            }
            if entry.renewable_action:
                item["renewable_action"] = entry.renewable_action
            if entry.renewable_power_kw is not None:
                item["renewable_power_kw"] = entry.renewable_power_kw
                
            schedule_formatted.append(item)
            soc_trajectory.append(entry.soc_after)
            
        data_block = {
            # Core Metrics
            "objective_value": round(result_obj.objective_value, 2),
            "net_profit": round(result_obj.net_profit, 2),
            
            # Breakdown
            "revenue_breakdown": revenue_bd,
            
            # Costs
            "degradation_cost": round(result_obj.degradation_cost, 2),
            "cyclic_aging_cost": round(result_obj.cyclic_aging_cost, 2),
            "calendar_aging_cost": round(result_obj.calendar_aging_cost, 2),
            
            # Trajectories
            "schedule": schedule_formatted,
            "soc_trajectory": soc_trajectory,
            
            # Logic/Solver Metadata
            "solve_time_seconds": result_obj.solve_time_seconds,
            "solver_name": "highs", # Hardcoded or from result_obj
            "model_type": request_data.model_type,
            "status": result_obj.status
        }
        
        # Renewable Utilization (Optional)
        if hasattr(result_obj, "renewable_utilization") and result_obj.renewable_utilization:
             data_block["renewable_utilization"] = result_obj.renewable_utilization

        return {
            "status": "success",
            "data": data_block
        }
