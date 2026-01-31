"""
Module 5: Battery Configuration
电池储能系统静态参数配置

提供电池的物理参数、效率参数和经济参数配置。
原 Module C 简化为配置文件方式。
"""

# ==============================================================================
# 电池配置 - Huawei LUNA2000-4.5MWh
# ==============================================================================

BATTERY_CONFIG = {
    # ========== 设备信息 ==========
    "model": "Huawei LUNA2000-4.5MWh",
    "manufacturer": "Huawei Digital Power",
    "location": "DE_LU",  # 德国-卢森堡竞价区
    
    # ========== 容量参数 ==========
    "capacity_kwh": 4472,           # 额定容量 (kWh)
    "c_rate": 0.5,                  # C-rate (可选: 0.25, 0.33, 0.5)
    "max_power_kw": 2236,           # 最大功率 = capacity_kwh × c_rate
    "min_soc": 0.1,                 # 最小 SOC (10%)
    "max_soc": 0.9,                 # 最大 SOC (90%)
    
    # ========== 效率参数 ==========
    "efficiency": 0.95,             # 往返效率 (Round-trip efficiency)
    "charge_efficiency": 0.975,     # 充电效率 (sqrt of 0.95)
    "discharge_efficiency": 0.975,  # 放电效率 (sqrt of 0.95)
    "self_discharge_rate": 0.001,   # 自放电率 (每小时 0.1%)
    
    # ========== 初始状态 (演示用默认值) ==========
    "initial_soc": 0.5,             # 初始 SOC (50%)
    "soh": 1.0,                     # 健康状态 (100%)
    
    # ========== 经济参数 ==========
    "investment_cost_per_kwh": 200, # 投资成本 (€/kWh)
    "total_investment": 894400,     # 总投资 = 4472 × 200 = €894,400
    "lifespan_years": 15,           # 设计寿命 (年)
    "degradation_cost_per_cycle": 0.5,  # 每循环退化成本 (€/cycle)
}


# ==============================================================================
# C-Rate 配置选项
# ==============================================================================

C_RATE_OPTIONS = {
    0.25: {
        "max_power_kw": 1118,       # 4472 × 0.25
        "description": "保守模式 - 延长电池寿命",
    },
    0.33: {
        "max_power_kw": 1476,       # 4472 × 0.33
        "description": "平衡模式 - 功率与寿命平衡",
    },
    0.5: {
        "max_power_kw": 2236,       # 4472 × 0.5
        "description": "高性能模式 - 最大收益潜力",
    },
}


# ==============================================================================
# 辅助函数
# ==============================================================================

def get_battery_config(c_rate: float = 0.5) -> dict:
    """
    获取电池配置，可指定 C-rate
    
    Args:
        c_rate: C-rate 值 (0.25, 0.33, 0.5)
    
    Returns:
        更新后的电池配置字典
    """
    config = BATTERY_CONFIG.copy()
    
    if c_rate in C_RATE_OPTIONS:
        config["c_rate"] = c_rate
        config["max_power_kw"] = C_RATE_OPTIONS[c_rate]["max_power_kw"]
    
    return config


def calculate_max_power(capacity_kwh: float, c_rate: float) -> float:
    """计算最大功率"""
    return capacity_kwh * c_rate


def get_config_summary() -> str:
    """获取配置摘要 (供 Agent 使用)"""
    cfg = BATTERY_CONFIG
    return f"""
Battery Configuration Summary:
- Model: {cfg['model']}
- Capacity: {cfg['capacity_kwh']} kWh
- Max Power: {cfg['max_power_kw']} kW (C-rate: {cfg['c_rate']})
- Efficiency: {cfg['efficiency'] * 100}%
- Initial SOC: {cfg['initial_soc'] * 100}%
- SOC Range: {cfg['min_soc'] * 100}% - {cfg['max_soc'] * 100}%
"""


# ==============================================================================
# 验证配置
# ==============================================================================

if __name__ == "__main__":
    print(get_config_summary())
    print("\nC-Rate Options:")
    for rate, info in C_RATE_OPTIONS.items():
        print(f"  {rate}: {info['max_power_kw']} kW - {info['description']}")
