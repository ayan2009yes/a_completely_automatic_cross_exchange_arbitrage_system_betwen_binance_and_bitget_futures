import requests
import time
import hashlib
import hmac
import base64
from decimal import Decimal, getcontext
from binance.client import Client
import json

# === HIGH PRECISION ===
getcontext().prec = 10

# === 🔐 API KEYS - REPLACE WITH YOUR ACTUAL KEYS ===
# 🔑 BINANCE API KEYS - Replace these with your actual Binance API credentials
binance_api_key = "enter_your_key"
binance_api_secret = "enter_your_key"
client = Client(binance_api_key, binance_api_secret)

# 🔑 BITGET API KEYS - Replace these with your actual Bitget API credentials
bitget_api_key = "enter_your_key"  # Replace with your Bitget API key
bitget_api_secret = "enter_your_key"  # Replace with your Bitget API secret
bitget_api_passphrase = "18Aug2009"  # Replace with your Bitget passphrase

# === 📬 TELEGRAM BOT SETTINGS ===
telegram_token = "enter_to_get_message_about_orders_in_telegram"
telegram_chat_id = "chat_id"

# === 🛠 CONFIGURATION ===
symbol = "CATIUSDT"  # Binance futures symbol
token_symbol = "CATI"
bitget_symbol = "CATIUSDT_UMCBL"  # Bitget futures symbol

gap_threshold = 0.3  # Buy/Sell threshold (%)
rebalance_threshold = -0.2  # Rebalance trigger (%)
fixed_trade_amount = Decimal('6.5')  
# Fixed $6 per trade
leverage = 1  # Leverage for futures trading (1-125x)

# Initialize clients
client = Client(binance_api_key, binance_api_secret)

# === 🔁 Enhanced trade state tracking ===
current_trade_state = "none"  # Can be "none", "binance_long_bitget_short", "binance_short_bitget_long"
last_action_time = 0

# ================================
# 🚀 FUNCTIONS START HERE
# ================================


def generate_bitget_signature(timestamp, method, request_path, body=""):
    """Generate Bitget API signature"""
    message = timestamp + method + request_path + body
    signature = base64.b64encode(
        hmac.new(bitget_api_secret.encode('utf-8'), message.encode('utf-8'),
                 hashlib.sha256).digest())
    return signature.decode()


def get_bitget_headers(method, request_path, body=""):
    """Generate Bitget API headers with proper authentication"""
    timestamp = str(int(time.time() * 1000))
    signature = generate_bitget_signature(timestamp, method, request_path,
                                          body)

    return {
        'ACCESS-KEY': bitget_api_key,
        'ACCESS-SIGN': signature,
        'ACCESS-TIMESTAMP': timestamp,
        'ACCESS-PASSPHRASE': bitget_api_passphrase,
        'Content-Type': 'application/json',
        'locale': 'en-US'
    }


def test_bitget_api_key():
    """Test if Bitget API key is working by calling a simple endpoint"""
    try:
        print("🔍 Testing Bitget API key...")
        request_path = "/api/spot/v1/account/getInfo"
        headers = get_bitget_headers("GET", request_path)

        url = f"https://api.bitget.com{request_path}"
        response = requests.get(url, headers=headers, timeout=10)
        data = response.json()

        if data.get('code') == '00000':
            print("✅ Bitget API key is working!")
            return True
        else:
            print(f"❌ Bitget API key test failed: {data}")
            return False
    except Exception as e:
        print(f"❌ Bitget API key test error: {e}")
        return False


def send_telegram_message(message):
    try:
        url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
        data = {"chat_id": telegram_chat_id, "text": message}
        requests.post(url, data=data, timeout=5)
    except Exception as e:
        print("Telegram Error:", e)


def get_binance_price():
    try:
        # Use private Binance futures API
        ticker = client.futures_symbol_ticker(symbol=symbol)
        return Decimal(ticker['price'])
    except Exception as e:
        print(f"❌ Binance price error: {e}")
        return None


def get_bitget_futures_price():
    try:
        # Use public Bitget futures API
        url = f"https://api.bitget.com/api/mix/v1/market/ticker?symbol={bitget_symbol}"
        response = requests.get(url, timeout=10)
        data = response.json()

        if data.get('code') == '00000' and data.get('data'):
            price_data = data['data']
            if 'last' in price_data and price_data['last']:
                return Decimal(price_data['last'])

        print(f"❌ Bitget futures API response: {data}")
        return None

    except Exception as e:
        print(f"❌ Bitget futures price error: {e}")
        return None


def get_usdt_balance():
    try:
        # Get USDT balance from Binance futures account
        balance = client.futures_account_balance()
        for asset in balance:
            if asset['asset'] == 'USDT':
                return Decimal(asset['balance'])
        return Decimal('0')
    except Exception as e:
        print(f"❌ Binance futures USDT balance error: {e}")
        return Decimal('0')


def get_binance_futures_position():
    try:
        # Get current futures position for the symbol
        positions = client.futures_position_information(symbol=symbol)
        for position in positions:
            if position['symbol'] == symbol:
                size = Decimal(position['positionAmt'])
                return {
                    'size':
                    abs(size),
                    'value':
                    Decimal(position['notional']),
                    'side':
                    'long' if size > 0 else ('short' if size < 0 else 'none')
                }
        return {'size': Decimal('0'), 'value': Decimal('0'), 'side': 'none'}
    except Exception as e:
        print(f"❌ Binance futures position error: {e}")
        return {'size': Decimal('0'), 'value': Decimal('0'), 'side': 'none'}


def get_bitget_futures_balance():
    try:
        # Check if API keys are set
        if bitget_api_key == "YOUR_BITGET_API_KEY" or not bitget_api_key:
            print("❌ Bitget API keys not configured!")
            return Decimal('0')

        # Try multiple endpoints for Bitget futures balance with retry logic
        for attempt in range(3):
            try:
                # Use the correct Bitget futures wallet endpoint with productType parameter
                request_path = "/api/mix/v1/account/accounts?productType=umcbl"
                headers = get_bitget_headers("GET", request_path)

                url = f"https://api.bitget.com{request_path}"
                response = requests.get(url, headers=headers, timeout=15)

                if response.status_code != 200:
                    print(
                        f"❌ Bitget API HTTP {response.status_code}: {response.text}"
                    )
                    print(f"🔍 Request URL: {url}")
                    print(f"🔍 Request Headers: {headers}")
                    if attempt < 2:
                        continue
                    return Decimal('0')

                data = response.json()
                # Only print debug output on first attempt to reduce spam
                if attempt == 0:
                    print(f"🔍 Bitget balance API response: {data}")

                if data.get('code') == '00000' and data.get('data'):
                    accounts = data['data']
                    for account in accounts:
                        if account.get('marginCoin') == 'USDT':
                            available_balance = Decimal(
                                str(account.get('available', '0')))
                            print(
                                f"💰 Bitget futures available: {available_balance} USDT"
                            )
                            return available_balance

                    print(f"⚠️ No USDT account found in: {accounts}")
                    return Decimal('0')
                elif data.get('code') == '40014':
                    print(
                        "❌ Bitget API Permission Error: Your API key needs 'Futures Read' and 'Futures Position Read/Write' permissions!"
                    )
                    print(
                        "💡 Please enable these permissions in your Bitget API settings."
                    )
                    return Decimal('0')
                else:
                    print(f"❌ Bitget balance API error: {data}")
                    if data.get('msg'):
                        print(f"Error message: {data['msg']}")
                    if attempt < 2:
                        continue
                    return Decimal('0')

            except requests.exceptions.ConnectionError as e:
                print(
                    f"❌ Bitget connection error (attempt {attempt + 1}): {e}")
                if attempt < 2:
                    continue
                return Decimal('0')
            except Exception as e:
                print(
                    f"❌ Bitget futures balance error (attempt {attempt + 1}): {e}"
                )
                if attempt < 2:
                    continue
                return Decimal('0')

        return Decimal('0')
    except Exception as e:
        print(f"❌ Bitget futures balance critical error: {e}")
        return Decimal('0')


def get_bitget_futures_positions():
    try:
        # Check if API keys are set
        if bitget_api_key == "YOUR_BITGET_API_KEY" or not bitget_api_key:
            print("❌ Bitget API keys not configured!")
            return {
                'size': Decimal('0'),
                'value': Decimal('0'),
                'side': 'none'
            }

        # Retry logic for Bitget positions
        for attempt in range(3):
            try:
                # Use correct Bitget futures positions endpoint with productType
                request_path = f"/api/mix/v1/position/allPosition?symbol={bitget_symbol}&productType=umcbl"
                headers = get_bitget_headers("GET", request_path)

                url = f"https://api.bitget.com{request_path}"
                response = requests.get(url, headers=headers, timeout=15)

                if response.status_code != 200:
                    print(
                        f"❌ Bitget positions HTTP {response.status_code}: {response.text}"
                    )
                    if attempt < 2:
                        continue
                    return {
                        'size': Decimal('0'),
                        'value': Decimal('0'),
                        'side': 'none'
                    }

                data = response.json()
                if attempt == 0:  # Only print debug on first attempt
                    print(f"🔍 Bitget positions API response: {data}")

                if data.get('code') == '00000' and data.get('data'):
                    positions = data['data']
                    if positions and len(positions) > 0:
                        position = positions[0]
                        size = Decimal(str(position.get('total', '0')))
                        side = position.get('holdSide', 'none')
                        return {
                            'size':
                            abs(size),
                            'value':
                            Decimal(str(position.get('unrealizedPL', '0'))),
                            'side':
                            side if size > 0 else 'none'
                        }

                    # No positions found
                    return {
                        'size': Decimal('0'),
                        'value': Decimal('0'),
                        'side': 'none'
                    }
                elif data.get('code') == '40014':
                    if attempt == 0:  # Only print once to avoid spam
                        print(
                            "❌ Bitget API Permission Error: Your API key needs 'Futures Position Read/Write' permissions!"
                        )
                        print(
                            "💡 Please enable these permissions in your Bitget API settings."
                        )
                    return {
                        'size': Decimal('0'),
                        'value': Decimal('0'),
                        'side': 'none'
                    }
                else:
                    if attempt == 0:
                        print(f"❌ Bitget positions API error: {data}")
                    if attempt < 2:
                        continue
                    return {
                        'size': Decimal('0'),
                        'value': Decimal('0'),
                        'side': 'none'
                    }

            except requests.exceptions.ConnectionError as e:
                print(
                    f"❌ Bitget positions connection error (attempt {attempt + 1}): {e}"
                )
                if attempt < 2:
                    continue
                return {
                    'size': Decimal('0'),
                    'value': Decimal('0'),
                    'side': 'none'
                }
            except Exception as e:
                print(f"❌ Bitget positions error (attempt {attempt + 1}): {e}")
                if attempt < 2:
                    continue
                return {
                    'size': Decimal('0'),
                    'value': Decimal('0'),
                    'side': 'none'
                }

        return {'size': Decimal('0'), 'value': Decimal('0'), 'side': 'none'}
    except Exception as e:
        print(f"❌ Bitget futures positions critical error: {e}")
        return {'size': Decimal('0'), 'value': Decimal('0'), 'side': 'none'}


def get_symbol_info():
    try:
        # Get futures exchange info
        info = client.futures_exchange_info()
        symbol_info = next(s for s in info['symbols'] if s['symbol'] == symbol)
        lot_size_filter = next(f for f in symbol_info['filters']
                               if f['filterType'] == 'LOT_SIZE')
        return {
            'stepSize': Decimal(lot_size_filter['stepSize']),
            'minQty': Decimal(lot_size_filter['minQty']),
            'maxQty': Decimal(lot_size_filter['maxQty'])
        }
    except Exception as e:
        print(f"❌ Futures symbol info error: {e}")
        return {
            'stepSize': Decimal('0.1'),
            'minQty': Decimal('0.1'),
            'maxQty': Decimal('1000000')
        }


def get_max_quantity_to_buy(price):
    usdt_balance = get_usdt_balance()
    if usdt_balance < fixed_trade_amount:
        return Decimal('0')

    symbol_info = get_symbol_info()
    qty = fixed_trade_amount / price

    # Adjust to step size
    qty = qty // symbol_info['stepSize'] * symbol_info['stepSize']

    # Check minimum quantity
    if qty < symbol_info['minQty']:
        return Decimal('0')

    return qty


def buy_on_binance():
    try:
        price = get_binance_price()
        if not price:
            return False
        quantity = get_max_quantity_to_buy(price)
        if quantity <= 0:
            return False

        # Use futures market buy order
        client.futures_create_order(symbol=symbol,
                                    side='BUY',
                                    type='MARKET',
                                    quantity=str(quantity))
        send_telegram_message(
            f"✅ Binance Futures BUY: {quantity} {token_symbol} @ {price} (${fixed_trade_amount})"
        )
        return True
    except Exception as e:
        send_telegram_message(f"❌ Binance Futures BUY failed: {e}")
        return False


def sell_on_binance():
    try:
        price = get_binance_price()
        if not price:
            return False

        # Calculate $6 worth of tokens to sell
        symbol_info = get_symbol_info()
        quantity = fixed_trade_amount / price

        # Adjust to step size
        quantity = quantity // symbol_info['stepSize'] * symbol_info['stepSize']

        if quantity < symbol_info['minQty']:
            send_telegram_message(
                f"⚠️ ${fixed_trade_amount} below minimum sell quantity.")
            return False

        # Use futures market sell order
        client.futures_create_order(symbol=symbol,
                                    side='SELL',
                                    type='MARKET',
                                    quantity=str(quantity))
        send_telegram_message(
            f"✅ Binance Futures SELL: {quantity} {token_symbol} @ {price} (${fixed_trade_amount})"
        )
        return True
    except Exception as e:
        send_telegram_message(f"❌ Binance Futures SELL failed: {e}")
        return False


def buy_futures_on_bitget():
    try:
        futures_balance = get_bitget_futures_balance()
        if futures_balance < fixed_trade_amount:
            send_telegram_message(
                f"⚠️ Not enough USDT in Bitget futures wallet to buy ${fixed_trade_amount} worth."
            )
            return False

        bitget_price = get_bitget_futures_price()
        if not bitget_price:
            return False

        # Calculate size for futures order
        size = fixed_trade_amount / bitget_price

        if size <= 0:
            send_telegram_message(
                f"⚠️ Order size too small for Bitget futures.")
            return False

        # Place market buy order on Bitget futures
        request_path = "/api/mix/v1/order/placeOrder"
        body = json.dumps({
            "symbol": bitget_symbol,
            "marginCoin": "USDT",
            "side": "open_long",
            "orderType": "market",
            "size": str(size)
        })
        headers = get_bitget_headers("POST", request_path, body)

        url = f"https://api.bitget.com{request_path}"
        response = requests.post(url, headers=headers, data=body, timeout=15)
        data = response.json()

        if data.get('code') == '00000':
            send_telegram_message(
                f"✅ Bitget Futures BUY: {size} @ {bitget_price}")
            return True
        else:
            send_telegram_message(f"❌ Bitget Futures BUY failed: {data}")
            return False

    except Exception as e:
        send_telegram_message(f"❌ Bitget Futures BUY failed: {e}")
        return False


def sell_futures_on_bitget():
    try:
        bitget_price = get_bitget_futures_price()
        if not bitget_price:
            return False

        # Calculate size for futures order
        size = fixed_trade_amount / bitget_price

        if size <= 0:
            send_telegram_message(
                "⚠️ Order size too small for Bitget futures.")
            return False

        # Place market sell order on Bitget futures
        request_path = "/api/mix/v1/order/placeOrder"
        body = json.dumps({
            "symbol": bitget_symbol,
            "marginCoin": "USDT",
            "side": "open_short",
            "orderType": "market",
            "size": str(size)
        })
        headers = get_bitget_headers("POST", request_path, body)

        url = f"https://api.bitget.com{request_path}"
        response = requests.post(url, headers=headers, data=body, timeout=15)
        data = response.json()

        if data.get('code') == '00000':
            send_telegram_message(
                f"✅ Bitget Futures SELL: {size} @ {bitget_price}")
            return True
        else:
            send_telegram_message(f"❌ Bitget Futures SELL failed: {data}")
            return False

    except Exception as e:
        send_telegram_message(f"❌ Bitget Futures SELL failed: {e}")
        return False


def close_binance_position():
    """Close existing Binance futures position"""
    try:
        position = get_binance_futures_position()
        if position['side'] == 'none' or position['size'] == 0:
            return True

        # Determine opposite side to close position
        close_side = 'SELL' if position['side'] == 'long' else 'BUY'

        # Close position using market order
        client.futures_create_order(symbol=symbol,
                                    side=close_side,
                                    type='MARKET',
                                    quantity=str(position['size']))

        send_telegram_message(
            f"✅ Binance position closed: {position['side']} {position['size']}"
        )
        return True

    except Exception as e:
        send_telegram_message(f"❌ Failed to close Binance position: {e}")
        return False


def close_bitget_position():
    """Close existing Bitget futures position"""
    try:
        position = get_bitget_futures_positions()
        if position['side'] == 'none' or position['size'] == 0:
            return True

        # Determine close side based on current position
        if position['side'] == 'long':
            close_side = 'close_long'
        elif position['side'] == 'short':
            close_side = 'close_short'
        else:
            return True

        # Close position using market order
        request_path = "/api/mix/v1/order/placeOrder"
        body = json.dumps({
            "symbol": bitget_symbol,
            "marginCoin": "USDT",
            "side": close_side,
            "orderType": "market",
            "size": str(position['size'])
        })
        headers = get_bitget_headers("POST", request_path, body)

        url = f"https://api.bitget.com{request_path}"
        response = requests.post(url, headers=headers, data=body, timeout=15)
        data = response.json()

        if data.get('code') == '00000':
            send_telegram_message(
                f"✅ Bitget position closed: {position['side']} {position['size']}"
            )
            return True
        else:
            send_telegram_message(f"❌ Failed to close Bitget position: {data}")
            return False

    except Exception as e:
        send_telegram_message(f"❌ Failed to close Bitget position: {e}")
        return False


def close_all_positions():
    """Close all existing positions on both exchanges"""
    global current_trade_state, last_action_time

    print("🔄 Closing all existing positions...")
    binance_closed = close_binance_position()
    bitget_closed = close_bitget_position()

    if binance_closed and bitget_closed:
        print("✅ All positions closed successfully")
        current_trade_state = "none"
        last_action_time = time.time()
        return True
    else:
        print("❌ Failed to close some positions")
        return False


def has_any_positions():
    """Check if there are any open positions on either exchange"""
    binance_position = get_binance_futures_position()
    bitget_position = get_bitget_futures_positions()

    return (binance_position['side'] != 'none'
            or bitget_position['side'] != 'none')


def can_enter_new_position():
    """Check if we can enter a new position based on state"""
    # Check if we already have active positions
    if current_trade_state != "none":
        return False

    # Check if there are any actual positions open
    if has_any_positions():
        return False

    return True


def execute_arbitrage_long_binance_short_bitget():
    """Execute arbitrage: Long Binance, Short Bitget"""
    global current_trade_state, last_action_time

    if not can_enter_new_position():
        print(
            "⚠️ Cannot enter new position - existing positions or cooldown active"
        )
        return False

    print("🚨 ARBITRAGE: Long Binance Futures, Short Bitget Futures")

    binance_success = buy_on_binance()  # Long on Binance
    bitget_success = sell_futures_on_bitget()  # Short on Bitget

    if binance_success and bitget_success:
        current_trade_state = "binance_long_bitget_short"
        last_action_time = time.time()
        send_telegram_message(
            "✅ Arbitrage executed: Longed Binance Futures, Shorted Bitget Futures"
        )
        return True
    else:
        # If one failed, try to close the successful one
        if binance_success:
            close_binance_position()
        if bitget_success:
            close_bitget_position()
        return False


def execute_arbitrage_short_binance_long_bitget():
    """Execute arbitrage: Short Binance, Long Bitget"""
    global current_trade_state, last_action_time

    if not can_enter_new_position():
        print(
            "⚠️ Cannot enter new position - existing positions or cooldown active"
        )
        return False

    print("🚨 ARBITRAGE: Short Binance Futures, Long Bitget Futures")

    binance_success = sell_on_binance()  # Short on Binance
    bitget_success = buy_futures_on_bitget()  # Long on Bitget

    if binance_success and bitget_success:
        current_trade_state = "binance_short_bitget_long"
        last_action_time = time.time()
        send_telegram_message(
            "✅ Arbitrage executed: Shorted Binance Futures, Longed Bitget Futures"
        )
        return True
    else:
        # If one failed, try to close the successful one
        if binance_success:
            close_binance_position()
        if bitget_success:
            close_bitget_position()
        return False


def check_balances():
    """Check if both exchanges have sufficient USDT balance for futures trading"""
    # Check if API keys are configured
    if binance_api_key == "YOUR_BINANCE_API_KEY" or not binance_api_key:
        print("❌ Binance API keys not configured!")
        return {'binance_can_trade': False, 'bitget_can_trade': False}

    if bitget_api_key == "YOUR_BITGET_API_KEY" or not bitget_api_key:
        print("❌ Bitget API keys not configured!")
        return {'binance_can_trade': False, 'bitget_can_trade': False}

    binance_usdt = get_usdt_balance()
    binance_position = get_binance_futures_position()
    bitget_futures_balance = get_bitget_futures_balance()
    bitget_position = get_bitget_futures_positions()

    print(
        f"💰 Binance Futures: {binance_usdt} USDT, Position: {binance_position['side']} {binance_position['size']}"
    )
    print(
        f"💰 Bitget Futures: {bitget_futures_balance} USDT, Position: {bitget_position['side']} {bitget_position['size']}"
    )

    # Check if we have enough USDT balance on both exchanges for futures trading
    has_binance_usdt = binance_usdt >= fixed_trade_amount
    has_bitget_usdt = bitget_futures_balance >= fixed_trade_amount

    return {
        'binance_can_trade': has_binance_usdt,
        'bitget_can_trade': has_bitget_usdt,
        'binance_position': binance_position,
        'bitget_position': bitget_position
    }


# =========================
# 🔁 MAIN LOOP
# =========================

print("🚀 Starting futures arbitrage bot...")

# Test API keys before starting
test_bitget_api_key()

while True:
    try:
        binance_price = get_binance_price()
        bitget_futures_price = get_bitget_futures_price()

        if not binance_price or not bitget_futures_price:
            print("⚠️ Skipping due to price fetch error.")
            continue

        # Calculate gap based on Binance as base
        gap = ((bitget_futures_price - binance_price) / binance_price) * 100
        print(
            f"📊 GAP: {gap:.2f}% | Binance: {binance_price} | Bitget Futures: {bitget_futures_price} | State: {current_trade_state}"
        )

        # Send Telegram notification when gap exceeds threshold
        if abs(gap) >= gap_threshold:
            gap_direction = "Bitget higher" if gap > 0 else "Binance higher"
            send_telegram_message(
                f"🚨 GAP ALERT: {gap:.2f}% ({gap_direction})\n"
                f"Binance: ${binance_price}\n"
                f"Bitget Futures: ${bitget_futures_price}\n"
                f"Threshold: {gap_threshold}%")

        # Check balances and positions on both exchanges
        balance_status = check_balances()

        # Check if we need to close positions due to gap reversal
        should_close_positions = False

        # Only close positions on true gap reversal, not minor fluctuations
        if current_trade_state == "binance_long_bitget_short" and gap <= -gap_threshold:  # Gap fully reversed
            should_close_positions = True
            print(
                f"🔄 Gap fully reversed for long Binance/short Bitget position: {gap:.2f}% <= -{gap_threshold}%"
            )
        elif current_trade_state == "binance_short_bitget_long" and gap >= gap_threshold:  # Gap fully reversed
            should_close_positions = True
            print(
                f"🔄 Gap fully reversed for short Binance/long Bitget position: {gap:.2f}% >= {gap_threshold}%"
            )

        # Close positions if needed
        if should_close_positions and current_trade_state != "none":
            if close_all_positions():
                send_telegram_message(
                    "🔄 Positions closed due to gap reversal/closure")

        # Only enter new positions if we don't have any existing ones
        if current_trade_state == "none" and can_enter_new_position():
            # 🚨 ARBITRAGE: Long Binance Futures, Short Bitget futures (when Bitget > Binance)
            if gap >= gap_threshold and balance_status[
                    'binance_can_trade'] and balance_status['bitget_can_trade']:
                execute_arbitrage_long_binance_short_bitget()

            # 🚨 ARBITRAGE: Short Binance Futures, Long Bitget futures (when Binance > Bitget)
            elif gap <= -gap_threshold and balance_status[
                    'binance_can_trade'] and balance_status['bitget_can_trade']:
                execute_arbitrage_short_binance_long_bitget()

        time.sleep(3)

    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user")
        break
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        time.sleep(3)
