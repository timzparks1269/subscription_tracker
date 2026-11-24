import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session
from tracker import (
    init_db,
    create_user,
    verify_user,
    load_subscriptions,
    add_subscription,
    update_subscription,
    delete_subscription,
    calculate_monthly_total,
    get_days_until_due,
)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key-change-later")
init_db()


@app.route("/")
def index():
    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]
    subscriptions = load_subscriptions(user_id)
    for sub in subscriptions:
        sub["days_left"] = get_days_until_due(sub["next_date"])

    subscriptions.sort(key=lambda item: item["days_left"])

    monthly_total = calculate_monthly_total(subscriptions)
    yearly_total = round(monthly_total * 12, 2)
    trial_count = sum(1 for sub in subscriptions if sub.get("is_trial", False))

    edit_id = request.args.get("edit", type=int)
    edit_sub = next((s for s in subscriptions if s["id"] == edit_id), None)

    return render_template(
        "index.html",
        username=session["username"],
        subscriptions=subscriptions,
        monthly_total=monthly_total,
        yearly_total=yearly_total,
        trial_count=trial_count,
        edit_sub=edit_sub,
    )


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        action = request.form.get("action")
        username = request.form["username"]
        password = request.form["password"]

        if action == "register":
            ok, msg = create_user(username, password)
            if not ok:
                error = msg
            else:
                user = verify_user(username, password)
                session["user_id"] = user["id"]
                session["username"] = user["username"]
                return redirect(url_for("index"))
        else:
            user = verify_user(username, password)
            if user:
                session["user_id"] = user["id"]
                session["username"] = user["username"]
                return redirect(url_for("index"))
            else:
                error = "Invalid username or password."

    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/add", methods=["POST"])
def add():
    if "user_id" not in session:
        return redirect(url_for("login"))

    add_subscription(
        session["user_id"],
        request.form["name"],
        request.form["price"],
        request.form["cycle"],
        request.form["next_date"],
        "is_trial" in request.form,
    )
    return redirect(url_for("index"))


@app.route("/edit/<int:sub_id>", methods=["POST"])
def edit(sub_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    update_subscription(
        session["user_id"],
        sub_id,
        request.form["name"],
        request.form["price"],
        request.form["cycle"],
        request.form["next_date"],
        "is_trial" in request.form,
    )
    return redirect(url_for("index"))


@app.route("/delete/<int:sub_id>", methods=["POST"])
def delete(sub_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    delete_subscription(session["user_id"], sub_id)
    return redirect(url_for("index"))

@app.route("/quick-add", methods=["GET", "POST"])
def quick_add():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        add_subscription(
            session["user_id"],
            request.form["name"],
            request.form["price"],
            request.form["cycle"],
            request.form["next_date"],
            "is_trial" in request.form,
        )
        return render_template("quick_saved.html", name=request.form["name"])

    prefill_name = request.args.get("name", "")
    prefill_price = request.args.get("price", "")
    default_date = datetime.now().date().strftime("%Y-%m-%d")
    return render_template(
        "quick_add.html",
        name=prefill_name,
        price=prefill_price,
        default_date=default_date,
    )
if __name__ == "__main__":
    app.run(debug=True, port=5001)