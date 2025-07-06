from flask import Flask, render_template, redirect, url_for, request, session
import paypalrestsdk

app = Flask(__name__)
app.secret_key = "your-secret-key"

# پیکربندی پی‌پال (Sandbox یا Live)
paypalrestsdk.configure({
    "mode": "sandbox",  # یا "live"
    "client_id": "اینجا Client ID را وارد کن",
    "client_secret": "اینجا Client Secret را وارد کن"
})

@app.route('/')
def index():
    return render_template("index.html")  # صفحه‌ای که دکمه خرید دارد

@app.route('/create_payment', methods=['POST'])
def create_payment():
    amount = "3.00"  # قیمت پلن به دلار

    payment = paypalrestsdk.Payment({
        "intent": "sale",
        "payer": {
            "payment_method": "paypal"
        },
        "redirect_urls": {
            "return_url": url_for('execute_payment', _external=True),
            "cancel_url": url_for('cancel_payment', _external=True)
        },
        "transactions": [{
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
        return f"خطا در ساخت پرداخت: {payment.error}", 500

@app.route('/execute')
def execute_payment():
    payment_id = request.args.get('paymentId')
    payer_id = request.args.get('PayerID')

    payment = paypalrestsdk.Payment.find(payment_id)

    if payment.execute({"payer_id": payer_id}):
        return "پرداخت با موفقیت انجام شد. متشکریم!"
    else:
        return f"خطا در تایید پرداخت: {payment.error}", 400

@app.route('/cancel')
def cancel_payment():
    return "پرداخت لغو شد."

if __name__ == "__main__":
    app.run(debug=True)
