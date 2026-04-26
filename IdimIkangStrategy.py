from pandas import DataFrame
import numpy as np
import pandas_ta as ta
from freqtrade.strategy import IStrategy

from pathlib import Path
import json

class WhitelistGate:
    def __init__(self, whitelist_path: str):
        self.whitelist_path = Path(whitelist_path)
        self._payload = {}
        self._index = {}
        if self.whitelist_path.exists():
            self.reload()

    def reload(self) -> None:
        self._payload = json.loads(self.whitelist_path.read_text(encoding="utf-8"))
        self._index = {
            pocket["pocket_id"]: pocket
            for pocket in self._payload.get("pockets", [])
        }

    def is_allowed(self, policy: str, regime: str, side: str) -> bool:
        pocket_id = f"{policy}|{regime}|{side.upper()}"
        return pocket_id in self._index


class IdimIkangStrategy(IStrategy):
    INTERFACE_VERSION = 3

    config_version = "v1.1-rr-repair-gated"
    timeframe = '15m'
    startup_candle_count: int = 50

    # Freqtrade required static config
    minimal_roi = {"0": 0.99}
    stoploss = -0.03
    trailing_stop = False

    # RR config
    use_custom_stoploss = True
    use_whitelist_gate = False
    use_hour_gate = False
    can_short = True

    whitelist_gate = WhitelistGate(str(Path(__file__).parent / "whitelist.json"))

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['ema20'] = ta.ema(dataframe['close'], length=20)
        dataframe['ema50'] = ta.ema(dataframe['close'], length=50)
        dataframe['rsi14'] = ta.rsi(dataframe['close'], length=14)
        macd = ta.macd(dataframe['close'])
        if macd is not None and len(macd.columns) >= 2:
            dataframe['macd_hist'] = macd[macd.columns[1]]
        else:
            dataframe['macd_hist'] = 0.0
        dataframe['atr14'] = ta.atr(dataframe['high'], dataframe['low'], dataframe['close'], length=14)
        dataframe['volume_sma20'] = ta.sma(dataframe['volume'], length=20)
        # RR fields
        sl_x = dataframe['atr14'] / dataframe['close']
        sl_x = sl_x.replace([np.inf, -np.inf], np.nan)
        sl_x = sl_x.clip(lower=0.003, upper=0.05)
        dataframe['sl_x'] = sl_x
        dataframe['tp_x'] = sl_x * 2.0
        dataframe['rr'] = dataframe['tp_x'] / dataframe['sl_x']
        # Placeholders for regime, family, policy, pwin, hour_utc
        if 'regime' not in dataframe:
            dataframe['regime'] = 'UNKNOWN'
        if 'family' not in dataframe:
            dataframe['family'] = 'UNKNOWN'
        if 'policy' not in dataframe:
            dataframe['policy'] = 'UNKNOWN'
        if 'pwin' not in dataframe.columns:
            dataframe['pwin'] = np.nan
        # hour_utc from date column if present
        if 'hour_utc' not in dataframe:
            if 'date' in dataframe:
                dataframe['hour_utc'] = dataframe['date'].dt.hour
            else:
                dataframe['hour_utc'] = 0
        return dataframe

    def _is_good_regime(self, regime: str, side: str) -> bool:
        if side == 'long':
            return regime not in ['RANGING', 'DOWNTREND', 'STRONG_DOWNTREND']
        else:
            return regime not in ['RANGING', 'UPTREND', 'STRONG_UPTREND']

    def _is_good_hour(self, hour: int) -> bool:
        # Placeholder: allow all hours unless use_hour_gate is True
        if not self.use_hour_gate:
            return True
        # Example: only allow 21 UTC
        return hour == 21

    def _is_allowed(self, row, side: str) -> bool:
        # pwin gate: must be real and >= 0.65
        if ('pwin' not in row or np.isnan(row['pwin']) or row['pwin'] < 0.65):
            return False
        # regime gate
        if not self._is_good_regime(row['regime'], side):
            return False
        # hour gate (disabled by default)
        if self.use_hour_gate and not self._is_good_hour(int(row['hour_utc'])):
            return False
        # whitelist gate (optional)
        if self.use_whitelist_gate:
            if not self.whitelist_gate.is_allowed(row['policy'], row['regime'], side):
                return False
        # RR gate
        if row['rr'] < 1.5:
            return False
        return True

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Vectorized regime, pwin, RR, hour, whitelist gates
        long_mask = (
            (dataframe['ema20'] > dataframe['ema50']) &
            (dataframe['close'] > dataframe['ema20']) &
            (dataframe['rsi14'] >= 30) & (dataframe['rsi14'] <= 65) &
            (dataframe['macd_hist'] > 0) &
            (dataframe['pwin'] >= 0.65) &
            (dataframe['rr'] >= 1.5) &
            (~dataframe['regime'].isin(['RANGING', 'DOWNTREND', 'STRONG_DOWNTREND']))
        )
        short_mask = (
            (dataframe['ema20'] < dataframe['ema50']) &
            (dataframe['close'] < dataframe['ema20']) &
            (dataframe['rsi14'] >= 35) & (dataframe['rsi14'] <= 70) &
            (dataframe['macd_hist'] < 0) &
            (dataframe['pwin'] >= 0.65) &
            (dataframe['rr'] >= 1.5) &
            (~dataframe['regime'].isin(['RANGING', 'UPTREND', 'STRONG_UPTREND']))
        )
        # Hour gate (if enabled)
        if self.use_hour_gate:
            long_mask &= (dataframe['hour_utc'] == 21)
            short_mask &= (dataframe['hour_utc'] == 21)
        # Whitelist gate (if enabled)
        if self.use_whitelist_gate:
            long_mask &= dataframe.apply(lambda row: self.whitelist_gate.is_allowed(row['policy'], row['regime'], 'long'), axis=1)
            short_mask &= dataframe.apply(lambda row: self.whitelist_gate.is_allowed(row['policy'], row['regime'], 'short'), axis=1)
        dataframe['enter_long'] = long_mask.astype(int)
        dataframe['enter_short'] = short_mask.astype(int)
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['exit_long'] = 0
        dataframe['exit_short'] = 0
        return dataframe

    def custom_stoploss(self, pair: str, trade, current_time, current_rate, current_profit, **kwargs):
        # ATR-based stoploss: 1R only
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe is None or dataframe.empty:
            return None
        last_row = dataframe.iloc[-1]
        sl_x = last_row.get('sl_x', None)
        if sl_x is None or not np.isfinite(sl_x):
            return None
        return -sl_x

    def custom_exit(self, pair: str, trade, current_time, current_rate, current_profit, **kwargs):
        # TP: 2R only
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe is None or dataframe.empty:
            return None
        last_row = dataframe.iloc[-1]
        tp_x = last_row.get('tp_x', None)
        if tp_x is None or not np.isfinite(tp_x):
            return None
        if current_profit >= tp_x:
            return "take_profit"
        return None
