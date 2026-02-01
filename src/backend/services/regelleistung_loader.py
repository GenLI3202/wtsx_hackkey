"""
Regelleistung.net 数据加载器

从 XLSX 文件加载 FCR, aFRR Capacity, aFRR Energy 市场价格数据。
数据来源: https://www.regelleistung.net/apps/datacenter/
"""

import os
import datetime
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field

try:
    import pandas as pd
except ImportError:
    pd = None
    print("Warning: pandas not installed. Run: pip install pandas openpyxl")


# ==============================================================================
# 数据模型
# ==============================================================================

@dataclass
class FCRPrice:
    """FCR 容量市场价格 (4小时块)"""
    timestamp: datetime.datetime
    price_eur_mw: float  # €/MW per 4-hour block
    product: str  # NEGPOS_00_04, NEGPOS_04_08, etc.


@dataclass
class AFRRCapacityPrice:
    """aFRR 容量市场价格 (4小时块, Pos/Neg)"""
    timestamp: datetime.datetime
    price_pos_eur_mw_h: float  # €/MW/h for positive reserve
    price_neg_eur_mw_h: float  # €/MW/h for negative reserve
    product: str  # POS_00_04, NEG_00_04, etc.


@dataclass
class AFRREnergyPrice:
    """aFRR 能量市场价格 (15分钟, Pos/Neg)"""
    timestamp: datetime.datetime
    price_pos_eur_mwh: float  # €/MWh for positive activation
    price_neg_eur_mwh: float  # €/MWh for negative activation
    product: str  # POS_001, NEG_001, etc.


@dataclass
class RegelleistungPrices:
    """Regelleistung 完整价格数据"""
    date: datetime.date
    fcr: List[FCRPrice] = field(default_factory=list)
    afrr_capacity: List[AFRRCapacityPrice] = field(default_factory=list)
    afrr_energy: List[AFRREnergyPrice] = field(default_factory=list)


# ==============================================================================
# 数据加载器
# ==============================================================================

class RegelleistungLoader:
    """
    Regelleistung.net XLSX 数据加载器
    
    从本地 XLSX 文件加载 FCR, aFRR Capacity, aFRR Energy 价格数据。
    """
    
    # 4小时时段映射
    TIME_SLOTS_4H = {
        "00_04": (0, 4),
        "04_08": (4, 8),
        "08_12": (8, 12),
        "12_16": (12, 16),
        "16_20": (16, 20),
        "20_24": (20, 24),
    }
    
    def __init__(self, data_dir: str = None):
        """
        初始化加载器
        
        Args:
            data_dir: XLSX 文件目录，默认为 data/prices/regelleistung/
        """
        if data_dir is None:
            # 相对于项目根目录
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
            self.data_dir = os.path.join(base_dir, "data", "prices", "regelleistung")
        else:
            self.data_dir = data_dir
    
    def load_fcr_prices(self, date: datetime.date) -> List[FCRPrice]:
        """
        加载 FCR 容量市场价格
        
        Args:
            date: 交付日期
            
        Returns:
            FCRPrice 列表 (6个4小时块)
        """
        if pd is None:
            raise ImportError("pandas is required. Install: pip install pandas openpyxl")
        
        date_str = date.strftime("%Y-%m-%d")
        filename = f"RESULT_OVERVIEW_CAPACITY_MARKET_FCR_{date_str}_{date_str}.xlsx"
        filepath = os.path.join(self.data_dir, filename)
        
        if not os.path.exists(filepath):
            print(f"FCR file not found: {filepath}")
            return []
        
        df = pd.read_excel(filepath, sheet_name=0)
        prices = []
        
        # 查找价格列 (优先使用 CROSSBORDER 或 GERMANY)
        price_col = None
        for col in df.columns:
            if 'CROSSBORDER_SETTLEMENTCAPACITY_PRICE' in col:
                price_col = col
                break
            elif 'GERMANY_SETTLEMENTCAPACITY_PRICE' in col and price_col is None:
                price_col = col
        
        if price_col is None:
            print(f"No price column found in FCR file")
            return []
        
        # 获取 PRODUCT 列
        product_col = 'PRODUCT' if 'PRODUCT' in df.columns else None
        
        for idx, row in df.iterrows():
            product = row.get(product_col, f"SLOT_{idx}") if product_col else f"SLOT_{idx}"
            price = row[price_col]
            
            # 解析时段
            slot_key = None
            for key in self.TIME_SLOTS_4H.keys():
                if key in str(product):
                    slot_key = key
                    break
            
            if slot_key:
                start_hour, _ = self.TIME_SLOTS_4H[slot_key]
                timestamp = datetime.datetime.combine(date, datetime.time(hour=start_hour))
            else:
                # Fallback: 按行号推算
                start_hour = (idx % 6) * 4
                timestamp = datetime.datetime.combine(date, datetime.time(hour=start_hour))
            
            prices.append(FCRPrice(
                timestamp=timestamp,
                price_eur_mw=float(price),
                product=str(product)
            ))
        
        return prices
    
    def load_afrr_capacity_prices(self, date: datetime.date) -> Dict[str, List[AFRRCapacityPrice]]:
        """
        加载 aFRR 容量市场价格
        
        Args:
            date: 交付日期
            
        Returns:
            {'pos': [...], 'neg': [...]} 字典
        """
        if pd is None:
            raise ImportError("pandas is required")
        
        date_str = date.strftime("%Y-%m-%d")
        filename = f"RESULT_OVERVIEW_CAPACITY_MARKET_aFRR_{date_str}_{date_str}.xlsx"
        filepath = os.path.join(self.data_dir, filename)
        
        if not os.path.exists(filepath):
            print(f"aFRR Capacity file not found: {filepath}")
            return {'pos': [], 'neg': []}
        
        df = pd.read_excel(filepath, sheet_name=0)
        
        if df.empty:
            return {'pos': [], 'neg': []}
        
        # 查找价格列
        price_col = None
        for col in df.columns:
            if 'AVERAGE_CAPACITY_PRICE' in col and 'TOTAL' in col:
                price_col = col
                break
            elif 'GERMANY_AVERAGE_CAPACITY_PRICE' in col:
                price_col = col
        
        if price_col is None:
            print(f"No price column found in aFRR Capacity file")
            return {'pos': [], 'neg': []}
        
        pos_prices = []
        neg_prices = []
        
        for idx, row in df.iterrows():
            product = str(row.get('PRODUCT', ''))
            price = row[price_col]
            
            # 解析时段
            slot_key = None
            for key in self.TIME_SLOTS_4H.keys():
                if key in product:
                    slot_key = key
                    break
            
            if slot_key:
                start_hour, _ = self.TIME_SLOTS_4H[slot_key]
                timestamp = datetime.datetime.combine(date, datetime.time(hour=start_hour))
            else:
                continue
            
            if product.startswith('POS'):
                pos_prices.append(AFRRCapacityPrice(
                    timestamp=timestamp,
                    price_pos_eur_mw_h=float(price),
                    price_neg_eur_mw_h=0.0,
                    product=product
                ))
            elif product.startswith('NEG'):
                neg_prices.append(AFRRCapacityPrice(
                    timestamp=timestamp,
                    price_pos_eur_mw_h=0.0,
                    price_neg_eur_mw_h=float(price),
                    product=product
                ))
        
        return {'pos': pos_prices, 'neg': neg_prices}
    
    def load_afrr_energy_prices(self, date: datetime.date) -> Dict[str, List[AFRREnergyPrice]]:
        """
        加载 aFRR 能量市场价格
        
        Args:
            date: 交付日期
            
        Returns:
            {'pos': [...], 'neg': [...]} 字典
        """
        if pd is None:
            raise ImportError("pandas is required")
        
        date_str = date.strftime("%Y-%m-%d")
        filename = f"RESULT_OVERVIEW_ENERGY_MARKET_aFRR_{date_str}_{date_str}.xlsx"
        filepath = os.path.join(self.data_dir, filename)
        
        if not os.path.exists(filepath):
            print(f"aFRR Energy file not found: {filepath}")
            return {'pos': [], 'neg': []}
        
        df = pd.read_excel(filepath, sheet_name=0)
        
        if df.empty:
            return {'pos': [], 'neg': []}
        
        # 查找价格列
        avg_price_col = None
        for col in df.columns:
            if 'AVERAGE_ENERGY_PRICE' in col:
                avg_price_col = col
                break
        
        if avg_price_col is None:
            return {'pos': [], 'neg': []}
        
        pos_prices = []
        neg_prices = []
        
        for idx, row in df.iterrows():
            product = str(row.get('PRODUCT', ''))
            price = row[avg_price_col]
            
            # 解析15分钟时段 (NEG_001 = 第1个15分钟 = 00:00-00:15)
            try:
                slot_num = int(product.split('_')[1])
                # 每个时段15分钟
                hour = ((slot_num - 1) * 15) // 60
                minute = ((slot_num - 1) * 15) % 60
                timestamp = datetime.datetime.combine(date, datetime.time(hour=hour, minute=minute))
            except (IndexError, ValueError):
                continue
            
            if product.startswith('POS'):
                pos_prices.append(AFRREnergyPrice(
                    timestamp=timestamp,
                    price_pos_eur_mwh=float(price),
                    price_neg_eur_mwh=0.0,
                    product=product
                ))
            elif product.startswith('NEG'):
                neg_prices.append(AFRREnergyPrice(
                    timestamp=timestamp,
                    price_pos_eur_mwh=0.0,
                    price_neg_eur_mwh=float(price),
                    product=product
                ))
        
        return {'pos': pos_prices, 'neg': neg_prices}
    
    def load_all_prices(self, date: datetime.date) -> RegelleistungPrices:
        """
        加载指定日期的所有市场价格
        
        Args:
            date: 交付日期
            
        Returns:
            RegelleistungPrices 对象
        """
        fcr = self.load_fcr_prices(date)
        afrr_cap = self.load_afrr_capacity_prices(date)
        afrr_energy = self.load_afrr_energy_prices(date)
        
        # 合并 pos/neg 到单一列表
        afrr_capacity_combined = afrr_cap['pos'] + afrr_cap['neg']
        afrr_energy_combined = afrr_energy['pos'] + afrr_energy['neg']
        
        return RegelleistungPrices(
            date=date,
            fcr=fcr,
            afrr_capacity=afrr_capacity_combined,
            afrr_energy=afrr_energy_combined
        )
    
    def to_price_service_format(self, prices: RegelleistungPrices) -> Dict[str, Any]:
        """
        转换为 PriceService 兼容格式
        
        Returns:
            {
                'fcr': [{'timestamp': '...', 'DE': price}, ...],
                'afrr_capacity': [{'timestamp': '...', 'DE_Pos': price, 'DE_Neg': price}, ...],
                'afrr_energy': [{'timestamp': '...', 'DE_Pos': price, 'DE_Neg': price}, ...]
            }
        """
        result = {
            'fcr': [],
            'afrr_capacity': [],
            'afrr_energy': []
        }
        
        # FCR
        for p in prices.fcr:
            result['fcr'].append({
                'timestamp': p.timestamp.strftime('%Y-%m-%dT%H:%M:%S.000'),
                'DE': p.price_eur_mw
            })
        
        # aFRR Capacity - 合并 Pos/Neg 到同一时间戳
        afrr_cap_by_time = {}
        for p in prices.afrr_capacity:
            ts_key = p.timestamp.strftime('%Y-%m-%dT%H:%M:%S.000')
            if ts_key not in afrr_cap_by_time:
                afrr_cap_by_time[ts_key] = {'timestamp': ts_key, 'DE_Pos': 0, 'DE_Neg': 0}
            if p.price_pos_eur_mw_h > 0:
                afrr_cap_by_time[ts_key]['DE_Pos'] = p.price_pos_eur_mw_h
            if p.price_neg_eur_mw_h > 0:
                afrr_cap_by_time[ts_key]['DE_Neg'] = p.price_neg_eur_mw_h
        result['afrr_capacity'] = list(afrr_cap_by_time.values())
        
        # aFRR Energy - 合并 Pos/Neg 到同一时间戳
        afrr_energy_by_time = {}
        for p in prices.afrr_energy:
            ts_key = p.timestamp.strftime('%Y-%m-%dT%H:%M:%S.000')
            if ts_key not in afrr_energy_by_time:
                afrr_energy_by_time[ts_key] = {'timestamp': ts_key, 'DE_Pos': 0, 'DE_Neg': 0}
            if p.price_pos_eur_mwh != 0:
                afrr_energy_by_time[ts_key]['DE_Pos'] = p.price_pos_eur_mwh
            if p.price_neg_eur_mwh != 0:
                afrr_energy_by_time[ts_key]['DE_Neg'] = p.price_neg_eur_mwh
        result['afrr_energy'] = list(afrr_energy_by_time.values())
        
        return result
    
    def list_available_dates(self) -> List[datetime.date]:
        """列出所有可用的数据日期"""
        dates = set()
        
        if not os.path.exists(self.data_dir):
            return []
        
        for f in os.listdir(self.data_dir):
            if f.endswith('.xlsx') and 'RESULT_OVERVIEW' in f:
                # 提取日期: ..._{date}_{date}.xlsx
                parts = f.replace('.xlsx', '').split('_')
                try:
                    date_str = parts[-2]  # 倒数第二个是开始日期
                    date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
                    dates.add(date)
                except (IndexError, ValueError):
                    continue
        
        return sorted(dates)


# ==============================================================================
# 测试
# ==============================================================================

if __name__ == "__main__":
    loader = RegelleistungLoader()
    
    print("Available dates:", loader.list_available_dates())
    
    # 加载 2026-02-01 数据
    date = datetime.date(2026, 2, 1)
    prices = loader.load_all_prices(date)
    
    print(f"\n📊 Data for {date}:")
    print(f"  FCR: {len(prices.fcr)} records")
    print(f"  aFRR Capacity: {len(prices.afrr_capacity)} records")
    print(f"  aFRR Energy: {len(prices.afrr_energy)} records")
    
    # 转换为 PriceService 格式
    ps_format = loader.to_price_service_format(prices)
    print(f"\n📦 PriceService format:")
    print(f"  fcr: {len(ps_format['fcr'])} records")
    print(f"  afrr_capacity: {len(ps_format['afrr_capacity'])} records")
    print(f"  afrr_energy: {len(ps_format['afrr_energy'])} records")
    
    if ps_format['fcr']:
        print(f"\n  FCR sample: {ps_format['fcr'][0]}")
    if ps_format['afrr_capacity']:
        print(f"  aFRR Capacity sample: {ps_format['afrr_capacity'][0]}")
    if ps_format['afrr_energy']:
        print(f"  aFRR Energy sample: {ps_format['afrr_energy'][0]}")
