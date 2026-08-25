import os
import asyncio
import threading
import pandas as pd
import numpy as np
from flask import Flask
from playwright.async_api import async_playwright
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

# Helper to automatically capture SSID using Playwright
async def get_automated_ssid(email, password):
    ssid_captured = None
    print("Launching headless browser to harvest fresh SSID...")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        def handle_ws(ws):
            nonlocal ssid_captured
            def handle_frame(frame):
                nonlocal ssid_captured
                if frame.text and frame.text.startswith('42["auth"'):
                    ssid_captured = frame.text
            ws.on("framesent", handle_frame)

        page.on("websocket", handle_ws)

        try:
            await page.goto("https://pocketoption.com/en/login", wait_until="networkidle")
            await page.fill('input[name="email"]', email)
            await page.fill('input[name="password"]', password)
            await page.click('button[type="submit"]')
            
            # Wait up to 30 seconds for the WS authentication frame
            for _ in range(30):
                if ssid_captured:
                    print("Successfully harvested fresh SSID!")
                    break
                await asyncio.sleep(1)
        except Exception as e:
            print(f"Error during browser automation: {e}")
        finally:
            await browser.close()
            
    return ssid_captured

# Main Async Bot Logic
async def run_async_bot():
    print("Starting Modern Async Cloud Bot...")
    
    # Try getting SSID from environment first, or harvest automatically
    ssid = os.environ.get("POCKET_SSID")
    email = os.environ.get("POCKET_EMAIL")
    password = os.environ.get("POCKET_PASSWORD")

    if not ssid and email and password:
        ssid = await get_automated_ssid(email, password)

    if not ssid:
        print("ERROR: Could not retrieve a valid POCKET_SSID!")
        return

    # Initialize client (routes through Render environment proxy)
    api = AsyncPocketOptionClient(ssid=ssid, is_demo=True)
    await api.connect()
    
    balance_info = await api.get_balance()
    print(f"Connected! Cloud Bot Balance: ${balance_info.balance}")
    
    pairs = ["EURUSD_otc", "GBPUSD_otc", "USDJPY_otc", "AUDUSD_otc"]
    trade_amount = 1.0
    trade_duration = 60
    
    while True:
        try:
            for pair in pairs:
                candles = await api.get_candles_dataframe(asset=pair, timeframe=60, count=200)
                if candles is None or candles.empty:
                    continue
                    
                df = apply_strategy(candles)
                current = df.iloc[-1]
                prev = df.iloc[-2]
                
                if current['close'] > current['ema_200']:
                    if prev['close'] <= current['lower_band'] and current['rsi'] < 30:
                        print(f"[{pair}] CALL Signal. Executing...")
                        await api.place_order(asset=pair, amount=trade_amount, direction=OrderDirection.CALL, duration=trade_duration)
                        await asyncio.sleep(65)
                
                elif current['close'] < current['ema_200']:
                    if prev['close'] >= current['upper_band'] and current['rsi'] > 70:
                        print(f"[{pair}] PUT Signal. Executing...")
                        await api.place_order(asset=pair, amount=trade_amount, direction=OrderDirection.PUT, duration=trade_duration)
                        await asyncio.sleep(65)
            
            await asyncio.sleep(10)
        except Exception as e:
            print(f"Error in loop: {e}")
            await asyncio.sleep(10)

def start_bot_thread():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(run_async_bot())

if __name__ == "__main__":
    bot_thread = threading.Thread(target=start_bot_thread)
    bot_thread.start()
    
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port) 
