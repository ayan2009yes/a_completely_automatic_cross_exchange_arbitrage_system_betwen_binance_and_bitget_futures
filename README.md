# Binance ↔ Bitget Futures Arbitrage Bot

This bot performs **cross-exchange futures arbitrage** between **Binance Futures** and **Bitget Futures** on the same trading pair.  
It detects **price gaps** between the exchanges and opens **hedged long/short positions** to lock in profit.

The bot also:
- Monitors price difference (gap)
- Automatically opens arbitrage trades when threshold is reached
- Automatically closes trades when gap reverses
- Sends real-time alerts & trade logs to **Telegram**

---

## ⚠️ IMPORTANT WARNING

### **Before running the bot:**
- **Replace all placeholder API keys** with your actual ones.
- **Never share this script with your real keys included.**
- **Use this at your own risk.**
- Start with **low amounts** until fully tested.

---

## 📦 Requirements

Install required dependencies:

```bash
pip install python-binance requests pycryptodome
🔧 Configuration (edit in botx.py)
python
Copy code
# BINANCE API
binance_api_key = "YOUR_BINANCE_API_KEY"
binance_api_secret = "YOUR_BINANCE_API_SECRET"

# BITGET API
bitget_api_key = "YOUR_BITGET_API_KEY"
bitget_api_secret = "YOUR_BITGET_API_SECRET"
bitget_api_passphrase = "YOUR_BITGET_API_PASSPHRASE"

# TELEGRAM
telegram_token = "YOUR_TELEGRAM_BOT_TOKEN"
telegram_chat_id = "YOUR_CHAT_ID"

# TRADING SETTINGS
symbol = "CATIUSDT"                # Binance futures symbol
bitget_symbol = "CATIUSDT_UMCBL"   # Bitget futures symbol
gap_threshold = 0.3                # Gap % to trigger trades
fixed_trade_amount = Decimal('6.5')  # USD size per trade
⚙️ How The Bot Works
Condition	Action
Bitget price > Binance price by gap %	Long Binance, Short Bitget
Binance price > Bitget price by gap %	Short Binance, Long Bitget
Gap reverses back	Close both positions

This ensures:

Zero net exposure to price movement

Profit comes from price convergence

▶️ How to Run
bash
Copy code
python botx.py
The bot will:

Start monitoring price differences every 3 seconds

Print live status in terminal

Send trade alerts to Telegram

💡 Recommended Safety Practices
Use isolated margin mode on both exchanges.

Start with very small trade sizes.

Monitor executions manually during initial runs.

Avoid running during extremely volatile markets.

🏁 Example Telegram Notifications
yaml
Copy code
🚨 GAP ALERT: 0.42% (Bitget higher)
Binance: $0.00124
Bitget Futures: $0.00129
Threshold: 0.30%

✅ Arbitrage executed: Longed Binance, Shorted Bitget

🔄 Positions closed due to gap reversal
📝 License
This project is for educational purposes only.
Use at your own risk. No warranty or liability provided.

