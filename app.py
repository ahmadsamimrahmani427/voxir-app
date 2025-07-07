from flask import Flask, render_template, redirect, url_for, request, session, send_file, jsonify
from flask_dance.contrib.google import make_google_blueprint, google
import edge_tts
import asyncio
import os
import paypalrestsdk
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

app = Flask(__name__)
app.secret_key = "your-secret-key"

paypalrestsdk.configure({
    "mode": "live",
    "client_id": "BAAPhnx7VkJgKOMM9B-Jowx06XDwRhrIeKIewOZBdKWJtkEDalPgw9vj6xw5Xi21YTIChXHr00JATIbVqY",
    "client_secret": "ECQhDhRs-bMYbcVfOkfqIpS8ZizF5S6YPNRXlRdmbc00u7XfdacA0nXOpPuTbOpiG5Fb6DWGrt0lBZ9S"
})

GOOGLE_CLIENT_ID = "786899786922-vu682l6h78vlc1ab1gh3jq0ffjlmrugo.apps.googleusercontent.com"
GOOGLE_CLIENT_SECRET = "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"

google_bp = make_google_blueprint(
    client_id=GOOGLE_CLIENT_ID,
    client_secret=GOOGLE_CLIENT_SECRET,
    scope=["profile", "email"],
    redirect_url="/login/google/authorized"
)
app.register_blueprint(google_bp, url_prefix="/login")

LANGUAGES = {
    "فارسی": "fa-IR-DilaraNeural",
    "انگلیسی": "en-US-AriaNeural",
    "آلمانی": "de-DE-KatjaNeural",
    "فرانسوی": "fr-FR-DeniseNeural",
    "اسپانیایی": "es-ES-ElviraNeural"
}

analyzer = SentimentIntensityAnalyzer()

def is_logged_in():
    return google.authorized or session.get("email")

@app.context_processor
def inject_google():
    return dict(google=google)

@app.route('/')
def welcome():
    return render_template("welcome.html")

@app.route('/login', methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        if email and password:
            session["email"] = email
            return redirect(url_for("app_main"))

    if google.authorized:
        resp = google.get("/oauth2/v2/userinfo")
        if resp.ok:
            session["email"] = resp.json().get("email")
            return redirect(url_for("app_main"))

    return render_template("login.html")

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for("welcome"))

@app.route('/app')
def app_main():
    if not is_logged_in():
        return redirect(url_for("login"))
    email = session.get("email", "کاربر")
    free_uses = 1
    plans = [
        {"name": "پلن رایگان", "price": "رایگان", "features": ["۳ استفاده رایگان"], "id": "free"},
        {"name": "پلن ۳ ماهه حرفه‌ای", "price": "۳ دلار", "features": ["استفاده نامحدود", "پشتیبانی ویژه"], "id": "pro"},
    ]
    return render_template(
        "index.html",
        email=email,
        languages=LANGUAGES,
        free_uses=free_uses,
        plans=plans
    )

@app.route('/create_payment', methods=['POST'])
def create_payment():
    if not is_logged_in():
        return redirect(url_for("login"))

    plan_id = request.form.get("plan_id")
    if plan_id not in ["free", "pro"]:
        return "پلن نامعتبر است", 400

    if plan_id == "free":
        return redirect(url_for("app_main"))

    amount = "3.00"

    payment = paypalrestsdk.Payment({
        "intent": "sale",
        "payer": {
            "payment_method": "paypal"
        },
        "redirect_urls": {
            "return_url": url_for('payment_execute', _external=True),
            "cancel_url": url_for('payment_cancel', _external=True)
        },
        "transactions": [{
            "item_list": {
                "items": [{
                    "name": "پلن ۳ ماهه حرفه‌ای",
                    "sku": plan_id,
                    "price": amount,
                    "currency": "USD",
                    "quantity": 1
                }]
            },
            "amount": {
                "total": amount,
                "currency": "USD"
            },
            "description": "خرید پلن ۳ ماهه حرفه‌ای"
        }]
    })

    if payment.create():
        for link in payment.links:
            if link.rel == "approval_url":
                return redirect(link.href)
        return "خطا در دریافت لینک پرداخت", 500
    else:
        print("خطا در ساخت پرداخت:", payment.error)
        return f"خطا در ساخت پرداخت: {payment.error}", 500

@app.route('/payment/execute')
def payment_execute():
    payment_id = request.args.get('paymentId')
    payer_id = request.args.get('PayerID')

    payment = paypalrestsdk.Payment.find(payment_id)

    if payment.execute({"payer_id": payer_id}):
        return "پرداخت با موفقیت انجام شد. متشکریم!"
    else:
        print("خطا در تایید پرداخت:", payment.error)
        return f"خطا در تایید پرداخت: {payment.error}", 400

@app.route('/payment/cancel')
def payment_cancel():
    return "پرداخت لغو شد."

@app.route('/tts', methods=['POST'])
def tts():
    if not is_logged_in():
        return {"error": "لطفا وارد شوید."}, 403

    data = request.get_json()
    text = data.get('text', '')
    voice = data.get('voice', 'fa-IR-DilaraNeural')

    if not text.strip():
        return {"error": "متن خالی است."}, 400

    output_path = "output.mp3"
    if os.path.exists(output_path):
        os.remove(output_path)

    # تحلیل احساسات برای تعیین آیکن (ولی مود صدای خاص نمی‌دهیم چون edge-tts نسخه قدیمی)
    scores = analyzer.polarity_scores(text)
    compound = scores.get('compound', 0)
    if compound >= 0.05:
        sentiment_icon = '😊'
    elif compound <= -0.05:
        sentiment_icon = '😞'
    else:
        sentiment_icon = '😐'

    async def synthesize():
        communicate = edge_tts.Communicate(text, voice)  # بدون style
        await communicate.save(output_path)

    try:
        asyncio.run(synthesize())
    except Exception as e:
        print("❌ Error generating sound:", e)
        return {"error": "خطا در تولید صدا."}, 500

    # می‌تونیم آیکن احساسات رو هم برگردونیم اگر خواستی از جاوااسکریپت نمایش بدی
    return {"audio_url": "/audio/output.mp3", "sentiment_icon": sentiment_icon}

@app.route('/audio/<path:filename>')
def serve_audio(filename):
    return send_file(filename, mimetype='audio/mpeg')

@app.route('/download')
def download():
    if not is_logged_in():
        return redirect(url_for("login"))
    if not os.path.exists("output.mp3"):
        return "فایل یافت نشد", 404
    return send_file("output.mp3", as_attachment=True)

@app.route('/sentiment', methods=['POST'])
def sentiment():
    data = request.get_json()
    text = data.get('text', '')

    if not text.strip():
        return jsonify({"error": "متن خالی است."})

    scores = analyzer.polarity_scores(text)
    return jsonify(scores)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=3000, debug=True)
