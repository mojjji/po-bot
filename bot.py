import os
import asyncio
import threading
import pandas as pd
import numpy as np
from flask import Flask
from pocketoptionapi_async import AsyncPocketOptionClient, OrderDirection

app = Flask(__name__)

@app.route('/')
def home():
    return "Async Pocket Option Bot is Active and Scanning!"

# Indicator Logic
def apply_strategy(df):
    df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()
    df['sma_20'] = df['close'].rolling(window=20).mean()
    df['std'] = df['close'].rolling(window=20).std()
    df['upper_band'] = df['sma_20'] + (df['std'] * 2)
    df['lower_band'] = df['sma_20'] - (df['std'] * 2)
    
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=7).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=7).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    return df

# Main Async Bot Logic
async def run_async_bot():
    print("Starting Modern Async Cloud Bot...")
    ssid = os.environ.get("POCKET_SSID")

    if not ssid:
        print("ERROR: POCKET_SSID not found in environment!")
        return

    # Initialize client (uses HTTP_PROXY/HTTPS_PROXY directly from Render's environment)
    api = AsyncPocketOptionClient(ssid=ssid, is_demo=True)
    await api.connect()
    
    balance_info = await api.get_balance()
    print(f"Connected! Cloud Bot Balance: ${balance_info.balance}")
    
    pairs = ["EURUSD_otc", "GBPUSD_otc", "USDJPY_otc", "AUDUSD_otc"]
    trade_amount = 1.0
    trade_duration = 60 # in seconds
    
    while True:
        try:
            for pair in pairs:
                # Fetch candles asynchronously
                candles = await api.get_candles_dataframe(asset=pair, timeframe=60, count=200)
                if candles is None or candles.empty:
                    continue
                    
                df = apply_strategy(candles)
                current = df.iloc[-1]
                prev = df.iloc[-2]
                
                # CALL Logic (Uptrend + Bottom Band + Oversold)
                if current['close'] > current['ema_200']:
                    if prev['close'] <= current['lower_band'] and current['rsi'] < 30:
                        print(f"[{pair}] CALL Signal. Executing...")
                        await api.place_order(asset=pair, amount=trade_amount, direction=OrderDirection.CALL, duration=trade_duration)
                        await asyncio.sleep(65)
                
                # PUT Logic (Downtrend + Top Band + Overbought)
                elif current['close'] < current['ema_200']:
                    if prev['close'] >= current['upper_band'] and current['rsi'] > 70:
                        print(f"[{pair}] PUT Signal. Executing...")
                        await api.place_order(asset=pair, amount=trade_amount, direction=OrderDirection.PUT, duration=trade_duration)
                        await asyncio.sleep(65)
            
            await asyncio.sleep(10) # Rest before next scan
        except Exception as e:
            print(f"Error in loop: {e}")
            await asyncio.sleep(10)

# Wrapper to run async functions inside a background thread
def start_bot_thread():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(run_async_bot())

if __name__ == "__main__":
    # Start the async bot in the background
    bot_thread = threading.Thread(target=start_bot_thread)
    bot_thread.start()
    
    # Start the dummy web server for Render
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
