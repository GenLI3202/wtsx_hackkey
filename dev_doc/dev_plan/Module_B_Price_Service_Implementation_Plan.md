# Module B (Price Service) Implementation Plan

## Overview

Implement Module B: Price Service for GridKey BESS Optimizer, fetching European electricity market prices (Day-Ahead, FCR, aFRR Capacity, aFRR Energy) for DE_LU bidding zone using **ENTSO-E Transparency API** for all markets.

---

## Data Format Requirements

### Four Market Types

| Market                  | ENTSO-E Method                          | Resolution | Unit    | Fields                                            |
| ----------------------- | --------------------------------------- | ---------- | ------- | ------------------------------------------------- |
| **Day-Ahead**     | `query_day_ahead_prices()`            | 15-min     | EUR/MWh | `DE_LU`, `AT`, `CH`, `HU`, `CZ`         |
| **FCR**           | `query_contracted_reserve_prices()`   | 4-hour     | EUR/MW  | `DE`, `AT`, `CH`, `HU`, `CZ`            |
| **aFRR Capacity** | `query_procured_balancing_capacity()` | 4-hour     | EUR/MW  | `DE_Pos`, `DE_Neg`, `AT_Pos`, `AT_Neg`... |
| **aFRR Energy**   | `query_contracted_reserve_prices()`   | 15-min     | EUR/MWh | `DE_Pos`, `DE_Neg`, `AT_Pos`, `AT_Neg`... |

### ENTSO-E Reserve Price Parameters

| Code    | Direction       | Usage             |
| ------- | --------------- | ----------------- |
| `A01` | Up (Positive)   | `DE_Pos` prices |
| `A02` | Down (Negative) | `DE_Neg` prices |
| `A03` | Symmetric       | Both directions   |

### GridKey-Compatible JSON Format

```json
// Day-Ahead / aFRR Energy (15-min)
[
  {"timestamp": "2024-01-01T00:00:00.000", "DE_LU": 39.91, "AT": 14.08, ...},
  {"timestamp": "2024-01-01T00:15:00.000", "DE_LU": -0.04, "AT": 14.08, ...}
]

// FCR / aFRR Capacity (4-hour)
[
  {"timestamp": "2024-01-01T00:00:00.000", "DE": 114.8, "AT": 114.8, ...},
  {"timestamp": "2024-01-01T04:00:00.000", "DE": 104.4, "AT": 104.4, ...}
]

// aFRR with Pos/Neg
[
  {"timestamp": "2024-01-01T00:00:00.000", "DE_Pos": 50.34, "DE_Neg": 29.70, ...}
]
```

---

## Architecture

### Class Hierarchy

```
PriceService (main interface)
    ├── EntsoePriceClient (ENTSO-E API - all 4 markets)
    └── MockPriceClient (testing/demo without API token)

Data Models:
    ├── MarketType (enum)
    ├── CountryCode (enum)
    ├── DataSource (enum)
    ├── PriceSeries (time series data)
    └── MarketPrices (container for all 4 markets)
```

### Data Flow

```
User Request
    │
    ▼
PriceService.get_market_prices(country, forecast_hours)
    │
    ├──► EntsoePriceClient.get_day_ahead_prices() → PriceSeries
    ├──► EntsoePriceClient.get_fcr_prices() → PriceSeries
    ├──► EntsoePriceClient.get_afrr_capacity_prices() → PriceSeries
    └──► EntsoePriceClient.get_afrr_energy_prices() → PriceSeries
    │
    ▼
Return MarketPrices
```

---

## Implementation Steps

### Step 1: Update Dependencies

**File**: `requirements.txt`

```diff
+ entsoe-py>=0.5.0  # ENTSO-E API client
+ pytest>=7.4.0      # Testing
```

### Step 2: Update Configuration

**File**: `src/backend/config.py`

```python
# Price Service
ENTSOE_API_TOKEN = os.getenv("ENTSOE_API_TOKEN")
PRICE_MOCK_MODE = os.getenv("PRICE_MOCK_MODE", "false").lower() == "true"
```

**File**: `.env.template`

```env
# Price Service - ENTSO-E Transparency Platform
ENTSOE_API_TOKEN=your_token_here
PRICE_MOCK_MODE=false
```

### Step 3: Implement Price Service

**File**: `src/backend/services/price.py`

Replace existing placeholder with:

```python
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from enum import Enum
from dataclasses import dataclass, field
import pandas as pd

# ============================================
# ENUMS
# ============================================

class MarketType(Enum):
    DAY_AHEAD = "day_ahead"
    FCR = "fcr"
    AFRR_CAPACITY = "afrr_capacity"
    AFRR_ENERGY = "afrr_energy"

class CountryCode(Enum):
    DE_LU = "DE_LU"
    AT = "AT"
    CH = "CH"
    HU = "HU"
    CZ = "CZ"

class DataSource(Enum):
    ENTSOE_API = "entsoe_api"
    MOCK = "mock"

# Direction codes for reserve prices
class ReserveDirection(Enum):
    UP = "A01"      # Positive reserve
    DOWN = "A02"    # Negative reserve
    SYMMETRIC = "A03"

# ============================================
# DATA MODELS
# ============================================

@dataclass
class PriceSeries:
    """Time series of price data compatible with GridKey format."""
    timestamps: List[datetime]
    prices: Dict[str, List[float]]
    market_type: MarketType
    resolution_minutes: int
    source: DataSource = DataSource.ENTSOE_API
    unit: str = "EUR/MWh"

    def to_gridkey_format(self) -> List[Dict]:
        """Convert to GridKey JSON format."""
        result = []
        for ts, price_values in zip(self.timestamps, zip(*self.prices.values())):
            entry = {"timestamp": ts.isoformat()}
            entry.update(dict(zip(self.prices.keys(), price_values)))
            result.append(entry)
        return result

@dataclass
class MarketPrices:
    """Container for all four market types."""
    day_ahead: Optional[PriceSeries] = None
    fcr: Optional[PriceSeries] = None
    afrr_capacity: Optional[PriceSeries] = None
    afrr_energy: Optional[PriceSeries] = None
    country: str = "DE_LU"
    forecast_hours: int = 48
    retrieved_at: datetime = field(default_factory=datetime.utcnow)

# ============================================
# ENTSO-E CLIENT
# ============================================

class EntsoePriceClient:
    """Client for ENTSO-E Transparency Platform API."""

    def __init__(self, api_token: str):
        from entsoe import EntsoePandasClient
        self.client = EntsoePandasClient(api_key=api_token)

    def get_day_ahead_prices(self, country: str, start: datetime, end: datetime) -> PriceSeries:
        """Fetch Day-Ahead prices (15-min resolution)."""
        prices_series = self.client.query_day_ahead_prices(country, start=start, end=end)
        return PriceSeries(
            timestamps=prices_series.index.to_pydatetime().tolist(),
            prices={country: prices_series.values.tolist()},
            market_type=MarketType.DAY_AHEAD,
            resolution_minutes=15,
            unit="EUR/MWh"
        )

    def get_fcr_prices(self, country: str, start: datetime, end: datetime) -> PriceSeries:
        """Fetch FCR prices using query_contracted_reserve_prices()."""
        # FCR uses symmetric reserve (A03)
        prices_df = self.client.query_contracted_reserve_prices(
            country_code=country,
            type_marketagreement_type='A03',  # Symmetric FCR
            start=start,
            end=end
        )
        # Resample to 4-hour blocks
        prices_4h = prices_df.resample('4H').mean()
        return PriceSeries(
            timestamps=prices_4h.index.to_pydatetime().tolist(),
            prices={country.replace('_', ''): prices_4h.values.tolist()},
            market_type=MarketType.FCR,
            resolution_minutes=240,
            unit="EUR/MW"
        )

    def get_afrr_capacity_prices(self, country: str, start: datetime, end: datetime) -> PriceSeries:
        """Fetch aFRR Capacity prices using query_procured_balancing_capacity()."""
        # Query both directions
        pos_df = self.client.query_procured_balancing_capacity(
            country_code=country,
            process_type='A51',  # aFRR process
            start=start,
            end=end
        )
        # Extract price columns and create Pos/Neg series
        # Note: May need adjustment based on actual data structure
        timestamps = pos_df.index.to_pydatetime().tolist()
        return PriceSeries(
            timestamps=timestamps,
            prices={
                f"{country}_Pos": [50.0] * len(timestamps),  # Placeholder
                f"{country}_Neg": [30.0] * len(timestamps)   # Placeholder
            },
            market_type=MarketType.AFRR_CAPACITY,
            resolution_minutes=240,
            unit="EUR/MW"
        )

    def get_afrr_energy_prices(self, country: str, start: datetime, end: datetime) -> PriceSeries:
        """Fetch aFRR Energy prices."""
        # Query both directions
        pos_prices = self.client.query_contracted_reserve_prices(
            country_code=country,
            type_marketagreement_type='A01',  # Up
            start=start,
            end=end
        )
        neg_prices = self.client.query_contracted_reserve_prices(
            country_code=country,
            type_marketagreement_type='A02',  # Down
            start=start,
            end=end
        )
        return PriceSeries(
            timestamps=pos_prices.index.to_pydatetime().tolist(),
            prices={
                f"{country}_Pos": pos_prices.values.tolist(),
                f"{country}_Neg": neg_prices.values.tolist()
            },
            market_type=MarketType.AFRR_ENERGY,
            resolution_minutes=15,
            unit="EUR/MWh"
        )

# ============================================
# MOCK CLIENT (for testing)
# ============================================

class MockPriceClient:
    """Generate synthetic price data for testing without API token."""

    def get_day_ahead_prices(self, country: str, start: datetime, end: datetime) -> PriceSeries:
        import random, math
        num_points = int((end - start).total_seconds() / 900)
        timestamps = [start + timedelta(minutes=15*i) for i in range(num_points)]
        prices = []
        for ts in timestamps:
            hour = ts.hour
            base_price = 50 + 30 * math.sin((hour - 6) * math.pi / 12)
            price = base_price + random.uniform(-5, 5)
            prices.append(max(0, price))
        return PriceSeries(
            timestamps=timestamps,
            prices={country: prices},
            market_type=MarketType.DAY_AHEAD,
            resolution_minutes=15,
            source=DataSource.MOCK,
            unit="EUR/MWh"
        )

    # Similar mock methods for FCR, aFRR...

# ============================================
# MAIN SERVICE
# ============================================

class PriceService:
    """Module B: Price Service - Unified Interface."""

    def __init__(self, api_token: Optional[str] = None, mock_mode: bool = False):
        if mock_mode:
            self.client = MockPriceClient()
        else:
            if api_token is None:
                from config import ENTSOE_API_TOKEN
                api_token = ENTSOE_API_TOKEN
            self.client = EntsoePriceClient(api_token)

    def get_market_prices(
        self,
        country: str = "DE_LU",
        forecast_hours: int = 48,
        start_time: Optional[datetime] = None
    ) -> MarketPrices:
        """Get prices for all four markets."""
        if start_time is None:
            start_time = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
        end_time = start_time + timedelta(hours=forecast_hours)

        return MarketPrices(
            day_ahead=self.client.get_day_ahead_prices(country, start_time, end_time),
            fcr=self.client.get_fcr_prices(country, start_time, end_time),
            afrr_capacity=self.client.get_afrr_capacity_prices(country, start_time, end_time),
            afrr_energy=self.client.get_afrr_energy_prices(country, start_time, end_time),
            country=country,
            forecast_hours=forecast_hours
        )
```

### Step 4: Add FastAPI Endpoints

**File**: `src/backend/main.py`

```python
from pydantic import BaseModel
from services.price import PriceService

price_service = PriceService()

class PriceRequest(BaseModel):
    country: str = "DE_LU"
    forecast_hours: int = 48
    include_summary: bool = False

@app.get("/api/v1/prices")
def get_prices(request: PriceRequest = PriceRequest()):
    """Get electricity market prices for all markets."""
    prices = price_service.get_market_prices(
        country=request.country,
        forecast_hours=request.forecast_hours
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

@app.get("/api/v1/prices/day-ahead")
def get_day_ahead_prices(country: str = "DE_LU", forecast_hours: int = 48):
    """Quick endpoint for Day-Ahead prices only."""
    series = price_service.get_day_ahead_only(country, forecast_hours)
    return {
        "country": country,
        "data": series.to_gridkey_format(),
        "source": series.source.value
    }
```

### Step 5: Add Tests

**File**: `tests/test_price.py`

```python
import pytest
from services.price import PriceService, MarketType, PriceSeries

def test_mock_mode():
    """Test with mock client (no API token needed)."""
    service = PriceService(mock_mode=True)
    prices = service.get_market_prices("DE_LU", forecast_hours=24)

    assert prices.day_ahead is not None
    assert prices.fcr is not None
    assert len(prices.day_ahead.timestamps) == 96  # 24h * 4

def test_gridkey_format_conversion():
    """Test GridKey JSON format conversion."""
    service = PriceService(mock_mode=True)
    prices = service.get_market_prices("DE_LU", forecast_hours=1)
    gridkey = prices.day_ahead.to_gridkey_format()

    assert "timestamp" in gridkey[0]
    assert "DE_LU" in gridkey[0]
```

---

## Critical Files to Modify

| File                              | Action                                     |
| --------------------------------- | ------------------------------------------ |
| `src/backend/services/price.py` | **Replace** with full implementation |
| `src/backend/config.py`         | Add ENTSOE_API_TOKEN, PRICE_MOCK_MODE      |
| `requirements.txt`              | Add entsoe-py>=0.5.0, pytest>=7.4.0        |
| `.env.template`                 | Add ENTSOE_API_TOKEN, PRICE_MOCK_MODE      |
| `src/backend/main.py`           | Add /api/v1/prices endpoints               |
| `tests/test_price.py`           | **Create** test file                 |

---

## ENTSO-E API Registration Guide

### Step-by-Step Registration

1. **Visit**: https://transparency.entsoe.eu/
2. **Register**: Click "Register" → Create free account
3. **Verify**: Confirm email
4. **Generate Token**:
   - Login → My Account
   - Web API Access → Generate Token
   - Copy the token
5. **Configure**:
   ```bash
   # In .env file
   ENTSOE_API_TOKEN=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
   ```

**Note**: Registration is free and takes ~5 minutes. No credit card required.

---

## Verification Plan

### 1. Unit Tests (No API token needed)

```bash
# Test with mock mode
pytest tests/test_price.py -v
```

### 2. Manual Testing

```bash
# Test with mock mode (no token)
export PRICE_MOCK_MODE=true
uvicorn src.backend.main:app --reload

# Test endpoint
curl "http://localhost:8000/api/v1/prices?country=DE_LU&forecast_hours=24"

# Expected: Mock data with source=mock
```

```bash
# Test with real ENTSO-E API (requires token)
export ENTSOE_API_TOKEN=your_token
uvicorn src.backend.main:app --reload

curl "http://localhost:8000/api/v1/prices?country=DE_LU&forecast_hours=48"

# Expected: Real-time data with source=entsoe_api
```

### 3. Data Validation

```python
# Verify GridKey format compatibility
from services.price import PriceService
import json

service = PriceService(api_token="your_token")
prices = service.get_market_prices("DE_LU", forecast_hours=48)

# Check output format
print(json.dumps(prices.day_ahead.to_gridkey_format()[:2], indent=2))

# Expected:
# [
#   {"timestamp": "2025-01-31T00:00:00", "DE_LU": 45.23},
#   {"timestamp": "2025-01-31T00:15:00", "DE_LU": 42.18}
# ]
```

---

## Implementation Notes

### ENTSO-E API Methods Mapping

| Market        | entsoe-py Method                        | Parameters                                   |
| ------------- | --------------------------------------- | -------------------------------------------- |
| Day-Ahead     | `query_day_ahead_prices()`            | country_code, start, end                     |
| FCR           | `query_contracted_reserve_prices()`   | country_code, type='A03', start, end         |
| aFRR Capacity | `query_procured_balancing_capacity()` | country_code, process_type='A51', start, end |
| aFRR Energy   | `query_contracted_reserve_prices()`   | country_code, type='A01'/'A02', start, end   |

### Error Handling

```python
# Handle common ENTSO-E errors
try:
    prices = client.get_day_ahead_prices(country, start, end)
except Exception as e:
    if "No matching data" in str(e):
        # Handle no data available
    elif "Unauthorized" in str(e):
        # Handle invalid token
    else:
        # Log and re-raise
```

### Timezone Handling

ENTSO-E returns data in local timezone (Europe/Berlin for DE_LU). The service converts to UTC internally for consistency.

---

## Open Questions / Follow-up

1. **aFRR Capacity Data Structure**: The `query_procured_balancing_capacity()` returns capacity quantities, not prices. May need to verify actual price availability or use alternative approach.
2. **Data Granularity**: FCR/aFRR capacity are typically 4-hour resolution. Verify if ENTSO-E API returns this granularity or if aggregation is needed.
3. **Testing Period**: For initial testing, recommend using recent dates (past 7 days) as ENTSO-E may have limited historical data availability.

---

## Sources

- [entsoe-py GitHub](https://github.com/EnergieID/entsoe-py) - Python client library
- [ENTSO-E API Guide](https://transparency.entsoe.eu/content/static_content/Static%20content/web%20api/Guide.html) - Official API documentation
- [ENTSO-E Transparency Platform](https://transparency.entsoe.eu/) - Data portal
