from flask import Flask, render_template, redirect, url_for, request, session, send_file, jsonify
from flask_dance.contrib.google import make_google_blueprint, google
import edge_tts
import asyncio
import os
import paypalrestsdk

app = Flask(__name__)
app.secret_key = "your-secret-key"

GOOGLE_CLIENT_ID = "786899786922-vu682l6h78vlc1ab1gh3jq0ffjlmrugo.apps.googleusercontent.com"
GOOGLE_CLIENT_SECRET = "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"

paypalrestsdk.configure({
    "mode": "sandbox",
    "client_id": "AVOqX9uegnvQoz6cpoxezjEhv_P1ljaHCq1tt_xSSg_DtEP976IaMzsjGf5OGdttuYUawR21q1H0L2cE",
    "client_secret": "EH_IHMgTO6hOFa13s4PxWE5vhAiLhT-zWpVAl5kAvp4S_iNDK1E9fq1lQF7ASH-a2cTlNTP40OsZm1_j"
})

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
            # مقداردهی اولیه تعداد استفاده رایگان
            session.setdefault("free_uses", 3)
            session["paid"] = False
            return redirect(url_for("app_main"))

    if google.authorized:
        resp = google.get("/oauth2/v2/userinfo")
        if resp.ok:
            session["email"] = resp.json().get("email")
            session.setdefault("free_uses", 3)
            session["paid"] = False
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
    free_uses = session.get("free_uses", 3)
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
        free_uses = session.get("free_uses", 3)
        if free_uses > 0:
            session["free_uses"] = free_uses - 1
            return redirect(url_for("app_main"))
        else:
            return "استفاده رایگان شما به پایان رسیده است. لطفاً پلن حرفه‌ای را خریداری کنید.", 403

    amount = "3.00"  # قیمت ۳ دلار

    payment = paypalrestsdk.Payment({
        "intent": "sale",
        "payer": {"payment_method": "paypal"},
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
            "amount": {"total": amount, "currency": "USD"},
            "description": "خرید پلن ۳ ماهه حرفه‌ای"
        }]
    })

    if payment.create():
        for link in payment.links:
            if link.rel == "approval_url":
                return redirect(link.href)
        return "خطا در دریافت لینک پرداخت", 500
    else:
        return f"خطا در ساخت پرداخت: {payment.error}", 500

@app.route('/payment/execute')
def payment_execute():
    payment_id = request.args.get('paymentId')
    payer_id = request.args.get('PayerID')

    payment = paypalrestsdk.Payment.find(payment_id)

    if payment.execute({"payer_id": payer_id}):
        session["paid"] = True
        return "پرداخت با موفقیت انجام شد. متشکریم!"
    else:
        return f"خطا در تایید پرداخت: {payment.error}", 400

@app.route('/payment/cancel')
def payment_cancel():
    return "پرداخت لغو شد."

@app.route('/tts', methods=['POST'])
def tts():
    if not is_logged_in():
        return jsonify({"error": "لطفا وارد شوید."}), 403

    data = request.get_json()
    text = data.get('text', '')
    voice = data.get('voice', 'fa-IR-DilaraNeural')

    if not text.strip():
        return jsonify({"error": "متن خالی است."}), 400

    free_uses = session.get("free_uses", 3)
    paid = session.get("paid", False)

    if not paid and free_uses <= 0:
        return jsonify({"error": "استفاده رایگان به پایان رسیده است. لطفاً پلن حرفه‌ای را خریداری کنید."}), 403

    output_path = "output.mp3"
    if os.path.exists(output_path):
        os.remove(output_path)

    async def synthesize():
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(output_path)

    asyncio.run(synthesize())

    if not paid:
        session["free_uses"] = free_uses - 1

    return jsonify({"audio_url": "/audio/output.mp3"})

@app.route('/audio/<path:filename>')
def serve_audio(filename):
    if not is_logged_in():
        return redirect(url_for("login"))
    return send_file(filename, mimetype='audio/mpeg')

@app.route('/download')
def download():
    if not is_logged_in():
        return redirect(url_for("login"))
    if not os.path.exists("output.mp3"):
        return "فایل یافت نشد", 404
    return send_file("output.mp3", as_attachment=True)

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 3000))
    app.run(host='0.0.0.0', port=port, debug=True)
