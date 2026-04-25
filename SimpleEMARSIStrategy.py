from pandas import DataFrame
import pandas_ta as ta
from freqtrade.strategy import IStrategy

class SimpleEMARSIStrategy(IStrategy):
    """
    Simple trading strategy using EMA and RSI indicators.
    """
    INTERFACE_VERSION = 3

    timeframe = '15m'
    
    # Needs 50 candles before producing valid signals
    startup_candle_count: int = 50

    # These values can be overridden in the config.
    minimal_roi = {
        "0": 0.05
    }
    stoploss = -0.05
    trailing_stop = False

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # EMA
        dataframe['ema_fast'] = ta.ema(dataframe['close'], length=20)
        dataframe['ema_slow'] = ta.ema(dataframe['close'], length=50)

        # RSI
        dataframe['rsi'] = ta.rsi(dataframe['close'], length=14)
        
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Based on TA indicators, populates the entry signal for the given dataframe
        :param dataframe: DataFrame
        :param metadata: Additional information, like the currently traded pair
        :return: DataFrame with entry columns populated
        """
        # Long condition: Fast EMA > Slow EMA and RSI < 30 (oversold)
        dataframe.loc[
            (dataframe['ema_fast'] > dataframe['ema_slow']) &
            (dataframe['rsi'] < 30),
            'enter_long'
        ] = 1

        # Short condition: Fast EMA < Slow EMA and RSI > 70 (overbought)
        dataframe.loc[
            (dataframe['ema_fast'] < dataframe['ema_slow']) &
            (dataframe['rsi'] > 70),
            'enter_short'
        ] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Based on TA indicators, populates the exit signal for the given dataframe
        :param dataframe: DataFrame
        :param metadata: Additional information, like the currently traded pair
        :return: DataFrame with exit columns populated
        """
        # Exit Long condition: RSI crosses into overbought zone
        dataframe.loc[
            (dataframe['rsi'] > 70),
            'exit_long'
        ] = 1

        # Exit Short condition: RSI crosses into oversold zone
        dataframe.loc[
            (dataframe['rsi'] < 30),
            'exit_short'
        ] = 1

        return dataframe
