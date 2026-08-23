import os
import time
import threading
import pandas as pd
import numpy as np
from flask import Flask
from pocketoptionapi.stable_api import PocketOption

# 1. Create a dummy web server to keep Render from crashing
app = Flask(__name__)

@app.route('/')
def home():
    return "Pocket Option Bot is Active and Scanning!"

# 2. Indicator Logic
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

# 3. Main Bot Logic
def run_bot():
    print("Starting Cloud Bot...")
    # Get SSID securely from Render Environment Variables
    ssid = os.environ.get("POCKET_SSID")
    if not ssid:
        print("ERROR: POCKET_SSID not found in environment!")
        return

    api = PocketOption(ssid)
    if not api.connect():
        print("Failed to connect. SSID might be expired.")
        return
        
    api.change_balance(True) # True = Demo, False = Real
    print(f"Connected! Cloud Bot Balance: ${api.get_balance()}")
    
    pairs = ["EURUSD_otc", "GBPUSD_otc", "USDJPY_otc", "AUDUSD_otc"]
    trade_amount = 1
    trade_minutes = 1
    
    while True:
        try:
            for pair in pairs:
                candles = api.get_candles(pair, 60, 200)
                if not candles:
                    continue
                    
                df = apply_strategy(pd.DataFrame(candles))
                current = df.iloc[-1]
                prev = df.iloc[-2]
                
                # CALL Logic
                if current['close'] > current['ema_200']:
                    if prev['close'] <= current['lower_band'] and current['rsi'] < 30:
                        print(f"[{pair}] CALL Signal. Executing...")
                        api.buy(trade_amount, pair, "call", trade_minutes)
                        time.sleep(65)
                
                # PUT Logic
                elif current['close'] < current['ema_200']:
                    if prev['close'] >= current['upper_band'] and current['rsi'] > 70:
                        print(f"[{pair}] PUT Signal. Executing...")
                        api.buy(trade_amount, pair, "put", trade_minutes)
                        time.sleep(65)
            
            time.sleep(10) # Rest before next scan
        except Exception as e:
            print(f"Error in loop: {e}")
            time.sleep(10)

if __name__ == "__main__":
    # Start the trading bot in the background
    bot_thread = threading.Thread(target=run_bot)
    bot_thread.start()
    
    # Start the dummy web server on the port Render assigns
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
