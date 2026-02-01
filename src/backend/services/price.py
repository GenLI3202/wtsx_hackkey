"""
Module B: Price Service
电力市场价格数据获取

Classes:
- PriceClient: ENTSO-E API 客户端 (获取市场价格)
- PriceData: 市场价格数据模型
- PriceForecastFallback: 价格预测回退机制 (历史数据)
- PriceService: 对外统一接口
"""

import math
import random
import requests
import datetime
from datetime import timezone, timedelta
from typing import List, Optional, Dict, Union
from pydantic import BaseModel, Field
from enum import Enum
from dataclasses import dataclass, field


# ==============================================================================
# Enums
# ==============================================================================

class MarketType(Enum):
    """市场类型"""
    DAY_AHEAD = "day_ahead"
    FCR = "fcr"
    AFRR_CAPACITY = "afrr_capacity"
    AFRR_ENERGY = "afrr_energy"


class CountryCode(Enum):
    """支持的国家/竞价区代码"""
    DE_LU = "DE_LU"  # Germany + Luxembourg
    AT = "AT"        # Austria
    CH = "CH"        # Switzerland
    HU = "HU"        # Hungary
    CZ = "CZ"        # Czech Republic


# ==============================================================================
# Data Models
# ==============================================================================

class PriceData(BaseModel):
    '''
    市场价格数据模型
  
    - Purpose: 结构化存储逐时段价格数据
    - Fields:
        - timestamps: List[datetime]
        - prices: Dict[str, List[float]]  # {country: [prices]}
        - market_type: MarketType
        - resolution_minutes: int
    - Notes: 保持与原 GridKey 数据格式兼容
    '''
    timestamps: List[datetime.datetime]
    prices: Dict[str, List[float]]  # e.g., {"DE_LU": [45.2, 48.1, ...], "AT": [...]}
    market_type: str  # day_ahead, fcr, afrr_capacity, afrr_energy
    resolution_minutes: int  # 15 for DA/aFRR_energy, 240 for FCR/aFRR_capacity
    unit: str = "EUR/MWh"  # or EUR/MW for capacity products

    def to_gridkey_format(self) -> List[Dict]:
        """
        转换为 GridKey 兼容的 JSON 格式
        
        Output format:
        [
            {"timestamp": "2024-01-01T00:00:00.000", "DE_LU": 39.91, "AT": 14.08, ...},
            {"timestamp": "2024-01-01T00:15:00.000", "DE_LU": -0.04, "AT": 14.08, ...}
        ]
        """
        result = []
        countries = list(self.prices.keys())
        
        for i, ts in enumerate(self.timestamps):
            entry = {"timestamp": ts.strftime("%Y-%m-%dT%H:%M:%S.000")}
            for country in countries:
                if i < len(self.prices[country]):
                    entry[country] = round(self.prices[country][i], 4)
            result.append(entry)
        
        return result


class MarketPrices(BaseModel):
    """
    四个市场的价格数据容器
    """
    day_ahead: Optional[PriceData] = None
    fcr: Optional[PriceData] = None
    afrr_capacity: Optional[PriceData] = None
    afrr_energy: Optional[PriceData] = None
    country: str = "DE_LU"
    forecast_hours: int = 48
    retrieved_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)


# ==============================================================================
# Price Client
# ==============================================================================

class PriceClient:
    '''
    电力市场价格数据获取客户端
  
    - Purpose: 调用 ENTSO-E Transparency API 获取市场价格
    - Input: 
        - country: 国家代码 (DE_LU)
        - market_type: 市场类型 (day_ahead, fcr, afrr_capacity, afrr_energy)
        - start_time, end_time: 时间范围
    - Output: PriceData 对象
    - Notes: 需要 ENTSO-E API Token；不同市场可能需要不同的 API endpoint
    '''
    
    # ENTSO-E Area Codes for bidding zones
    AREA_CODES = {
        "DE_LU": "10Y1001A1001A82H",  # Germany-Luxembourg
        "AT": "10YAT-APG------L",      # Austria
        "CH": "10YCH-SWISSGRIDZ",      # Switzerland
        "HU": "10YHU-MAVIR----U",      # Hungary
        "CZ": "10YCZ-CEPS-----N",      # Czech Republic
    }
    
    def __init__(self, api_token: Optional[str] = None):
        """
        初始化 ENTSO-E 客户端
        
        Args:
            api_token: ENTSO-E Transparency API token
        """
        self.api_token = api_token
        self.base_url = "https://web-api.tp.entsoe.eu/api"
        
        # 如果有 token，尝试使用 entsoe-py 库
        self._client = None
        if api_token:
            try:
                from entsoe import EntsoePandasClient
                self._client = EntsoePandasClient(api_key=api_token)
            except ImportError:
                print("Warning: entsoe-py not installed. Using direct API calls.")
    
    def get_prices(
        self, 
        country: str, 
        market_type: str, 
        start_time: datetime.datetime, 
        end_time: datetime.datetime
    ) -> PriceData:
        """
        获取指定市场的价格数据
        
        Args:
            country: 国家代码 (DE_LU, AT, CH, HU, CZ)
            market_type: 市场类型 (day_ahead, fcr, afrr_capacity, afrr_energy)
            start_time: 开始时间
            end_time: 结束时间
            
        Returns:
            PriceData 对象
        """
        if market_type == "day_ahead":
            return self._get_day_ahead_prices(country, start_time, end_time)
        elif market_type == "fcr":
            return self._get_fcr_prices(country, start_time, end_time)
        elif market_type == "afrr_capacity":
            return self._get_afrr_capacity_prices(country, start_time, end_time)
        elif market_type == "afrr_energy":
            return self._get_afrr_energy_prices(country, start_time, end_time)
        else:
            raise ValueError(f"Unknown market type: {market_type}")
    
    def _get_day_ahead_prices(
        self, 
        country: str, 
        start_time: datetime.datetime, 
        end_time: datetime.datetime
    ) -> PriceData:
        """
        获取 Day-Ahead 价格 (15分钟分辨率)
        
        优先使用 Energy-Charts API (免费，无需 Token)
        回退到 ENTSO-E API (需要 Token) 或模拟数据
        """
        # 尝试使用 Energy-Charts API (免费)
        try:
            return self._get_energy_charts_prices(country, start_time, end_time)
        except Exception as e:
            print(f"Energy-Charts API error: {e}")
        
        # 回退到 ENTSO-E (如果有 token)
        if self._client:
            try:
                import pandas as pd
                start = pd.Timestamp(start_time, tz='Europe/Berlin')
                end = pd.Timestamp(end_time, tz='Europe/Berlin')
                
                prices_series = self._client.query_day_ahead_prices(country, start=start, end=end)
                
                timestamps = prices_series.index.to_pydatetime().tolist()
                prices_list = prices_series.values.tolist()
                
                return PriceData(
                    timestamps=timestamps,
                    prices={country: prices_list},
                    market_type="day_ahead",
                    resolution_minutes=15,
                    unit="EUR/MWh"
                )
            except Exception as e:
                print(f"ENTSO-E API error: {e}. Falling back to mock data.")
        
        # Fallback: 生成模拟数据
        return self._generate_mock_da_prices(country, start_time, end_time)
    
    def _get_energy_charts_prices(
        self, 
        country: str, 
        start_time: datetime.datetime, 
        end_time: datetime.datetime
    ) -> PriceData:
        """
        使用 Energy-Charts API 获取 Day-Ahead 价格 (免费，无需 Token)
        
        API: https://api.energy-charts.info/price
        数据来源: Bundesnetzagentur | SMARD.de
        """
        # 映射国家代码到 bzn (bidding zone)
        bzn_map = {
            "DE_LU": "DE-LU",
            "DE": "DE-LU",
            "AT": "AT",
            "CH": "CH",
        }
        bzn = bzn_map.get(country, "DE-LU")
        
        # 格式化日期
        start_str = start_time.strftime("%Y-%m-%d")
        end_str = end_time.strftime("%Y-%m-%d")
        
        # 调用 API
        url = f"https://api.energy-charts.info/price?bzn={bzn}&start={start_str}&end={end_str}"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # 解析响应
        unix_seconds = data.get("unix_seconds", [])
        prices = data.get("price", [])
        
        if not unix_seconds or not prices:
            raise ValueError("No price data returned from Energy-Charts API")
        
        # 转换时间戳
        timestamps = [
            datetime.datetime.fromtimestamp(ts, tz=timezone.utc) 
            for ts in unix_seconds
        ]
        
        # 过滤到请求的时间范围
        filtered_timestamps = []
        filtered_prices = []
        for ts, price in zip(timestamps, prices):
            if start_time <= ts <= end_time and price is not None:
                filtered_timestamps.append(ts)
                filtered_prices.append(round(price, 2))
        
        return PriceData(
            timestamps=filtered_timestamps,
            prices={country: filtered_prices},
            market_type="day_ahead",
            resolution_minutes=15,
            unit="EUR/MWh"
        )
    
    def _get_fcr_prices(
        self, 
        country: str, 
        start_time: datetime.datetime, 
        end_time: datetime.datetime
    ) -> PriceData:
        """
        获取 FCR 价格 (4小时分辨率)
        
        FCR 价格来源: regelleistung.net 或 ENTSO-E
        """
        if self._client:
            try:
                import pandas as pd
                start = pd.Timestamp(start_time, tz='Europe/Berlin')
                end = pd.Timestamp(end_time, tz='Europe/Berlin')
                
                # FCR 使用 query_contracted_reserve_prices with type A03 (symmetric)
                prices_df = self._client.query_contracted_reserve_prices(
                    country_code=country.replace("_LU", ""),  # FCR uses DE, not DE_LU
                    type_marketagreement_type='A03',
                    start=start,
                    end=end
                )
                
                # 重采样到 4 小时
                prices_4h = prices_df.resample('4H').mean()
                
                return PriceData(
                    timestamps=prices_4h.index.to_pydatetime().tolist(),
                    prices={country.replace("_LU", ""): prices_4h.values.flatten().tolist()},
                    market_type="fcr",
                    resolution_minutes=240,
                    unit="EUR/MW"
                )
            except Exception as e:
                print(f"FCR API error: {e}. Falling back to mock data.")
        
        # Fallback: 生成模拟数据
        return self._generate_mock_fcr_prices(country, start_time, end_time)
    
    def _get_afrr_capacity_prices(
        self, 
        country: str, 
        start_time: datetime.datetime, 
        end_time: datetime.datetime
    ) -> PriceData:
        """
        获取 aFRR Capacity 价格 (4小时分辨率, Pos/Neg)
        """
        # aFRR Capacity 通常较难从 ENTSO-E 直接获取，使用模拟数据
        return self._generate_mock_afrr_capacity_prices(country, start_time, end_time)
    
    def _get_afrr_energy_prices(
        self, 
        country: str, 
        start_time: datetime.datetime, 
        end_time: datetime.datetime
    ) -> PriceData:
        """
        获取 aFRR Energy 价格 (15分钟分辨率, Pos/Neg)
        """
        # aFRR Energy 使用模拟数据
        return self._generate_mock_afrr_energy_prices(country, start_time, end_time)
    
    # ==========================================================================
    # Mock Data Generators (for testing without API token)
    # ==========================================================================
    
    def _generate_mock_da_prices(
        self, 
        country: str, 
        start_time: datetime.datetime, 
        end_time: datetime.datetime
    ) -> PriceData:
        """
        生成模拟的 Day-Ahead 价格
        
        模拟真实的日内价格波动：
        - 凌晨低谷 (€20-40)
        - 早高峰 (€60-90，8-10点)
        - 午间太阳能低价 (€30-50)
        - 晚高峰 (€70-120，18-21点)
        """
        num_points = int((end_time - start_time).total_seconds() / 900)  # 15分钟间隔
        timestamps = [start_time + timedelta(minutes=15*i) for i in range(num_points)]
        
        prices = []
        for ts in timestamps:
            hour = ts.hour
            
            # 基础价格曲线 (典型的德国DA模式)
            if 0 <= hour < 6:
                # 夜间低谷
                base_price = 25 + 10 * math.sin(hour * math.pi / 6)
            elif 6 <= hour < 10:
                # 早高峰
                base_price = 50 + 30 * math.sin((hour - 6) * math.pi / 4)
            elif 10 <= hour < 14:
                # 午间太阳能压低
                base_price = 40 - 15 * math.sin((hour - 10) * math.pi / 4)
            elif 14 <= hour < 18:
                # 下午回升
                base_price = 45 + 20 * math.sin((hour - 14) * math.pi / 4)
            elif 18 <= hour < 22:
                # 晚高峰
                base_price = 70 + 40 * math.sin((hour - 18) * math.pi / 4)
            else:
                # 夜间回落
                base_price = 35 - 10 * ((hour - 22) / 2)
            
            # 添加随机波动
            noise = random.gauss(0, 5)
            price = max(-50, base_price + noise)  # 允许负价格
            prices.append(round(price, 2))
        
        return PriceData(
            timestamps=timestamps,
            prices={country: prices},
            market_type="day_ahead",
            resolution_minutes=15,
            unit="EUR/MWh"
        )
    
    def _generate_mock_fcr_prices(
        self, 
        country: str, 
        start_time: datetime.datetime, 
        end_time: datetime.datetime
    ) -> PriceData:
        """
        生成模拟的 FCR 价格 (4小时分辨率)
        
        FCR 价格相对稳定，通常在 €60-150/MW 范围
        """
        num_points = int((end_time - start_time).total_seconds() / 14400)  # 4小时间隔
        timestamps = [start_time + timedelta(hours=4*i) for i in range(num_points)]
        
        prices = []
        for i, ts in enumerate(timestamps):
            # 基础价格 + 日内变化
            block = (ts.hour // 4)  # 0-5 表示一天中的6个4小时块
            
            # 典型 FCR 价格模式
            base_prices = [110, 95, 75, 85, 100, 120]  # 按4小时块
            base_price = base_prices[block] if block < len(base_prices) else 90
            
            noise = random.gauss(0, 10)
            price = max(0, base_price + noise)
            prices.append(round(price, 2))
        
        # 简化：只返回 DE
        country_key = country.replace("_LU", "")
        
        return PriceData(
            timestamps=timestamps,
            prices={country_key: prices},
            market_type="fcr",
            resolution_minutes=240,
            unit="EUR/MW"
        )
    
    def _generate_mock_afrr_capacity_prices(
        self, 
        country: str, 
        start_time: datetime.datetime, 
        end_time: datetime.datetime
    ) -> PriceData:
        """
        生成模拟的 aFRR Capacity 价格 (4小时分辨率, Pos/Neg)
        """
        num_points = int((end_time - start_time).total_seconds() / 14400)  # 4小时间隔
        timestamps = [start_time + timedelta(hours=4*i) for i in range(num_points)]
        
        prices_pos = []
        prices_neg = []
        
        for ts in timestamps:
            # aFRR Capacity 价格通常较低
            base_pos = 8 + random.gauss(0, 3)
            base_neg = 12 + random.gauss(0, 4)
            
            prices_pos.append(round(max(0, base_pos), 2))
            prices_neg.append(round(max(0, base_neg), 2))
        
        country_key = country.replace("_LU", "")
        
        return PriceData(
            timestamps=timestamps,
            prices={
                f"{country_key}_Pos": prices_pos,
                f"{country_key}_Neg": prices_neg
            },
            market_type="afrr_capacity",
            resolution_minutes=240,
            unit="EUR/MW"
        )
    
    def _generate_mock_afrr_energy_prices(
        self, 
        country: str, 
        start_time: datetime.datetime, 
        end_time: datetime.datetime
    ) -> PriceData:
        """
        生成模拟的 aFRR Energy 价格 (15分钟分辨率, Pos/Neg)
        """
        num_points = int((end_time - start_time).total_seconds() / 900)  # 15分钟间隔
        timestamps = [start_time + timedelta(minutes=15*i) for i in range(num_points)]
        
        prices_pos = []
        prices_neg = []
        
        for ts in timestamps:
            # aFRR Energy 价格波动较大
            hour = ts.hour
            
            # 基础价格跟随 DA 趋势，但波动更大
            if 0 <= hour < 6:
                base = 30
            elif 18 <= hour < 22:
                base = 80
            else:
                base = 50
            
            pos_price = base + random.gauss(0, 20)
            neg_price = base * 0.6 + random.gauss(0, 15)
            
            prices_pos.append(round(max(0, pos_price), 4))
            prices_neg.append(round(max(0, neg_price), 4))
        
        country_key = country.replace("_LU", "")
        
        return PriceData(
            timestamps=timestamps,
            prices={
                f"{country_key}_Pos": prices_pos,
                f"{country_key}_Neg": prices_neg
            },
            market_type="afrr_energy",
            resolution_minutes=15,
            unit="EUR/MWh"
        )


# ==============================================================================
# Price Forecast Fallback
# ==============================================================================

class PriceForecastFallback:
    '''
    价格预测回退机制
  
    - Purpose: 当实时 API 不可用时，使用 Regelleistung 历史数据
    - Input: country, market_type, target_date
    - Output: PriceData（基于本地 XLSX 数据）
    - Notes: 优先使用 regelleistung.net 下载的真实数据，无数据时回退到模拟
    '''
    
    def __init__(self, data_dir: str = None):
        self.regelleistung_loader = None
        # 延迟导入避免循环依赖
        try:
            from services.regelleistung_loader import RegelleistungLoader
            self.regelleistung_loader = RegelleistungLoader(data_dir)
        except ImportError:
            print("Warning: RegelleistungLoader not available, using mock data")
    
    def get_fallback_prices(
        self, 
        country: str, 
        market_type: str, 
        target_date: datetime.datetime
    ) -> PriceData:
        """
        获取回退价格数据
        
        策略：
        1. 优先从 Regelleistung XLSX 文件加载真实数据
        2. 无数据时使用最近可用日期的数据
        3. 完全无数据时回退到模拟数据
        """
        if self.regelleistung_loader is not None:
            date = target_date.date() if isinstance(target_date, datetime.datetime) else target_date
            
            # 获取可用日期
            available_dates = self.regelleistung_loader.list_available_dates()
            
            # 如果请求日期有数据，直接使用
            if date in available_dates:
                data_date = date
            elif available_dates:
                # 使用最近的可用日期
                data_date = max(available_dates)
                print(f"No data for {date}, using {data_date}")
            else:
                data_date = None
            
            if data_date is not None:
                try:
                    prices = self.regelleistung_loader.load_all_prices(data_date)
                    ps_format = self.regelleistung_loader.to_price_service_format(prices)
                    
                    # 根据 market_type 返回对应数据
                    if market_type == "fcr" and ps_format['fcr']:
                        return self._convert_to_pricedata(
                            ps_format['fcr'], market_type, country, 240, "EUR/MW"
                        )
                    elif market_type == "afrr_capacity" and ps_format['afrr_capacity']:
                        return self._convert_to_pricedata(
                            ps_format['afrr_capacity'], market_type, country, 240, "EUR/MW"
                        )
                    elif market_type == "afrr_energy" and ps_format['afrr_energy']:
                        return self._convert_to_pricedata(
                            ps_format['afrr_energy'], market_type, country, 15, "EUR/MWh"
                        )
                except Exception as e:
                    print(f"Error loading Regelleistung data: {e}")
        
        # 回退到模拟数据
        mock_client = PriceClient()
        end_time = target_date + timedelta(hours=48)
        return mock_client.get_prices(country, market_type, target_date, end_time)
    
    def _convert_to_pricedata(
        self, 
        data: List[Dict], 
        market_type: str, 
        country: str,
        resolution_minutes: int,
        unit: str
    ) -> PriceData:
        """将 Regelleistung 格式转换为 PriceData"""
        timestamps = []
        prices_dict = {}
        
        for record in data:
            ts = datetime.datetime.fromisoformat(record['timestamp'].replace('.000', ''))
            timestamps.append(ts)
            
            for key, value in record.items():
                if key != 'timestamp':
                    if key not in prices_dict:
                        prices_dict[key] = []
                    prices_dict[key].append(value)
        
        return PriceData(
            timestamps=timestamps,
            prices=prices_dict,
            market_type=market_type,
            resolution_minutes=resolution_minutes,
            unit=unit
        )


# ==============================================================================
# Price Service (Main Interface)
# ==============================================================================

class PriceService:
    '''
    Price 模块对外统一接口
  
    - Purpose: 封装完整流程，供 Optimizer 和 Agent 调用
    - Input: country, forecast_hours
    - Output: MarketPrices 对象（含四个市场的价格数据）
    - Notes: 优先使用实时 API，失败时回退到历史数据
    '''
    
    def __init__(self, api_token: Optional[str] = None):
        """
        初始化 Price Service
        
        Args:
            api_token: ENTSO-E API token (可选，无 token 时使用模拟数据)
        """
        if api_token is None:
            try:
                from config import ENTSOE_API_TOKEN
                api_token = ENTSOE_API_TOKEN
            except ImportError:
                pass
        
        self.client = PriceClient(api_token)
        self.fallback = PriceForecastFallback()
    
    def get_market_prices(
        self, 
        country: str = "DE_LU", 
        forecast_hours: int = 48
    ) -> MarketPrices:
        """
        获取四个市场的完整价格数据
        
        Args:
            country: 国家/竞价区代码
            forecast_hours: 预测小时数
            
        Returns:
            MarketPrices 对象
        """
        start_time = datetime.datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
        end_time = start_time + timedelta(hours=forecast_hours)
        
        # 获取四个市场的价格
        try:
            da = self.client.get_prices(country, "day_ahead", start_time, end_time)
        except Exception as e:
            print(f"DA price error: {e}")
            da = None
        
        try:
            fcr = self.client.get_prices(country, "fcr", start_time, end_time)
        except Exception as e:
            print(f"FCR price error: {e}")
            fcr = None
        
        try:
            afrr_cap = self.client.get_prices(country, "afrr_capacity", start_time, end_time)
        except Exception as e:
            print(f"aFRR Capacity price error: {e}")
            afrr_cap = None
        
        try:
            afrr_eng = self.client.get_prices(country, "afrr_energy", start_time, end_time)
        except Exception as e:
            print(f"aFRR Energy price error: {e}")
            afrr_eng = None
        
        return MarketPrices(
            day_ahead=da,
            fcr=fcr,
            afrr_capacity=afrr_cap,
            afrr_energy=afrr_eng,
            country=country,
            forecast_hours=forecast_hours,
            retrieved_at=datetime.datetime.now(timezone.utc)
        )
