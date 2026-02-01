
import requests
import json
import sys

BASE_URL = "http://localhost:8000"

def run_simulation():
    print("🤖 Agent: Starting 12-hour BESS Schedule Planning...")

    # 1. Get Weather (12 hours)
    print("\n1️⃣  Fetching Weather Forecast (Munich)...")
    try:
        w_resp = requests.get(f"{BASE_URL}/weather/forecast", params={"location": "Munich", "hours": 12})
        w_resp.raise_for_status()
        weather_data = w_resp.json()
        
        # Extract total output (PV + Wind)
        # timeline is list of objects with 'total_output_kw'
        renewable_gen = [item['total_output_kw'] for item in weather_data['timeline']]
        print(f"   ✅ Got {len(renewable_gen)} data points from Weather Service.")
    except Exception as e:
        print(f"   ❌ Weather Service Failed: {e}")
        return

    # 2. Get Prices (Requesting 48h to be safe, then slicing)
    print("\n2️⃣  Fetching Market Prices (DE_LU)...")
    try:
        # Note: Price endpoint might return more data than requested due to fixed horizons
        p_resp = requests.get(f"{BASE_URL}/price/forecast", params={"country": "DE_LU", "hours": 24})
        p_resp.raise_for_status()
        price_data = p_resp.json()
        print(f"   ✅ Got Price Service Response.")
    except Exception as e:
        print(f"   ❌ Price Service Failed: {e}")
        return

    # 3. Construct Optimization Payload
    print("\n3️⃣  Orchestrating Optimization Request...")
    
    # Slice/Pad data to match 12 hours (48 steps of 15-min)
    TARGET_STEPS = 48 # 12 hours * 4
    
    # Process Prices
    # Price service response format check: 'day_ahead' is typically a list or dict
    # Based on recent edits, PriceService returns a Pydantic model, JSONified. 
    # Let's assume standard simple lists from the `to_gridkey_format` output in main.py
    
    def get_list(source, key, target_len):
        data = source.get(key, [])
        if not data: return [0.0] * target_len
        # If data is shorter, pad with last value; if longer, slice
        if len(data) < target_len:
            return data + [data[-1]] * (target_len - len(data))
        return data[:target_len]
    
    # 4-hour block steps = target_len / 16 (since 4 steps/hr * 4hr = 16 steps)
    # Actually block prices (FCR) are usually 4-hour blocks. 
    # 12 hours = 3 blocks.
    BLOCK_STEPS = 3
    
    # Debug Price Data Structure
    # print(f"DEBUG: Price Keys: {price_data.keys()}")
    # if 'afrr_energy' in price_data:
    #      print(f"DEBUG: afrr_energy type: {type(price_data['afrr_energy'])}")
    
    # Based on main.py `get_price_forecast`, it returns:
    # "afrr_energy": prices.afrr_energy.to_gridkey_format() 
    # to_gridkey_format likely returns a LIST of floats if it follows the old pattern, 
    # BUT if it returns a Pydantic object, `requests.json()` turns it into a dict.
    # Let's handle the dict case specifically for `afrr_energy`.
    
    # Price Service now returns flat arrays directly per Optimizer spec
    # No more complex extraction needed!
    
    # Check Price Service Response structure in log if needed
    # Should contain keys: "day_ahead", "fcr", "afrr_energy_pos", etc.
    
    def get_list(source, key, target_len):
        data = source.get(key, [])
        if not data: return [0.0] * target_len
        if len(data) < target_len:
            # Simple padding with last value
            return data + [data[-1]] * (target_len - len(data))
        return data[:target_len]
    
    # 4-hour block steps
    BLOCK_STEPS = 3
    
    market_prices = {
        "day_ahead": get_list(price_data, "day_ahead", TARGET_STEPS),
        "fcr": get_list(price_data, "fcr", BLOCK_STEPS),
        "afrr_capacity_pos": get_list(price_data, "afrr_capacity_pos", BLOCK_STEPS),
        "afrr_capacity_neg": get_list(price_data, "afrr_capacity_neg", BLOCK_STEPS),
        "afrr_energy_pos": get_list(price_data, "afrr_energy_pos", TARGET_STEPS),
        "afrr_energy_neg": get_list(price_data, "afrr_energy_neg", TARGET_STEPS)
    }

    # Remove manual aFRR Split logic as it's now handled by the API endpoint

    # Fix: Renewable Gen
    gen_forecast = renewable_gen # calculated above
    # Ensure length matches
    if len(gen_forecast) < TARGET_STEPS:
         gen_forecast += [0.0] * (TARGET_STEPS - len(gen_forecast))
    gen_forecast = gen_forecast[:TARGET_STEPS]

    payload = {
        "location": "Munich",
        "country": "DE_LU",
        "model_type": "II", # Switch to Model II for speed (Model III was timing out on 12h)
        "c_rate": 0.5,
        "alpha": 1.0,
        "market_prices": market_prices,
        "renewable_generation": gen_forecast,
        "time_horizon_hours": 4
    }

    # 4. Call Optimizer
    print("\n4️⃣  Calling Optimizer Engine...")
    try:
        o_resp = requests.post(f"{BASE_URL}/api/v1/optimize", json=payload)
        if o_resp.status_code != 200:
            print(f"   ❌ Optimizer Error {o_resp.status_code}: {o_resp.text}")
            return
            
        result = o_resp.json()
        
        # New API Format: {"status": "success", "data": { ... }}
        if result.get("status") == "success" and "data" in result:
            data = result["data"]
            print("\n✅ OPTIMIZATION SUCCESSFUL\n")
            print(f"💰 Net Profit: {data.get('net_profit', 0):.2f} EUR")
            print(f"📉 Degradation Cost: {data.get('degradation_cost', 0):.2f} EUR")
            
            schedule = data.get("schedule", [])
            print(f"\n📅 Schedule ({len(schedule)} steps):")
            print("-" * 60)
            print(f"{'Time':<20} | {'Action':<10} | {'Power (kW)':<12} | {'SOC %':<8}")
            print("-" * 60)
            
            for step in schedule:
                # New format: flat dict
                ts = step.get("timestamp", "").replace("T", " ")[:16]
                action = step.get("action", "unknown")
                power = step.get("power_kw", 0.0)
                soc = step.get("soc_after", 0.0) * 100 
                
                print(f"{ts:<20} | {action:<10} | {power:<12.1f} | {soc:<8.1f}")
        else:
             print(f"\n❌ Optimization Failed (Logic Error): {result}")

    except Exception as e:
        print(f"   ❌ Optimizer Call Failed: {e}")

if __name__ == "__main__":
    run_simulation()
