from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import requests
import matplotlib.pyplot as plt
import datetime
import io
import nest_asyncio
import asyncio
import numpy as np

# --- Sabitler ---
BOT_TOKEN = "7684671214:AAFBDb6VmeEun8MvJkuKzVXACeBe5GoA3jo"

SYMBOL_TO_ID = {
    "btc": "bitcoin", "eth": "ethereum", "doge": "dogecoin", "sol": "solana",
    "ada": "cardano", "bnb": "binancecoin", "xrp": "ripple", "dot": "polkadot",
    "avax": "avalanche-2", "trx": "tron"
}

ID_TO_SYMBOL = {v: k.upper() for k, v in SYMBOL_TO_ID.items()}

# --- Coin ID bul ---
def get_coin_id_from_input(user_input: str):
    url = "https://api.coingecko.com/api/v3/coins/list"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            coins = r.json()
            user_input = user_input.lower()
            for coin in coins:
                if coin["symbol"].lower() == user_input or coin["id"].lower() == user_input:
                    return coin["id"]
            for coin in coins:
                if user_input in coin["id"].lower() or user_input in coin["symbol"].lower():
                    return coin["id"]
    except Exception as e:
        print(f"Coin listesi alınamadı: {e}")
    return None

# --- Coin verisi al ---
def get_coin_data(coin_id):
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}?localization=false&tickers=false&market_data=true"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            data = r.json()
            market_data = data.get('market_data', {})
            current_price = market_data.get('current_price', {})
            change_24h = market_data.get('price_change_percentage_24h')
            change_7d = market_data.get('price_change_percentage_7d')

            if current_price and change_24h is not None and change_7d is not None:
                price_usd = current_price.get('usd', None)
                price_try = current_price.get('try', None)
                symbol = ID_TO_SYMBOL.get(coin_id, data.get('symbol', '').upper())
                name = data.get('name', coin_id)

                suggestion = get_suggestion(change_24h, change_7d)
                prediction, probability = ai_prediction(change_24h, change_7d)

                return {
                    "symbol": symbol,
                    "name": name,
                    "price_usd": price_usd,
                    "price_try": price_try,
                    "change_24h": change_24h,
                    "change_7d": change_7d,
                    "suggestion": suggestion,
                    "ai_prediction": prediction,
                    "ai_probability": probability,
                }
    except Exception as e:
        print(f"Coin verisi alınamadı: {e}")
    return None

# --- Tahmin üret ---
def get_suggestion(change_24h, change_7d):
    if change_24h < -5 and change_7d < -5:
        return "📉 Şu anda düşüş trendinde, alım için dikkatli olun!"
    elif change_24h > 5 and change_7d > 5:
        return "🚀 Güçlü yükseliş trendi var, fırsat olabilir."
    elif change_24h < 0 and change_7d > 0:
        return "📈 Kısa vadede düşüş ama genel yön yukarı."
    elif change_24h > 0 and change_7d < 0:
        return "⚠️ Toparlanma var ama genel düşüşte."
    else:
        return "🤔 Nötr durumda, biraz beklemek mantıklı."

# --- Yapay Zeka benzeri tahmin ---
def ai_prediction(change_24h, change_7d):
    features = np.array([change_24h, change_7d])
    weighted = 0.4 * features[0] + 0.6 * features[1]
    prob = 1 / (1 + np.exp(-weighted))
    prediction = "📈 Bu coin yükseliş eğiliminde." if prob > 0.5 else "📉 Bu coin düşüş eğiliminde."
    return prediction, int(prob * 100)

# --- Binance linki kontrol et ---
def get_binance_url(coin_id):
    base_url = f"https://www.binance.com/en/trade/{coin_id.upper()}_USDT"
    return base_url

def is_coin_on_binance(symbol):
    try:
        url = f"https://api.binance.com/api/v3/exchangeInfo"
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            data = r.json()
            return any(s['symbol'] == f"{symbol.upper()}USDT" for s in data['symbols'])
    except Exception as e:
        print(f"Binance kontrolü başarısız: {e}")
    return False

# --- Grafik çiz ---
def get_price_history(coin_id, currency='usd'):
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
    params = {'vs_currency': currency, 'days': '7', 'interval': 'hourly'}
    r = requests.get(url, params=params, timeout=10)
    if r.status_code == 200:
        return r.json().get('prices', [])
    return []

def plot_graph(prices, coin_symbol):
    times = [datetime.datetime.fromtimestamp(p[0] / 1000) for p in prices]
    values = [p[1] for p in prices]
    plt.figure(figsize=(10, 4))
    plt.plot(times, values, color='blue')
    plt.title(f'{coin_symbol.upper()} - 7 Günlük Fiyat (USD)')
    plt.xlabel('Tarih')
    plt.ylabel('Fiyat ($)')
    plt.grid(True)
    plt.tight_layout()
    buffer = io.BytesIO()
    plt.savefig(buffer, format='png')
    buffer.seek(0)
    plt.close()
    return buffer

# --- /coin komutu ---
async def coin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Örn: /coin btc")
        return

    user_input = context.args[0].lower()
    coin_id = SYMBOL_TO_ID.get(user_input) or get_coin_id_from_input(user_input)
    if not coin_id:
        await update.message.reply_text("Coin bulunamadı.")
        return

    data = get_coin_data(coin_id)
    if not data:
        await update.message.reply_text("Veri alınamadı.")
        return

    text = f"""💰 {data['symbol']} / {data['name']} fiyatı:
• USD: ${data['price_usd']:.4f}
• TRY: ₺{data['price_try']:.4f}
📉 24 Saat: {data['change_24h']:.2f}%
📈 7 Gün: {data['change_7d']:.2f}%

🧠 Yapay Zeka Tahmin: {data['ai_prediction']}
📊 Yükselme İhtimali: %{data['ai_probability']}

💡 Yorum: {data['suggestion']}
⚠️ Bu yatırım tavsiyesi değildir."""

    # Binance butonu
    symbol = data['symbol'].upper()
    if is_coin_on_binance(symbol):
        url = get_binance_url(symbol)
        button = InlineKeyboardMarkup([[InlineKeyboardButton("🟢 Binance'de Hemen Al", url=url)]])
    else:
        button = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Binance'de Yok", callback_data="yok")]])

    await update.message.reply_text(text, reply_markup=button)

# --- /grafik komutu ---
async def grafik(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Örn: /grafik btc")
        return

    user_input = context.args[0].lower()
    coin_id = SYMBOL_TO_ID.get(user_input) or get_coin_id_from_input(user_input)
    if not coin_id:
        await update.message.reply_text("Coin bulunamadı.")
        return

    prices = get_price_history(coin_id)
    if not prices:
        await update.message.reply_text("Fiyat verisi alınamadı.")
        return

    image = plot_graph(prices, user_input)
    await update.message.reply_photo(photo=image, caption=f"{user_input.upper()} fiyat grafiği (7 gün)")

# --- Ana bot çalıştır ---
async def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("coin", coin))
    app.add_handler(CommandHandler("grafik", grafik))
    print("✅Bot çalışıyor...")
    await app.run_polling()

# --- Başlat ---
if __name__ == "__main__":
    nest_asyncio.apply()
    asyncio.run(main())
