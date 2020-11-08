import os
import cs50
from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session, url_for
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash
from collections import OrderedDict
from sortedcontainers import SortedDict
import collections
from flask_mail import Mail
from flask_mail import Message
import smtplib
import csv

from helpers import login_required, lookup, usd

# Configure application
app = Flask(__name__)


app.config["TEMPLATES_AUTO_RELOAD"] = True

app.config["MAIL_SERVER"] = 'smtp.gmail.com'
app.config["MAIL_PORT"] = 465
app.config["MAIL_USE_TLS"] = False
app.config["MAIL_USE_SSL"] = True
app.config["MAIL_USERNAME"] = 'le.stock.simulator@gmail.com'
app.config["MAIL_DEFAULT_SENDER"] = ('LE Stock Simulator', 'le.stock.simulator@gmail.com')
app.config["MAIL_PASSWORD"] = 'pass'
app.config["MAIL_DEBUG"] = True
app.config["TESTING"] = False
app.config["MAIL_SUPPRESS_SEND"] = False


mail = Mail(app)

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

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")



@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    user = db.execute("SELECT cash FROM users WHERE id =:user", user = session["user_id"])
    stocks = db.execute("SELECT Symbol, SUM(Shares) as total_shares FROM transactions WHERE user_id = :user_id GROUP BY Symbol HAVING total_shares > 0", user_id=session["user_id"])
    quotes = {}
    total = 0
    for stock in stocks:
        quotes[stock["Symbol"]] = lookup(stock["Symbol"])
        total = total + quotes[stock["Symbol"]]["price"] * stock["total_shares"]

    cash_remaining = user[0]["cash"]
    total = total + cash_remaining



    return render_template("index.html", quotes=quotes, stocks=stocks, total= total, cash_remaining=cash_remaining)

@app.route("/friends", methods=["GET", "POST"]) #can phai them ca phan überprüfen xem co ton tai friend hay ko
@login_required
def friends():
    if request.method == "GET":
        return render_template("friends.html")

    if request.method == "POST":
        username = request.form.get("username")
        rows = db.execute("SELECT * FROM users WHERE id = :user_id",
                          user_id = session["user_id"])
        mainuser = rows[0]["username"]
        newfriend = db.execute("SELECT * FROM users WHERE username = :username", username = username)
        friends_id = newfriend[0]["id"]
        db.execute("INSERT INTO friendstable (mainuser, friends, friends_id) VALUES (:mainuser, :friends, :friends_id)", mainuser = mainuser, friends = username, friends_id = friends_id)


        msg = Message("New Friend Added", recipients=[rows[0]["email"]])
        msg.html = render_template('mail-friend.html',
                    username=rows[0]["name"] ,
                    friendname = newfriend[0]["name"],
                    friend = username)
        mail.send(msg)

        flash("Successfuly added new friend")
        return render_template("friends.html")

@app.route("/ranking", methods =["GET"])
@login_required
def ranking():
    rows = db.execute("SELECT * FROM users WHERE id = :user_id",
                          user_id = session["user_id"])
    mainuser = rows[0]["username"]
    ranking = db.execute("SELECT friends, friends_id FROM friendstable WHERE mainuser = :mainuser", mainuser = mainuser)
    #stocks = db.execute("SELECT user_id, Symbol, SUM(Shares) as total_shares FROM transactions INNER JOIN friendstable ON transactions.user_id = friendstable.friends_id")


    endrank1 = list() #list for name
    endrank2 = list() #list for money

    for a in ranking:
        gewinn = 0
        stocks = db.execute("SELECT Symbol, SUM(Shares) as total_shares FROM transactions WHERE user_id = :friends_id GROUP BY Symbol", friends_id = a["friends_id"])
        for stock in stocks:
            ashare = lookup(stock["Symbol"])
            gewinn = gewinn + ashare["price"] * stock["total_shares"]

        row = db.execute("SELECT username, cash FROM users WHERE username = :username", username = a["friends"])
        endrank1.append(row[0]["username"])
        total = row[0]["cash"] + gewinn
        endrank2.append(total)

    endrank = dict(zip(endrank1, endrank2))
    jojo = sorted(endrank.items(), key=lambda value: value[1])
    jaja = reversed(jojo)
    endrank = dict(jaja)

    return render_template("ranking.html", name = mainuser, endrank = endrank)


















@app.route("/buy", methods=["GET", "POST"]) #con bug o cai symbol khong chiu len xuong
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        if not request.form.get("symbol"):
            flash("Please input ticket symbol")
            return redirect(url_for("buy"))
        if not request.form.get("shares"):
            flash("Please input number of shares you want to buy")
            return redirect(url_for("buy"))

        try:
            number = int(request.form.get("shares"))
        except:
            flash("A number must be provided, please try again")
            return redirect(url_for("buy"))

        if number < 0:
            flash("A positive number must be provided, please try again")
            return redirect(url_for("buy"))

        try:
            share = lookup(request.form.get("symbol"))
        except:
            flash("This company is at the moment not available on our platform, please try again")
            return redirect(url_for("buy"))

        if share == None:
            flash("This company is at the moment not available on our platform, please try again")
            return redirect(url_for("buy"))

        rows = db.execute("SELECT * FROM users WHERE id = :user", user=session["user_id"])

        vor = rows[0]["cash"]
        pps = -(share["price"])
        verlust = pps * number

        if vor < verlust:
            flash("Not enough cash for this transaction, please try again")
            return redirect(url_for("buy"))

        db.execute("UPDATE users SET cash = cash + :verlust WHERE id = :user", verlust = verlust, user = session["user_id"])
        db.execute("INSERT INTO transactions (user_id, Symbol, Company, Shares, pps, Total) VALUES (:user_id, :symbol, :company, :shares, :pricepershare, :total)",
                    symbol = share["symbol"],
                    company = share["name"],
                    shares = number,
                    pricepershare = pps,
                    total = verlust,
                    user_id = session["user_id"]
                    )
        user = db.execute("SELECT cash FROM users WHERE id =:user", user = session["user_id"])
        stocks = db.execute("SELECT Symbol, SUM(Shares) as total_shares FROM transactions WHERE user_id = :user_id GROUP BY Symbol HAVING total_shares > 0", user_id=session["user_id"])
        quotes = {}
        total = 0
        for stock in stocks:
            quotes[stock["Symbol"]] = lookup(stock["Symbol"])
            total = total + quotes[stock["Symbol"]]["price"] * stock["total_shares"]

        cash_remaining = user[0]["cash"]
        total = total + cash_remaining

        msg = Message("Purchase Transaction", recipients=[rows[0]["email"]])
        msg.html = render_template('mail-purchase.html',
                    username=rows[0]["name"] ,
                    number=number ,
                    company= share["name"],
                    pricepershare=share["price"] ,
                    totalinpurchase = share["price"] * number,
                    cash = "%.2f" % user[0]["cash"],
                    totaltotal = "%.2f" % total)
        mail.send(msg)

        flash("Successfully Bought!")
        return redirect(url_for("index"))


    if request.method =="GET":
        return render_template("buy.html")



@app.route("/check", methods=["GET"])
def check():
    """Return true if username available, else false, in JSON format"""
    return jsonify("TODO")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    transactions = db.execute(
        "SELECT Symbol, Shares, pps, timestamp FROM transactions WHERE user_id = :user_id ORDER BY timestamp ASC", user_id=session["user_id"])

    return render_template("history.html", transactions=transactions)



@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            flash("Username must be provided, please try again")
            return redirect(url_for("login"))

        # Ensure password was submitted
        elif not request.form.get("password"):
            flash("Password must be provided, please try again")
            return redirect(url_for("login"))

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            flash("Invalid user and/or password, please try again")
            return redirect(url_for("login"))

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
        quote = lookup(request.form.get("symbol"))

        if quote == None:
            flash("This company is at the moment not available on our platform, please try again")
            return redirect(url_for("quote"))

        return render_template("quoted.html", quote = quote)

    else:
        return render_template("quote.html")



@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":
        if not request.form.get("username"):
            flash("Username field must be filled, please try again")
            return redirect(url_for("register"))
        elif not request.form.get("password"):
            flash("Password field must be filled, please try again")
            return redirect(url_for("register"))
        elif not request.form.get("name"):
            flash("Name field must be filled, please try again")
            return redirect(url_for("register"))
        elif not request.form.get("email"):
            flash("Your e-mail field must be filled, please try again")
            return redirect(url_for("register"))
        elif not request.form.get("confirmation") == request.form.get("password"):
            flash("Wrong password, please try again")
            return redirect(url_for("register"))

        passwort = generate_password_hash(request.form.get("password"), method='pbkdf2:sha256', salt_length=8)
        new_user = db.execute("INSERT INTO users (username, hash, name, email) VALUES (:username, :passwort, :name, :email)",
                    username=request.form.get("username"), passwort=passwort, name = request.form.get("name"), email= request.form.get("email"))
        db.execute("INSERT INTO friendstable (mainuser, friends) VALUES (:mainuser, :friends)",
                    mainuser = request.form.get("username"),
                    friends = request.form.get("username"))
        if not new_user:
            flash("username already exists, please try again")
            return redirect(url_for("register"))

        session["user_id"] = new_user


        db.execute("UPDATE friendstable SET friends_id =:friends_id WHERE friends = :friend AND mainuser = friends",
                    friends_id = session["user_id"],
                    friend = request.form.get("username"))

        user = db.execute("SELECT * FROM users WHERE id =:user_id", user_id=session["user_id"])

        msg = Message("Registration", recipients=[user[0]["email"]])
        msg.html = render_template('mail-register.html',
                    username=user[0]["name"])
        mail.send(msg)

        flash("Successfully Registered! A message has been sent to your spam folder in your mailbox. Please check your spam folder for confirmation")
        return redirect(url_for("index"))

    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    if request.method == "GET":
        stocks = db.execute("SELECT Symbol, SUM(Shares) as total_shares FROM transactions WHERE user_id = :user_id GROUP BY Symbol HAVING total_shares > 0", user_id = session["user_id"])
        return render_template("sell.html", stocks = stocks)

    elif request.method =="POST":
        quote = lookup(request.form.get("symbol"))
        if quote == None:
            flash("There is no such symbol value, please try again")
            return redirect(url_for("sell"))

        try:
            shares = int(request.form.get("shares"))
        except:
            flash("Number of shares must be an positive integer, please try again")
            return redirect(url_for("sell"))

        if shares < 0:
            flash("Number of shares must be a positive integer, please try again")
            return redirect(url_for("sell"))

        stock = db.execute("SELECT SUM(Shares) as total_shares FROM transactions WHERE user_id = :user_id AND Symbol = :symbol GROUP BY Symbol", user_id = session["user_id"], symbol = request.form.get("symbol"))

        if stock[0]["total_shares"] < shares:
            flash("Cannot sell more shares than you have, please try again")
            return redirect(url_for("sell"))

        addmoney = shares * quote["price"]

        db.execute("UPDATE users SET cash = cash + :addmoney WHERE id = :user_id", addmoney = addmoney, user_id = session["user_id"])
        db.execute("INSERT INTO transactions (user_id, Symbol, Shares, Company, pps, Total) VALUES (:user_id, :Symbol, :Shares, :Company, :pps, :Total)",
                    user_id = session["user_id"],
                    Symbol = quote["symbol"],
                    Shares = -shares,
                    Company = quote["name"],
                    pps = quote["price"],
                    Total = addmoney)

        user = db.execute("SELECT * FROM users WHERE id =:user", user = session["user_id"])
        stocks = db.execute("SELECT Symbol, SUM(Shares) as total_shares FROM transactions WHERE user_id = :user_id GROUP BY Symbol HAVING total_shares > 0", user_id=session["user_id"])
        quotes = {}
        total = 0
        for st in stocks:
            quotes[st["Symbol"]] = lookup(st["Symbol"])
            total = total + quotes[st["Symbol"]]["price"] * st["total_shares"]

        cash_remaining = user[0]["cash"]
        total = total + cash_remaining

        msg = Message("Sell Transaction", recipients=[user[0]["email"]])
        msg.html = render_template('mail-sell.html',
                    username=user[0]["name"] ,
                    number=shares,
                    company= quote["name"],
                    pricepershare=quote["price"] ,
                    totalinsell = quote["price"] * shares,
                    cash = "%.2f" % user[0]["cash"],
                    totaltotal = "%.2f" % total)
        mail.send(msg)

        flash("Successfully Sold!")
        return redirect(url_for("index"))



@app.route("/list", methods=["GET"])
def get_sheet():
    with open("list.csv","r") as file:
        reader = csv.DictReader(file)
        company = list(reader)

    return render_template("list.html", thelist = company)







def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return "fehler"


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)

if __name__ == '__main__':
    app.run(debug = True)
