@app.route('/create_payment', methods=['POST'])
def create_payment():
    if not is_logged_in():
        return redirect(url_for("login"))

    plan_id = request.form.get("plan_id")
    plan = PLANS.get(plan_id)

    if not plan:
        return "Invalid plan selected", 400

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
                    "name": plan["name"],
                    "sku": plan_id,
                    "price": plan["price"],
                    "currency": "USD",
                    "quantity": 1
                }]
            },
            "amount": {
                "total": plan["price"],
                "currency": "USD"
            },
            "description": f"Purchase of {plan['name']}"
        }]
    })

    if payment.create():
        for link in payment.links:
            if link.rel == "approval_url":
                return redirect(link.href)
        return "Error: no approval URL found", 500
    else:
        return f"Payment creation error: {payment.error}", 500
