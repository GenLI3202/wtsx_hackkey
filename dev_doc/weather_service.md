# Weather Service 开发指南

本文档为 Module A: Weather Service 的开发参考手册。

---

## 1. 环境配置

### 1.1 必需的 API Key

| 变量名 | 来源 | 说明 |
|--------|------|------|
| `OPENWEATHER_API_KEY` | [OpenWeatherMap](https://openweathermap.org/api) | 免费账号支持 1000 次/天 |

### 1.2 .env 配置

在项目根目录创建 `.env` 文件：

```bash
# Weather Service
OPENWEATHER_API_KEY=your_api_key_here
```

> ⚠️ **注意**: `.env` 文件已在 `.gitignore` 中，不要提交到 Git

### 1.3 ngrok 配置（IBM WatsonX Orchestrate 集成）

IBM WatsonX Orchestrate 需要一个**公网可访问的 HTTPS URL** 才能调用你的本地 API。使用 ngrok 创建安全隧道：

#### 安装 ngrok

```bash
# macOS
brew install ngrok

# 或直接下载
# https://ngrok.com/download
```

#### 配置 ngrok Token

```bash
# 注册 ngrok 账号后获取 authtoken
ngrok config add-authtoken YOUR_NGROK_TOKEN
```

#### 启动隧道

```bash
# 1. 先启动本地 API 服务
cd /Users/shane/Desktop/hackkez/wtsx_hackkey
uvicorn src.backend.main:app --host 0.0.0.0 --port 8000

# 2. 新终端启动 ngrok
ngrok http 8000
```

ngrok 输出示例：
```
Forwarding  https://abc123.ngrok-free.app -> http://localhost:8000
```

#### 获取 OpenAPI 规范

```bash
# 使用 ngrok 提供的 HTTPS 地址
curl https://abc123.ngrok-free.app/openapi.json > openapi_spec.json
```

### 1.4 IBM WatsonX Orchestrate 集成步骤

1. **登录** [WatsonX Orchestrate](https://www.ibm.com/products/watsonx-orchestrate)
2. **创建 Skill** → Import from OpenAPI
3. **上传** `openapi_spec.json` 或输入 ngrok URL: `https://abc123.ngrok-free.app/openapi.json`
4. **测试** Skill 调用

> ⚠️ **注意**: ngrok 免费版每次重启会**更换 URL**，需要重新配置 Orchestrate

---

## 2. 快速开始

```python
from src.backend.services.weather import WeatherService, AssetConfig

# 初始化服务
weather_svc = WeatherService(api_key="your_openweather_api_key")

# 方式一: 使用城市名
forecast = weather_svc.get_generation_forecast(
    location="Munich",
    forecast_hours=24
)

# 方式二: 使用经纬度
forecast = weather_svc.get_generation_forecast(
    location=(48.1351, 11.5820),  # Munich
    forecast_hours=24
)

# 遍历预测结果
for point in forecast.timeline:
    print(f"{point.timestamp}: PV={point.pv_output_kw}kW, Wind={point.wind_output_kw}kW")
```

---

## 3. 类说明

### 3.1 WeatherService（主入口）

对外统一接口，组合调用其他组件。

```python
def get_generation_forecast(
    location: str | Tuple[float, float],  # 城市名或 (lat, lon)
    forecast_hours: int,                   # 预测时长（小时）
    asset_config: Optional[AssetConfig]    # 资产配置，可选
) -> GenerationForecast
```

### 3.2 WeatherClient

OpenWeatherMap API 客户端，负责：
- 调用 `/forecast` 接口获取 5 天预报
- 将 3 小时分辨率**线性插值**到 1 小时
- 计算太阳辐照度（基于物理模型）

### 3.3 PVForecaster

光伏发电预测器：
- 输入: 辐照度、装机容量、效率、朝向
- 输出: 逐小时发电量 (kW)

### 3.4 WindForecaster

风电发电预测器：
- 使用标准风机功率曲线
- 支持配置切入/额定/切出风速

---

## 4. 数据模型

### 4.1 AssetConfig（资产配置）

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `pv_capacity_kw` | float | 10.0 | 光伏装机容量 |
| `pv_tilt` | float | 30.0 | 光伏板倾角 (°) |
| `pv_azimuth` | float | 180.0 | 光伏板朝向 (180=正南) |
| `pv_efficiency` | float | 0.20 | 组件效率 (0-1) |
| `wind_capacity_kw` | float | 50.0 | 风机额定功率 |
| `wind_cut_in_speed` | float | 3.0 | 切入风速 (m/s) |
| `wind_rated_speed` | float | 12.0 | 额定风速 (m/s) |
| `wind_cut_out_speed` | float | 25.0 | 切出风速 (m/s) |

### 4.2 WeatherForecast（气象数据）

列式存储，所有 List 长度一致：

| 字段 | 类型 | 单位 |
|------|------|------|
| `timestamps` | List[datetime] | UTC 时间 |
| `solar_irradiance` | List[float] | W/m² |
| `wind_speed` | List[float] | m/s |
| `wind_direction` | List[float] | ° |
| `temperature` | List[float] | °C |
| `cloud_cover` | List[float] | % |
| `humidity` | List[float] | % |

### 4.3 GenerationForecast（发电预测）

```python
{
    "location": "Munich",
    "generated_at": "2026-01-31T18:00:00",
    "timeline": [
        {
            "timestamp": "2026-01-31T19:00:00",
            "pv_output_kw": 2.5,
            "wind_output_kw": 15.3,
            "total_output_kw": 17.8
        },
        ...
    ]
}
```

---

## 5. 物理模型备注

### 5.1 太阳辐照度计算

`PhysicsEngine.calculate_irradiance()` 实现了简化的太阳位置模型：

1. 计算太阳赤纬角（基于日期）
2. 计算太阳高度角（基于纬度和时间）
3. 晴天辐射 = 1000 × sin(高度角) W/m²
4. 云量衰减 = 1 - 0.75 × (云量)³

### 5.2 风机功率曲线

```
功率
  │     ___________
  │    /
  │   /
  │__/
  └─────────────────── 风速
   切入  额定   切出
```

- 切入前: 0 输出
- 切入~额定: 立方关系增长
- 额定~切出: 满功率
- 切出后: 0 输出（保护性停机）

---

## 6. 常见问题

### Q1: API 调用频率限制？

OpenWeatherMap 免费账号限制 **60 次/分钟**。建议：
- 开发时使用缓存或 mock 数据
- 生产环境考虑 Redis 缓存

### Q2: 如何使用 Mock 数据测试？

目前代码中内置了简单的 Geocoding mock（支持 Munich, Berlin, Shanghai）。如需更多城市，可在 `WeatherClient.get_forecast()` 中添加。

### Q3: 支持哪些城市？

内置支持：Munich, Berlin, Shanghai。其他城市请使用 `(lat, lon)` 坐标。

---

## 7. 相关文件

- 实现代码: [weather.py](../src/backend/services/weather.py)
- 架构设计: [architecture.md](../architecture.md) (Module A 章节)
- 测试用例: [test_weather.py](../tests/test_weather.py)
