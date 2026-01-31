"""
Module A: Weather Service
气象数据获取与可再生能源发电预测

Classes:
- WeatherClient: OpenWeatherMap API 客户端
- WeatherForecast: 气象预报数据模型
- PVForecaster: 光伏发电预测器
- WindForecaster: 风电发电预测器
- WeatherService: 对外统一接口
"""

import math
import requests
import datetime
from datetime import timezone
from typing import List, Optional, Union, Tuple
from pydantic import BaseModel, Field


# ==============================================================================
# Data Models
# ==============================================================================

class AssetConfig(BaseModel):
    """
    资产配置参数 - 允许在请求时动态调整物理参数
    """
    # PV Config
    pv_capacity_kw: float = Field(10.0, description="光伏装机容量")
    pv_tilt: float = Field(30.0, description="光伏板倾角")
    pv_azimuth: float = Field(180.0, description="光伏板朝向 (180=South)")
    pv_efficiency: float = Field(0.20, description="光伏组件效率")
    
    # Wind Config
    wind_capacity_kw: float = Field(50.0, description="风机额定功率")
    wind_cut_in_speed: float = Field(3.0, description="切入风速 m/s")
    wind_rated_speed: float = Field(12.0, description="额定风速 m/s")
    wind_cut_out_speed: float = Field(25.0, description="切出风速 m/s")


class WeatherForecast(BaseModel):
    '''
    气象预报数据模型 (符合 Architecture 文档定义的列式结构)
  
    - Purpose: 结构化存储逐小时气象数据
    - Notes: 时间分辨率应与 Optimizer 匹配（15分钟或1小时）
    '''
    timestamps: List[datetime.datetime]
    solar_irradiance: List[float]  # W/m²
    wind_speed: List[float]        # m/s
    wind_direction: List[float]    # degrees
    temperature: List[float]       # °C
    cloud_cover: List[float]       # %
    humidity: List[float]          # %


class GenerationPoint(BaseModel):
    """单点发电预测 (1小时分辨率)"""
    timestamp: datetime.datetime
    pv_output_kw: float   # 光伏产出
    wind_output_kw: float # 风电产出
    total_output_kw: float


class GenerationForecast(BaseModel):
    """完整的发电预测序列"""
    location: str
    generated_at: datetime.datetime
    timeline: List[GenerationPoint]


# ==============================================================================
# Physics Engine
# ==============================================================================

class PhysicsEngine:
    """物理计算引擎 - 辐照度与发电量计算"""
    
    @staticmethod
    def calculate_irradiance(lat: float, dt: datetime.datetime, cloud_cover: int) -> float:
        """
        估算太阳辐射 (W/m^2)
        基于: 纬度、时间、云量
        """
        # 1. 计算一年中的第几天 (Day of Year)
        doy = dt.timetuple().tm_yday
        
        # 2. 计算太阳赤纬角 (Declination Angle)
        declination = 23.45 * math.sin(math.radians(360/365 * (doy - 81)))
        
        # 3. 计算时角 (Hour Angle)
        hour_offset = dt.hour + (dt.minute / 60) - 12
        hour_angle = 15 * hour_offset
        
        # 4. 计算太阳高度角 (Solar Elevation Angle)
        lat_rad = math.radians(lat)
        dec_rad = math.radians(declination)
        ha_rad = math.radians(hour_angle)
        
        sin_elevation = math.sin(lat_rad) * math.sin(dec_rad) + \
                        math.cos(lat_rad) * math.cos(dec_rad) * math.cos(ha_rad)
        
        elevation = math.degrees(math.asin(max(0, sin_elevation)))
        
        # 5. 如果太阳在地平线以下，辐射为0
        if elevation <= 0:
            return 0.0
            
        # 6. 晴天理论辐射 (Clear Sky Radiation)
        clear_sky_rad = 1000 * math.sin(math.radians(elevation))
        
        # 7. 云量衰减 (Cloud Attenuation)
        cloud_factor = 1 - (0.75 * (cloud_cover / 100)**3)
        
        return max(0, clear_sky_rad * cloud_factor)

    @staticmethod
    def calculate_pv_output(irradiance: float, capacity_kw: float = 5.0, efficiency: float = 0.9) -> float:
        """
        计算光伏产出 (kW)
        Formula: Output = Irradiance(kW/m2) * Capacity * Efficiency
        """
        sun_units = irradiance / 1000.0
        output = sun_units * capacity_kw * efficiency
        return round(output, 3)

    @staticmethod
    def calculate_wind_output(
        wind_speed: float, 
        capacity_kw: float = 10.0,
        cut_in: float = 3.0,
        rated: float = 12.0,
        cut_out: float = 25.0
    ) -> float:
        """
        计算风电产出 (kW) - 标准功率曲线
        可配置切入、额定、切出风速
        """
        if wind_speed < cut_in or wind_speed > cut_out:
            return 0.0
        
        if wind_speed >= rated:
            return float(capacity_kw)
            
        # 在切入和额定之间，功率与风速的立方成正比
        factor = ((wind_speed - cut_in) / (rated - cut_in)) ** 3
        return round(capacity_kw * factor, 3)


# ==============================================================================
# Weather Client
# ==============================================================================

class WeatherClient:
    '''
    气象数据获取客户端
  
    - Purpose: 调用 OpenWeatherMap API 获取指定位置的天气预报
    - Input: location (纬度/经度 或 城市名), forecast_hours (预测时长)
    - Output: WeatherForecast 对象（含逐小时气象参数）
    - Notes: 需要 API Key；考虑请求频率限制和缓存策略
    '''
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.openweathermap.org/data/2.5"

    def _fetch_raw_data(self, lat: float, lon: float) -> list:
        """Internal helper to fetch data"""
        url = f"{self.base_url}/forecast"
        params = {
            "lat": lat, "lon": lon, "appid": self.api_key, "units": "metric"
        }
        try:
            resp = requests.get(url, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            return data.get("list", [])
        except Exception as e:
            print(f"Error fetching OWM data: {e}")
            return []

    def get_forecast(self, location: Union[Tuple[float, float], str], forecast_hours: int) -> WeatherForecast:
        """
        Implementation of the required interface.
        location: Can be (lat, lon) tuple OR "City Name" string.
        """
        # 1. Resolve Location
        lat, lon = 0.0, 0.0
        if isinstance(location, tuple):
            lat, lon = location
        elif isinstance(location, str):
            # 简单的 Mock Geocoding (实际应调用 Geocoding API)
            if "Shanghai" in location: lat, lon = 31.2304, 121.4737
            elif "Munich" in location: lat, lon = 48.1351, 11.5820
            elif "Berlin" in location: lat, lon = 52.5200, 13.4050
            else: lat, lon = 31.2304, 121.4737  # Default

        # 2. Fetch Data
        raw_list = self._fetch_raw_data(lat, lon)
        if not raw_list:
            # Return empty structure on error
            return WeatherForecast(
                timestamps=[], solar_irradiance=[], wind_speed=[], 
                wind_direction=[], temperature=[], cloud_cover=[], humidity=[]
            )

        # 3. Process & Interpolate
        timestamps = []
        solars = []
        winds = []
        wind_dirs = []
        temps = []
        clouds = []
        humidities = []

        # 预处理数据点
        parsed_points = []
        for p in raw_list:
            parsed_points.append({
                "dt": datetime.datetime.fromtimestamp(p["dt"], timezone.utc),
                "temp": p["main"]["temp"],
                "clouds": p["clouds"]["all"],
                "wind": p["wind"]["speed"],
                "wind_deg": p["wind"].get("deg", 0),
                "humidity": p["main"].get("humidity", 50)
            })

        # 执行线性插值 (每两点之间填充)
        for i in range(len(parsed_points) - 1):
            p1 = parsed_points[i]
            p2 = parsed_points[i+1]
            
            # 计算需要插入几个点
            time_diff = (p2["dt"] - p1["dt"]).total_seconds() / 3600
            steps = int(time_diff)
            
            for step in range(steps):
                factor = step / steps
                
                # 线性插值计算
                interp_temp = p1["temp"] + (p2["temp"] - p1["temp"]) * factor
                interp_clouds = int(p1["clouds"] + (p2["clouds"] - p1["clouds"]) * factor)
                interp_wind = p1["wind"] + (p2["wind"] - p1["wind"]) * factor
                interp_deg = p1["wind_deg"]  # 方向插值较复杂，暂且取最近
                interp_hum = p1["humidity"] + (p2["humidity"] - p1["humidity"]) * factor
                
                current_dt = p1["dt"] + datetime.timedelta(hours=step)
                
                # 停止条件
                if len(timestamps) >= forecast_hours:
                    break

                timestamps.append(current_dt)
                temps.append(round(interp_temp, 2))
                clouds.append(float(interp_clouds))
                winds.append(round(interp_wind, 2))
                wind_dirs.append(float(interp_deg))
                humidities.append(float(interp_hum))
                
                # 估算辐射 (Physics)
                irr = PhysicsEngine.calculate_irradiance(lat, current_dt, interp_clouds)
                solars.append(round(irr, 2))
            
            if len(timestamps) >= forecast_hours:
                break

        return WeatherForecast(
            timestamps=timestamps,
            solar_irradiance=solars,
            wind_speed=winds,
            wind_direction=wind_dirs,
            temperature=temps,
            cloud_cover=clouds,
            humidity=humidities
        )


# ==============================================================================
# Forecasters
# ==============================================================================

class PVForecaster:
    '''
    光伏发电量预测器
  
    - Purpose: 基于气象数据和光伏系统参数，预测发电量
    - Input: 
        - weather: WeatherForecast
        - pv_capacity_kw: 装机容量
        - panel_efficiency: 组件效率 (0-1)
        - orientation: 朝向/倾角（可选） tuple(tilt, azimuth)
    - Output: List[float] 逐时段发电量 (kWh)
    - Notes: 简化模型：generation = irradiance × capacity × efficiency × (1 - cloud_factor)
    '''
    def __init__(self, tilt: float = 30.0, azimuth: float = 180.0):
        self.default_tilt = tilt
        self.default_azimuth = azimuth

    def _calculate_orientation_factor(self, tilt: float, azimuth: float) -> float:
        """Internal helper for orientation loss"""
        # 每偏离最佳朝向 45度，损失 5%
        azimuth_diff = abs(azimuth - 180)
        azimuth_loss = (azimuth_diff / 45) * 0.05
        
        # 每偏离最佳倾角 15度，损失 2%
        tilt_diff = abs(tilt - 30)
        tilt_loss = (tilt_diff / 15) * 0.02
        
        factor = 1.0 - azimuth_loss - tilt_loss
        return max(0.0, factor)

    def predict(
        self, 
        weather: WeatherForecast, 
        pv_capacity_kw: float, 
        panel_efficiency: float,
        orientation: Optional[Tuple[float, float]] = None
    ) -> List[float]:
        """
        Implementation of the required interface.
        orientation: Optional tuple (tilt, azimuth). If None, use defaults.
        """
        tilt = self.default_tilt
        azimuth = self.default_azimuth
        
        if orientation:
            tilt, azimuth = orientation
            
        results = []
        orientation_factor = self._calculate_orientation_factor(tilt, azimuth)
        
        for irr in weather.solar_irradiance:
            base_output = PhysicsEngine.calculate_pv_output(irr, pv_capacity_kw, panel_efficiency)
            final_output = base_output * orientation_factor
            results.append(round(final_output, 3))
            
        return results


class WindForecaster:
    '''
    风电发电量预测器
  
    - Purpose: 基于风速和风机参数，预测发电量
    - Input:
        - weather: WeatherForecast
        - turbine_capacity_kw: 风机额定功率
        - cut_in_speed: 切入风速 (m/s)
        - rated_speed: 额定风速 (m/s)
        - cut_out_speed: 切出风速 (m/s)
    - Output: List[float] 逐时段发电量 (kWh)
    - Notes: 使用风机功率曲线；超过切出风速时输出为0
    '''
    def predict(
        self, 
        weather: WeatherForecast, 
        turbine_capacity_kw: float, 
        cut_in_speed: float, 
        rated_speed: float, 
        cut_out_speed: float
    ) -> List[float]:
        """
        Implementation of the required interface.
        """
        results = []
        for wind_spd in weather.wind_speed:
            out = PhysicsEngine.calculate_wind_output(
                wind_speed=wind_spd, 
                capacity_kw=turbine_capacity_kw,
                cut_in=cut_in_speed,
                rated=rated_speed,
                cut_out=cut_out_speed
            )
            results.append(out)
        return results


# ==============================================================================
# Weather Service (Main Interface)
# ==============================================================================

class WeatherService:
    '''
    Weather 模块对外统一接口
  
    - Purpose: 封装完整流程，供 Optimizer 和 Agent 调用
    - Input: location, forecast_hours, asset_config (PV/Wind 参数)
    - Output: GenerationForecast 对象（含 PV + Wind 预测）
    - Notes: 组合调用 WeatherClient + PVForecaster + WindForecaster
    '''
    def __init__(self, api_key: str):
        self.client = WeatherClient(api_key)
        self.pv_forecaster = PVForecaster()
        self.wind_forecaster = WindForecaster()

    def get_generation_forecast(
        self, 
        location: Union[Tuple[float, float], str], 
        forecast_hours: int, 
        asset_config: Optional[AssetConfig] = None
    ) -> GenerationForecast:
        """
        Implementation of the required interface.
        """
        # 1. Handle Default Config
        if asset_config is None:
            asset_config = AssetConfig()

        # 2. Get Weather Data (Client)
        wf = self.client.get_forecast(location, forecast_hours)
        
        # 3. Predict PV Generation
        pv_outputs = self.pv_forecaster.predict(
            weather=wf,
            pv_capacity_kw=asset_config.pv_capacity_kw,
            panel_efficiency=asset_config.pv_efficiency,
            orientation=(asset_config.pv_tilt, asset_config.pv_azimuth)
        )
        
        # 4. Predict Wind Generation
        wind_outputs = self.wind_forecaster.predict(
            weather=wf,
            turbine_capacity_kw=asset_config.wind_capacity_kw,
            cut_in_speed=asset_config.wind_cut_in_speed,
            rated_speed=asset_config.wind_rated_speed,
            cut_out_speed=asset_config.wind_cut_out_speed
        )
        
        # 5. Assemble Result
        timeline = []
        count = len(wf.timestamps)
        
        # Determine location name for report
        loc_name = location if isinstance(location, str) else "Lat/Lon"
        
        for i in range(count):
            pv = pv_outputs[i]
            wind = wind_outputs[i]
            timeline.append(GenerationPoint(
                timestamp=wf.timestamps[i],
                pv_output_kw=pv,
                wind_output_kw=wind,
                total_output_kw=round(pv + wind, 3)
            ))
            
        return GenerationForecast(
            location=loc_name,
            generated_at=datetime.datetime.now(),
            timeline=timeline
        )
