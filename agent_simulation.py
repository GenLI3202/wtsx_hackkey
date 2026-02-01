
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
    
    # Helper to extract numeric values from Price Service response items
    def extract_price_value(item, key_type, country="DE_LU"):
        # item is like {"timestamp": "...", "DE_LU": 123.4} or {"DE_Pos": 5.5, ...}
        if isinstance(item, (int, float)): return float(item)
        if not isinstance(item, dict): return 0.0
        
        # 1. Try exact country key (e.g. "DE_LU")
        if country in item: return float(item[country])
        
        # 2. Try generic keys based on type
        if key_type == "fcr":
            # FCR often uses "DE" or just "price"
            for k in ["DE", "AT", "price", "value"]:
                if k in item: return float(item[k])
                
        if "afrr" in key_type:
            # aFRR Capacity often has "DE_Pos"/"DE_Neg"
            # We need to know if we want pos or neg
            suffix = "_Pos" if "pos" in key_type else "_Neg"
            # Try constructing key
            # Assuming country code prefix "DE" from "DE_LU"
            c_code = country.split("_")[0] # "DE"
            target_key = f"{c_code}{suffix}"
            if target_key in item: return float(item[target_key])
            
            # Fallback for aFRR Energy which might be just "DE_LU" if separated list
            if country in item: return float(item[country])

        # 3. Fallback: return first float value found that isn't timestamp
        for k, v in item.items():
            if k != "timestamp" and isinstance(v, (int, float)):
                return float(v)
        return 0.0

    def get_list(source, key, target_len, key_type=""):
        data = source.get(key, [])
        if not data: return [0.0] * target_len
        
        # Extract values from dicts if necessary
        clean_data = []
        for item in data:
            clean_data.append(extract_price_value(item, key_type, "DE_LU"))
            
        # Pad/Slice
        if len(clean_data) < target_len:
            return clean_data + [clean_data[-1]] * (target_len - len(clean_data))
        return clean_data[:target_len]
    
    # 4-hour block steps
    BLOCK_STEPS = 3
    
    market_prices = {
        "day_ahead": get_list(price_data, "day_ahead", TARGET_STEPS, "day_ahead"),
        "fcr": get_list(price_data, "fcr", BLOCK_STEPS, "fcr"),
        "afrr_capacity_pos": get_list(price_data, "afrr_capacity", BLOCK_STEPS, "afrr_capacity_pos"),
        "afrr_capacity_neg": get_list(price_data, "afrr_capacity", BLOCK_STEPS, "afrr_capacity_neg")
    }

    # Special handling for aFRR Energy 
    # Price Service returns `afrr_energy` as a list of dicts.
    # Optimizer needs `afrr_energy_pos` and `afrr_energy_neg`.
    # Based on error logs, `afrr_energy` might not be in the top level if PriceService was updated?
    # Wait, the error logs didn't show `afrr_energy` validation error, so maybe it was missing or nil?
    # Let's check keys again. `price_data` usually matches the Response Model in `main.py`.
    # `main.py` -> `afrr_energy` key.
    
    afrr_e_data = price_data.get("afrr_energy", [])
    # If aFRR energy is single list of dicts, we use it for both pos/neg (symmetric assumption)
    # OR it might have Pos/Neg keys inside? 
    # Usually Energy prices are direction specific but simple PriceService might return one.
    # Let's clean it.
    
    clean_afrr_e = []
    if afrr_e_data:
        # Use get_list logic manually
        # Assuming "DE_LU" key for energy price
        clean_afrr_e = get_list(price_data, "afrr_energy", TARGET_STEPS, "afrr_energy")
    else:
        clean_afrr_e = [0.0] * TARGET_STEPS
        
    market_prices["afrr_energy_pos"] = clean_afrr_e
    market_prices["afrr_energy_neg"] = [x * 0.8 for x in clean_afrr_e] # Simulate lower neg price if needed, or just same

    # Fix: Renewable Gen
    gen_forecast = renewable_gen # calculated above
    # Ensure length matches
    if len(gen_forecast) < TARGET_STEPS:
         gen_forecast += [0.0] * (TARGET_STEPS - len(gen_forecast))
    gen_forecast = gen_forecast[:TARGET_STEPS]

    payload = {
        "location": "Munich",
        "country": "DE_LU",
        "model_type": "III-renew",
        "c_rate": 0.5,
        "alpha": 1.0,
        "market_prices": market_prices,
        "renewable_generation": gen_forecast,
        "time_horizon_hours": 12
    }

    # 4. Call Optimizer
    print("\n4️⃣  Calling Optimizer Engine...")
    try:
        o_resp = requests.post(f"{BASE_URL}/api/v1/optimize", json=payload)
        if o_resp.status_code != 200:
            print(f"   ❌ Optimizer Error {o_resp.status_code}: {o_resp.text}")
            return
            
        result = o_resp.json()
        print("\n✅  OPTIMIZATION SUCCESSFUL!")
        print(f"    • Total Profit: €{result['summary']['net_profit_eur']:.2f}")
        print(f"    • Revenue:      €{result['summary']['total_revenue_eur']:.2f}")
        print(f"    • Cycles:       {result['summary'].get('battery_cycles', 'N/A')}")
        
        print("\nSCHEDULE HIGHLIGHTS (First 4 hours):")
        print(f"{'Time':<20} | {'Action':<10} | {'Power (kW)':<10} | {'SOC (%)':<8}")
        print("-" * 60)
        for entry in result['schedule'][:16]:
            ts = entry['timestamp'].replace('T', ' ')
            print(f"{ts:<20} | {entry['action']:<10} | {entry['power_kw']:<10.2f} | {entry['soc_pct']:<8}")
            
    except Exception as e:
        print(f"   ❌ Optimizer Call Failed: {e}")

if __name__ == "__main__":
    run_simulation()
