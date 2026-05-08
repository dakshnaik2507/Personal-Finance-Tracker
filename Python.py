from flask import Flask, render_template, request, redirect
from flask_login import *
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3

app = Flask(__name__)
app.secret_key = "secret123"

login_manager = LoginManager(app)
login_manager.login_view = "login"

# ================= DATABASE =================
def get_db():
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()

    conn.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        username TEXT,
        password TEXT
    )
    """)

    conn.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY,
        user_id INTEGER,
        amount REAL,
        type TEXT,
        category TEXT,
        date TEXT
    )
    """)

    conn.execute("""
    CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY,
        user_id INTEGER,
        name TEXT
    )
    """)

    conn.execute("""
    CREATE TABLE IF NOT EXISTS goals (
        id INTEGER PRIMARY KEY,
        user_id INTEGER,
        target REAL,
        saved REAL
    )
    """)

    conn.commit()
    conn.close()

init_db()

# ================= USER =================
class User(UserMixin):
    def __init__(self, id, username):
        self.id = id
        self.username = username

@login_manager.user_loader
def load_user(user_id):
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    conn.close()
    if user:
        return User(user["id"], user["username"])
    return None

# ================= ROUTES =================

@app.route("/")
def home():
    return redirect("/login")

# ---------- LOGIN ----------
@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        conn = get_db()
        user = conn.execute(
            "SELECT * FROM users WHERE username=?",
            (request.form["username"],)
        ).fetchone()
        conn.close()

        if user and check_password_hash(user["password"], request.form["password"]):
            login_user(User(user["id"], user["username"]))
            return redirect("/dashboard")

    return render_template("login.html")

# ---------- SIGNUP ----------
@app.route("/signup", methods=["GET","POST"])
def signup():
    if request.method == "POST":
        conn = get_db()
        conn.execute(
            "INSERT INTO users (username,password) VALUES (?,?)",
            (request.form["username"],
             generate_password_hash(request.form["password"]))
        )
        conn.commit()
        conn.close()
        return redirect("/login")

    return render_template("signup.html")

# ---------- LOGOUT ----------
@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect("/login")

# ---------- DASHBOARD ----------
@app.route("/dashboard")
@login_required
def dashboard():
    conn = get_db()

    data = conn.execute(
        "SELECT * FROM transactions WHERE user_id=?",
        (current_user.id,)
    ).fetchall()

    income = sum([x["amount"] for x in data if x["type"] == "income"])
    expense = sum([x["amount"] for x in data if x["type"] == "expense"])
    balance = income - expense

    recent = conn.execute("""
        SELECT * FROM transactions
        WHERE user_id=?
        ORDER BY id DESC LIMIT 5
    """, (current_user.id,)).fetchall()

    goal = conn.execute(
        "SELECT * FROM goals WHERE user_id=?",
        (current_user.id,)
    ).fetchone()

    conn.close()

    return render_template(
        "dashboard.html",
        income=income,
        expense=expense,
        balance=balance,
        recent=recent,
        goal=goal,
        username=current_user.username   # ✅ for welcome message
    )

# ---------- ADD ----------
@app.route("/add", methods=["GET","POST"])
@login_required
def add():
    if request.method == "POST":
        conn = get_db()
        conn.execute("""
            INSERT INTO transactions (user_id,amount,type,category,date)
            VALUES (?,?,?,?,?)
        """, (
            current_user.id,
            request.form["amount"],
            request.form["type"],
            request.form["category"],
            request.form["date"]
        ))
        conn.commit()
        conn.close()
        return redirect("/dashboard")

    return render_template("add.html")

# ---------- TRANSACTIONS ----------
@app.route("/transactions")
@login_required
def transactions():
    conn = get_db()

    search = request.args.get("search")

    if search:
        data = conn.execute("""
            SELECT * FROM transactions
            WHERE user_id=? AND category LIKE ?
        """, (current_user.id, f"%{search}%")).fetchall()
    else:
        data = conn.execute(
            "SELECT * FROM transactions WHERE user_id=?",
            (current_user.id,)
        ).fetchall()

    conn.close()
    return render_template("transactions.html", data=data)

# ---------- DELETE (FIXED) ----------
@app.route("/delete/<int:id>")
@login_required
def delete(id):
    conn = get_db()
    conn.execute(
        "DELETE FROM transactions WHERE id=? AND user_id=?",
        (id, current_user.id)
    )
    conn.commit()
    conn.close()
    return redirect("/transactions")

# ---------- EDIT (FIXED) ----------
@app.route("/edit/<int:id>", methods=["GET","POST"])
@login_required
def edit(id):
    conn = get_db()

    if request.method == "POST":
        conn.execute("""
            UPDATE transactions
            SET amount=?, type=?, category=?, date=?
            WHERE id=? AND user_id=?
        """, (
            request.form["amount"],
            request.form["type"],
            request.form["category"],
            request.form["date"],
            id,
            current_user.id
        ))
        conn.commit()
        conn.close()
        return redirect("/transactions")

    data = conn.execute(
        "SELECT * FROM transactions WHERE id=? AND user_id=?",
        (id, current_user.id)
    ).fetchone()

    conn.close()
    return render_template("edit.html", data=data)

# ---------- REPORTS ----------
@app.route("/reports", methods=["GET","POST"])
@login_required
def reports():
    conn = get_db()

    if request.method == "POST":
        start = request.form["start"]
        end = request.form["end"]

        data = conn.execute("""
            SELECT * FROM transactions
            WHERE user_id=? AND date BETWEEN ? AND ?
        """, (current_user.id, start, end)).fetchall()
    else:
        data = conn.execute(
            "SELECT * FROM transactions WHERE user_id=?",
            (current_user.id,)
        ).fetchall()

    conn.close()
    return render_template("reports.html", data=data)

# ---------- INSIGHTS ----------
@app.route("/insights")
@login_required
def insights():
    conn = get_db()

    data = conn.execute("""
        SELECT category, SUM(amount) as total
        FROM transactions
        WHERE user_id=? AND type='expense'
        GROUP BY category
    """, (current_user.id,)).fetchall()

    labels = [x["category"] for x in data]
    values = [x["total"] for x in data]

    conn.close()

    return render_template("insights.html", labels=labels, values=values)

# ---------- CATEGORIES ----------
@app.route("/categories", methods=["GET","POST"])
@login_required
def categories():
    conn = get_db()

    if request.method == "POST":
        conn.execute(
            "INSERT INTO categories (user_id,name) VALUES (?,?)",
            (current_user.id, request.form["name"])
        )
        conn.commit()

    data = conn.execute(
        "SELECT * FROM categories WHERE user_id=?",
        (current_user.id,)
    ).fetchall()

    conn.close()
    return render_template("categories.html", data=data)

# ---------- GOAL ----------
@app.route("/goal", methods=["GET","POST"])
@login_required
def goal():
    conn = get_db()

    if request.method == "POST":
        conn.execute("DELETE FROM goals WHERE user_id=?", (current_user.id,))
        conn.execute("""
            INSERT INTO goals (user_id,target,saved)
            VALUES (?,?,?)
        """, (
            current_user.id,
            request.form["target"],
            request.form["saved"]
        ))
        conn.commit()

    goal = conn.execute(
        "SELECT * FROM goals WHERE user_id=?",
        (current_user.id,)
    ).fetchone()

    conn.close()
    return render_template("goal.html", goal=goal)

# ---------- PROFILE ----------
@app.route("/profile", methods=["GET","POST"])
@login_required
def profile():
    if request.method == "POST":
        conn = get_db()
        conn.execute("""
            UPDATE users SET password=? WHERE id=?
        """, (
            generate_password_hash(request.form["password"]),
            current_user.id
        ))
        conn.commit()
        conn.close()

    return render_template("profile.html")

# ================= RUN =================
if __name__ == "__main__":
    app.run(debug=True)
