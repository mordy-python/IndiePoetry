from flask import (
    Flask,
    render_template,
    send_from_directory,
    session,
    redirect,
    url_for,
    request,
    flash,
)
from deta import Deta
import os
from flask_gravatar import Gravatar
import bcrypt
from datetime import date, datetime
import random
from hashlib import md5

try:
    import dotenv

    dotenv.load_dotenv(".env")
except ModuleNotFoundError:  # We're not running locally
    pass

app = Flask(__name__)
deta = Deta("")
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "super-secret-key")

gravatar = Gravatar(
    app,
    size=100,
    rating="g",
    default="retro",
    force_default=False,
    use_ssl=False,
    base_url=None,
)

poems = deta.Base("poems")
users = deta.Base("users")
pfps = deta.Drive("pfps")

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "jfif"}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# Sitemap.xml
@app.route("/sitemap.xml")
def sitemap():
    return send_from_directory(".", "sitemap.xml")


@app.route("/")
def index():
    user = (
        users.fetch({"username": session["username"]}).items[0]
        if "username" in session
        else {}
    )
    _poems = poems.fetch().items
    _poems = sorted(_poems, key=lambda d: d["_time"], reverse=True)
    return render_template(
        "index.html",
        name=user.get("username", "Not Logged In"),
        birthday=user.get(
            "bday",
            f"{random.randint(1, 13)}/{random.randint(1, 30)}/{random.randint(1990, 2022)}",
        ),
        location=user.get("location", "New York, NY"),
        poems=_poems,
        title="Home",
    )


@app.route("/poems/<id>")
def single_poem(id):
    user = (
        users.fetch({"username": session["username"]}).items[0]
        if "username" in session
        else {}
    )
    poem = poems.get(id)
    author_id = users.fetch({"username": poem["posted_by"]}).items[0]["key"]
    return render_template(
        "poem.html",
        poem=poem,
        name=user.get("username", "Not Logged In"),
        birthday=user.get(
            "bday",
            f"{random.randint(1, 13)}/{random.randint(1, 30)}/{random.randint(1990, 2022)}",
        ),
        location=user.get("location", "New York, NY"),
        page_type="poem_page",
        title=poem["title"],
        author_id=author_id,
    )


@app.route("/compose", methods=["GET", "POST"])
def compose():
    if not "username" in session:
        return redirect(url_for("index"))
    if request.method == "POST":
        title = request.form.get("title")
        poem = request.form.get("poem")
        author = session["username"]
        date_posted = date.today()
        post = {
            "title": title,
            "poem_body": poem,
            "posted_by": author,
            "posted_on": str(date_posted),
            "_time": str(datetime.now()),
        }
        poems.put(post)
        return redirect(url_for("index"))
    rules = [
        "Do not post other people's poems without attributing them.",
        "Do not post other people's poems without their permission even if you are attributing them.",
        "No slurs will be tolerated, the poem will be deleted.",
        # "If your poem mentions something triggering, a trigger warning is required in the title.",
        "If a user's poems are repeatedly deleted for slurs, being hateful, or otherwise disrupting this site, their account may be deleted.",
    ]
    return render_template(
        "compose.html",
        rules=rules,
        page_type="signup_or_login_or_poem",
        title="New Poem",
    )


@app.route("/account")
def account():
    if not "username" in session:
        return redirect(url_for("login"))
    user = (
        users.fetch({"username": session["username"]}).items[0]
        if "username" in session
        else {}
    )
    user_poems = poems.fetch({"posted_by": session["username"]}).items
    return render_template(
        "account.html",
        email=user["email"],
        name=user.get("username", "Not Logged In"),
        birthday=user.get(
            "bday",
            f"{random.randint(1, 13)}/{random.randint(1, 30)}/{random.randint(1990, 2022)}",
        ),
        location=user.get("location", "New York, NY"),
        num_poems=len(user_poems),
        users_poems=user_poems,
        title="My Account",
        page_type="account",
    )


@app.route("/save-account-data", methods=["POST"])
def save_account_data():
    data = request.form
    username = data.get("username", session["username"])
    email = data.get("email", session["email"])
    location = data.get("location", "New York, NY")
    user = users.fetch({"username": session["username"]}).items[0]
    user_id = user["key"]
    users.update(
        {"username": username, "email": email, "location": location}, key=user_id
    )
    session["username"] = username
    flash("Successfully update your info!", "success")
    return redirect(url_for("account"))


def avatar(email):
    digest = md5(email.lower().encode("utf-8")).hexdigest()
    return f"https://www.gravatar.com/avatar/{digest}?d=robohash&s=64"


@app.route("/login", methods=["GET", "POST"])
def login():
    if "username" in session:
        return redirect(url_for("index"))
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        user_exists = users.fetch({"username": username})
        if not user_exists.items:
            flash("Invalid username or password", "error")
            return redirect(url_for("login"))
        stored_pwd = user_exists.items[0]["password"].encode()
        if bcrypt.checkpw(password.encode(), stored_pwd):
            session["username"] = user_exists.items[0]["username"]
            session["email"] = user_exists.items[0]["email"]
            # session['pfp'] = user_exists.items[0]["avatar"]
            flash("Logged in successfully!", "success")
            return redirect(url_for("index"))
        else:
            flash("Invalid username or password", "error")
    return render_template(
        "login.html", page_type="signup_or_login_or_poem", title="Login"
    )


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if "username" in session:
        return redirect(url_for("index"))
    if request.method == "POST":
        username = request.form["username"]
        email = request.form["email"]
        password = request.form["password"]
        bday = request.form["bday"]
        user_exists = users.fetch({"username": username})
        if user_exists.items:
            flash("That username or email is already taken", "error")
            return redirect(url_for("signup"))
        user_exists = users.fetch({"email": email})
        if user_exists.items:
            flash("That username or email is already taken", "error")
            return redirect(url_for("signup"))
        hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt(prefix=b"2a"))
        user = {
            "username": username,
            "email": email,
            "password": hashed.decode(),
            "bday": bday,
            "avatar": avatar(email),
        }
        users.put(user)
        flash("Account Created Successfully!", "success")
        return redirect(url_for("login"))
    return render_template(
        "signup.html", page_type="signup_or_login_or_poem", title="Signup"
    )


@app.route("/signout")
def signout():
    if "username" in session:
        session.pop("username")
        session.pop("email")
    return redirect(url_for("index"))


@app.route("/delete")
def delete():
    poems.delete(request.args["id"]) if "username" in session else ""
    flash("Post deleted successfully!", "success")
    return redirect(url_for("index"))


@app.route("/poets/<user_id>")
def profile(user_id):
    user = users.get(user_id)
    users_poems = sorted(
        poems.fetch({"posted_by": user["username"]}).items,
        key=lambda x: x["_time"],
        reverse=True,
    )
    return render_template(
        "profile.html",
        user=user,
        page_type="signup_or_login_or_poem",
        title=f'{user["username"]}\'s profile',
        num_poems=len(users_poems),
        poems=users_poems,
    )


@app.route("/upload", methods=["POST"])
def upload():
    return "Hello"


if __name__ == "__main__":
    app.run(debug=True)
