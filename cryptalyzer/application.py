import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True


# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure SQLite database
db = SQL("sqlite:///crypto.db")

# Make sure API key is set
#if not os.environ.get("API_KEY"):
#    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    current_user = db.execute("SELECT * FROM users WHERE id = ?;", session["user_id"])
    cash_reserve = round(current_user[0]['cash'], 2)

    # Get current user's currently owned coins
    rows = db.execute("SELECT name, symbol, sum(quantity) as sum_of_quantity FROM transactions WHERE user_id = ? GROUP BY user_id, name, symbol HAVING sum_of_quantity > 0", session["user_id"])

    # Get current price of each coin
    rows = [dict(x, **{'price': lookup(x['symbol'])['price']}) for x in rows]

    # Calcuate value for each coin
    rows = [dict(x, **{'total': x['price']*x['sum_of_quantity']}) for x in rows]

    total = cash_reserve + sum([x['total'] for x in rows])

    return render_template("index.html", cash_reserve=cash_reserve, rows=rows, total=total)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Expand coin acronyms to full names"""
    cryptocoins = {"BTC": "Bitcoin",
                   "ETH": "Ethereum",
                   "LTC": "Litecoin",
                   "DOGE": "Dogecoin",
                   "DASH": "DASH",
                   "SHIB": "Shiba Inu Coin",
                   "SOL": "Solana",
                   "USDT": "Tether Coin",
                   "XRP": "Ripple",
                   "TCRV": "TradeCurve",
                   "BNB": "Binance Coin"}

    """Buy different crypto coins"""
    if request.method == "POST":

        # Ensure symbol and quantity are entered
        if not (request.form.get("Symbol") and request.form.get("Quantity")):
            return apology("Missing value", 403)

        # Ensure quantity are not fractional, negative, and non-numeric
        temp = request.form.get("Quantity").isdigit()
        try:
            quantity = int(temp)
            if quantity < 1:
                return apology("Invalid", 400)
        except ValueError:
            return apology("Invalid", 400)

        # Ensure symbol is valid and convert symbol to full name
        a = request.form.get("Symbol")
        check_symbol = lookup(a)
        coinname = cryptocoins[a.upper()]
        if a.upper() not in cryptocoins:
            coinname = a.upper()
        if not check_symbol:
            return apology("Invalid", 400)

        current_id = session["user_id"]
        current_cash = db.execute("SELECT cash FROM users WHERE id = ?", current_id)
        symb = request.form.get("Symbol")
        returned_price = lookup(symb)
        qty = request.form.get("Quantity")
        amount_requested = int(qty) * returned_price["price"]
        print(amount_requested)
        reduced_cash = int(current_cash[0]["cash"]) - amount_requested

        # Ensure user has sufficient funds before purchase
        if (current_cash[0]["cash"] < amount_requested):
            return apology("No sufficient funds", 403)

        # Go ahead and buy the coins
        else:
            # Deduct amount from user's current cash holdings
            db.execute("UPDATE users SET cash = ? WHERE id = ?", reduced_cash, current_id)

            # Add coins to user's portfolio
            db.execute("INSERT INTO transactions(user_id, name, symbol, quantity, price) VALUES(?, ?, ?, ?, ?)", session["user_id"], coinname, symb, qty, returned_price["price"])

            flash("Crypto Just Bought!")
            return redirect("/")
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    current_id = session["user_id"]
    rows = db.execute("SELECT * FROM transactions WHERE user_id = ? ORDER BY transacted", current_id)
    return render_template("history.html", rows=rows)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":
        if not request.form.get("Symbol"):
            return apology("Enter a symbol", 400)
        symb = request.form.get("Symbol")
        returned_symbol = lookup(symb)
        if not returned_symbol:
            return apology("Invalid", 400)
        else:
            return render_template("quote.html", returned_symbol=returned_symbol)
    else:
        return render_template("quoted.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Ensure password was submitted
        if not request.form.get("password"):
            return apology("must provide password", 400)

        # Ensure password is re-entered
        if not request.form.get("confirmation"):
            return apology("must re-enter password", 400)

        if (request.form.get("password")) != (request.form.get("confirmation")):
            return apology("passwords don't match", 400)

        # Check if username is already taken
        new_username = (request.form.get("username"))
        duplicate_names = db.execute("SELECT * FROM users WHERE username = ?", new_username)
        if len(duplicate_names) != 0:
            return apology("Username taken", 400)

        # Add user to database
        else:
            username = (request.form.get("username"))
            password = generate_password_hash(request.form.get("confirmation"))
            db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", username, password)

        # Redirect user to home page
        flash("You've registered successsfully! Login")
        return redirect("/")

    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():

    cryptocoins = {"BTC": "Bitcoin",
                   "ETH": "Ethereum",
                   "LTC": "Litecoin",
                   "DOGE": "Dogecoin",
                   "DASH": "DASH",
                   "SHIB": "Shiba Inu Coin",
                   "SOL": "Solana",
                   "USDT": "Tether Coin",
                   "XRP": "Ripple",
                   "TCRV": "TradeCurve",
                   "BNB": "Binance Coin"}

    """Sell crpto coins"""
    owned_symbols = db.execute("SELECT symbol, sum(quantity) as sum_of_quantity FROM transactions WHERE user_id = ? GROUP BY user_id, symbol HAVING sum_of_quantity > 0", session["user_id"])

    if request.method == "POST":
        if not request.form.get("Symbol"):
            return apology("Invalid", 400)

        if not request.form.get("Quantity"):
            return apology("Invalid", 400)

        quantity = request.form.get("Quantity")
        try:
            quantity = int(quantity)
            if quantity < 1:
                return apology("Invalid", 400)
        except ValueError:
            return apology("Invalid", 400)

        symbol = request.form.get("Symbol")

        symbols_dict = {element['symbol']: element['sum_of_quantity'] for element in owned_symbols}
        if symbols_dict[symbol] < int(quantity):
            return apology("You don't own so many coins", 400)

        ongoing_price = lookup(symbol)

        # Get user's cash reserves
        rows = db.execute("SELECT * FROM users WHERE id = ?", session["user_id"])

        # Go ahead and sell the user's coins
        db.execute("INSERT INTO transactions(user_id, name, symbol, quantity, price) VALUES(?, ?, ?, ?, ?)", session["user_id"], cryptocoins[symbol.upper()], symbol, -int(quantity), ongoing_price["price"])

        # Add cash back into user's account
        updated_cash = rows[0]["cash"] + (ongoing_price["price"] * int(quantity))
        db.execute("UPDATE users SET cash = ? WHERE id = ?", updated_cash, session["user_id"])

        flash("You Just Sold Crypto Coins!")
        return redirect("/")

    else:
        return render_template("sell.html", symbols=owned_symbols)


@app.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    """Allow user to change password"""
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure old password was submitted
        elif not request.form.get("old-password"):
            return apology("must provide old password", 403)

        # Ensure new password 1 was submitted
        elif not request.form.get("new-password1"):
            return apology("must provide new password", 403)

        # Ensure new password 2 was submitted
        elif not request.form.get("new-password2"):
            return apology("must re-enter new password", 403)

        # Check if both new passwords match
        elif (request.form.get("password1")) != (request.form.get("password2")):
            return apology("New passwords don't match", 403)

        # Check username & old password against database
        usn = (request.form.get("username"))
        pwd = generate_password_hash(request.form.get("old-password"))
        user = db.execute("SELECT * FROM users WHERE username = ?", usn)
        if len(user) != 1 or not check_password_hash(user[0]["hash"], request.form.get("old-password")):
            return apology("invalid username and/or password", 403)

        # Change password
        else:
            usn = (request.form.get("username"))
            new_pwd = generate_password_hash(request.form.get("new-password2"))
            db.execute("UPDATE users SET hash = ? WHERE username = ?", new_pwd, usn)
            flash("Your password changed was changed successfully!")
            return render_template("pwdchanged.html")
    else:
        return render_template("change-password.html")


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)