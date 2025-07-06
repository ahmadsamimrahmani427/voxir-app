from flask import Flask, render_template, redirect, url_for, request, session, send_file, jsonify
import paypalrestsdk
import os
import edge_tts
import asyncio

app = Flask(__name__)
app.secret_key = "your-secret-key"  # کلید امن خودت را قرار بده

# پیکربندی پی‌پال (Sandbox یا Live)
paypalrestsdk.configure({
    "mode": "sandbox",  # یا "live"
    "client_id": "اینجا Client ID پی‌پال خودت را قرار بده",
    "client_secret": "اینجا Client Secret پی‌پال خودت را قرار بده"
})

# شبیه‌سازی ورود کاربر (برای نمونه)
def is_logged_in():
    return "email" in session

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        if email:
            session["email"] = email
            session["free_uses"] = 0
            return redirect(url_for('app_main'))
    return '''
    <form method="POST">
        ایمیل: <input name="email" type="email" required>
        <button type="submit">ورود</button>
    </form>
    '''

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/')
def welcome():
    if not is_logged_in():
        return redirect(url_for('login'))
    return redirect(url_for('app_main'))

@app.route('/app')
def app_main():
    if not is_logged_in():
        return redirect(url_for('login'))

    email = session.get("email")
    free_uses = session.get("free_uses", 0)

    plans = [
        {"name": "پلن رایگان", "price": "رایگان", "features": ["۳ استفاده رایگان"], "id": "free"},
        {"name": "پلن ۳ ماهه حرفه‌ای", "price": "۳ دلار", "features": ["استفاده نامحدود", "پشتیبانی ویژه"], "id": "pro"},
    ]

    languages = {
        "فارسی": "fa-IR-DilaraNeural",
        "انگلیسی": "en-US-AriaNeural",
        "آلمانی": "de-DE-KatjaNeural",
        "فرانسوی": "fr-FR-DeniseNeural",
        "اسپانیایی": "es-ES-ElviraNeural"
    }

    return render_template(
        "index.html",
        email=email,
        free_uses=free_uses,
        plans=plans,
        languages=languages
    )

@app.route('/create_payment', methods=['POST'])
def create_payment():
    if not is_logged_in():
        return redirect(url_for('login'))

    plan_id = request.form.get("plan_id")
    if plan_id not in ["free", "pro"]:
        return "پلن نامعتبر است", 400

    if plan_id == "free":
        # افزایش استفاده رایگان (نمونه)
        session["free_uses"] = session.get("free_uses", 0) + 1
        return redirect(url_for('app_main'))

    # مبلغ پلن حرفه‌ای
    amount = "3.00"

    payment = paypalrestsdk.Payment({
        "intent": "sale",
        "payer": {"payment_method": "paypal"},
        "redirect_urls": {
            "return_url": url_for('payment_execute', _external=True),
            "cancel_url": url_for('payment_cancel', _external=True)
        },
        "transactions": [{
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
    text = data.get('text', '').strip()
    voice = data.get('voice', 'fa-IR-DilaraNeural')

    if not text:
        return jsonify({"error": "متن خالی است."}), 400

    output_path = "output.mp3"
    if os.path.exists(output_path):
        os.remove(output_path)

    async def synthesize():
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(output_path)

    asyncio.run(synthesize())
    return jsonify({"audio_url": "/audio/output.mp3"})

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

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=3000, debug=True)
