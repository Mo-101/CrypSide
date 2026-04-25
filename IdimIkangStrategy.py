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

    config_version = "v1.0-baseline-observer"
    
    timeframe = '15m'
    
    # Optional parameters
    startup_candle_count: int = 50

    # ATR Multipliers
    atr_sl_multiplier = 1.0
    atr_tp_multiplier = 3.0

    can_short = True

    whitlist_gate = WhitelistGate(str(Path(__file__).parent / "whitelist.json"))

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # EMA
        dataframe['ema20'] = ta.ema(dataframe['close'], length=20)
        dataframe['ema50'] = ta.ema(dataframe['close'], length=50)

        # RSI
        dataframe['rsi14'] = ta.rsi(dataframe['close'], length=14)

        # MACD
        macd = ta.macd(dataframe['close'])
        if macd is not None and len(macd.columns) >= 2:
            dataframe['macd_hist'] = macd[macd.columns[1]]
        else:
            dataframe['macd_hist'] = 0.0

        # ATR
        dataframe['atr14'] = ta.atr(dataframe['high'], dataframe['low'], dataframe['close'], length=14)
        
        # Volume SMA
        dataframe['volume_sma20'] = ta.sma(dataframe['volume'], length=20)

        # Note: In Freqtrade, we typically calculate the 4H regime using 4H informative timeframe
        # For simplicity, we calculate a simplified regime on 15m or mock it if informative not added perfectly
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (dataframe['ema20'] > dataframe['ema50']) &
            (dataframe['close'] > dataframe['ema20']) &
            (dataframe['rsi14'] >= 30) & (dataframe['rsi14'] <= 65) &
            (dataframe['macd_hist'] > 0),
            'enter_long'
        ] = 1

        dataframe.loc[
            (dataframe['ema20'] < dataframe['ema50']) &
            (dataframe['close'] < dataframe['ema20']) &
            (dataframe['rsi14'] >= 35) & (dataframe['rsi14'] <= 70) &
            (dataframe['macd_hist'] < 0),
            'enter_short'
        ] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[:, 'exit_long'] = 0
        dataframe.loc[:, 'exit_short'] = 0
        return dataframe
