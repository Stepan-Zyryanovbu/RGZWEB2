from flask import Flask, render_template, request, redirect, url_for, flash, current_app, session
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from psycopg2.extras import RealDictCursor
import psycopg2
import os
import uuid
import sqlite3
from os import path

app = Flask(__name__)

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'секретно-секретный секрет')
app.config['DB_TYPE'] = os.getenv('DB_TYPE', 'postgres')

# Папка для хранения загруженных файлов
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Функция для подключения к базе данных
def db_connect():
#   Устанавливает подключение к базе данных.
    
    if current_app.config['DB_TYPE'] == 'postgres':
        conn = psycopg2.connect(
            host='127.0.0.1',
            database='rgz',
            user='admin',
            password='5522369'
        )
        cur = conn.cursor(cursor_factory=RealDictCursor)
    else:
        dir_path = path.dirname(path.realpath(__file__))
        db_path = path.join(dir_path, "database.db")
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

    return conn, cur

def db_close(conn, cur):
    conn.commit()
    cur.close()
    conn.close()

# Функция для проверки разрешенных типов файлов
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Функция для создания папки для загрузок
def create_upload_folder():
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])

# Проверка на администратора
def is_admin():
    return session.get('user_id') and session.get('email') == 'spznsk@gmail.com'

@app.route("/", methods=["GET"])
def home():
    username = session.get('username')  # Проверяем сессию для имени пользователя
    avatar = None

    if session.get('user_id'):
        # Получаем аватар пользователя из базы данных
        conn, cur = db_connect()
        if current_app.config['DB_TYPE'] == 'postgres':
            cur.execute("SELECT avatar FROM users WHERE id = %s;", (session.get('user_id'),))
        else:
            cur.execute("SELECT avatar FROM users WHERE id = ?;", (session.get('user_id'),))
        user = cur.fetchone()
        db_close(conn, cur)

        if user and user['avatar']:  # Проверка через ключ 'avatar'
            avatar = user['avatar']  # Если аватар есть, добавляем его в сессию

    session['avatar'] = avatar  # Сохраняем аватар в сессию

    conn, cur = db_connect()

    # Получаем все объявления и добавляем поле user_id
    if current_app.config['DB_TYPE'] == 'postgres':
        cur.execute(""" 
            SELECT ads.id, ads.title, ads.description, ads.photo, users.name, users.email, ads.user_id
            FROM ads
            JOIN users ON ads.user_id = users.id;
        """)
    else:
        cur.execute(""" 
            SELECT ads.id, ads.title, ads.description, ads.photo, users.name, users.email, ads.user_id
            FROM ads
            JOIN users ON ads.user_id = users.id;
        """)

    ads = cur.fetchall()
    db_close(conn, cur)

    if not session.get('user_id'):
        # Если пользователь не авторизован, скрываем email
        ads = [
            (ad['id'], ad['title'], ad['description'], ad['photo'], ad['name'], None, ad['user_id'])
            for ad in ads
        ]
    else:
        # Для авторизованных пользователей, в том числе email
        ads = [
            (ad['id'], ad['title'], ad['description'], ad['photo'], ad['name'], ad['email'], ad['user_id'])
            for ad in ads
        ]

    return render_template("index.html", user=username, avatar=avatar, ads=ads)





@app.route("/register", methods=["GET", "POST"])
def register():
    create_upload_folder()  # Создаём папку для загрузки, если она не существует

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        name = request.form.get("name")
        email = request.form.get("email")

        avatar = request.files.get("avatar")
        avatar_filename = None

        if avatar and allowed_file(avatar.filename):
            avatar_filename = f"{uuid.uuid4()}_{secure_filename(avatar.filename)}"
            avatar.save(os.path.join(app.config['UPLOAD_FOLDER'], avatar_filename))

        if not username or not password or not name or not email:
            flash("Заполните все поля!", "danger")
            return render_template("register.html")

        conn, cur = db_connect()

        if current_app.config['DB_TYPE'] == 'postgres':
            cur.execute("SELECT * FROM users WHERE login=%s;", (username,))
        else:
            cur.execute("SELECT * FROM users WHERE login=?;", (username,))
        if cur.fetchone():
            db_close(conn, cur)
            flash("Пользователь с таким именем уже существует.", "danger")
            return render_template("register.html")

        if current_app.config['DB_TYPE'] == 'postgres':
            cur.execute("SELECT * FROM users WHERE email=%s;", (email,))
        else:
            cur.execute("SELECT * FROM users WHERE email=?;", (email,))
        if cur.fetchone():
            db_close(conn, cur)
            flash("Пользователь с таким email уже существует.", "danger")
            return render_template("register.html")

        password_hash = generate_password_hash(password)
        if current_app.config['DB_TYPE'] == 'postgres':
            if avatar_filename:
                cur.execute("INSERT INTO users (login, password, name, email, avatar) VALUES (%s, %s, %s, %s, %s);", 
                        (username, password_hash, name, email, avatar_filename))
            else:
                cur.execute("INSERT INTO users (login, password, name, email) VALUES (%s, %s, %s, %s);", 
                        (username, password_hash, name, email))
        else:
            if avatar_filename:
                cur.execute("INSERT INTO users (login, password, name, email, avatar) VALUES (?, ?, ?, ?, ?);", 
                        (username, password_hash, name, email, avatar_filename))
            else:
                cur.execute("INSERT INTO users (login, password, name, email) VALUES (?, ?, ?, ?);", 
                        (username, password_hash, name, email))

        db_close(conn, cur)

        flash("Регистрация успешна!", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        conn, cur = db_connect()
        if current_app.config['DB_TYPE'] == 'postgres':
            cur.execute("SELECT id, password, email FROM users WHERE login = %s", (username,))
        else:
            cur.execute("SELECT id, password, email FROM users WHERE login = ?", (username,))
        user = cur.fetchone()
        db_close(conn, cur)

        if user:
            if check_password_hash(user['password'] if isinstance(user, dict) else user[1], password):
                session["user_id"] = user['id'] if isinstance(user, dict) else user[0]
                session["username"] = username
                session["email"] = user['email'] if isinstance(user, dict) else user[2]
                flash("Добро пожаловать!", "success")
                return redirect(url_for("home"))
            else:
                flash("Неверное имя пользователя или пароль", "error")
        else:
            flash("Пользователь не найден", "error")

    return render_template("login.html")


@app.route("/logout", methods=["GET", "POST"])
def logout():
    if request.method == "POST":
        session.pop("user_id", None)
        session.pop("username", None)
        session.pop("email", None)
        flash("Вы вышли из системы.", "info")
        return redirect(url_for("home"))
    return redirect(url_for("home"))


@app.route("/create_ad", methods=["GET", "POST"])
def create_ad():
    if request.method == "POST":
        title = request.form.get("title")
        description = request.form.get("description")

        user_id = session.get("user_id")
        if not user_id:
            flash("Пожалуйста, войдите в систему", "error")
            return redirect(url_for("login"))

        photo = request.files.get("photo")
        photo_filename = None

        if photo and allowed_file(photo.filename):
            photo_filename = f"{uuid.uuid4()}_{secure_filename(photo.filename)}"
            photo.save(os.path.join(app.config['UPLOAD_FOLDER'], photo_filename))

        conn, cur = db_connect()

        # Вставляем объявление в базу, используя правильный user_id
        if current_app.config['DB_TYPE'] == 'postgres':
            cur.execute(
            "INSERT INTO ads (user_id, title, description, photo) VALUES (%s, %s, %s, %s);",
            (user_id, title, description, photo_filename)
        )
        else:
            cur.execute(
            "INSERT INTO ads (user_id, title, description, photo) VALUES (?, ?, ?, ?);",
            (user_id, title, description, photo_filename)
        )
        db_close(conn, cur)

        flash("Объявление успешно добавлено!", "success")
        return redirect(url_for("home"))

    return render_template("create_ad.html")


@app.route("/ad/<int:id>")
def view_ad(id):
    if not session.get("user_id"):
        flash("Пожалуйста, войдите в систему.", "warning")
        return redirect(url_for("login"))

    conn, cur = db_connect()
    if current_app.config['DB_TYPE'] == 'postgres':
        cur.execute("SELECT * FROM ads WHERE id = %s;", (id,))
    else:
        cur.execute("SELECT * FROM ads WHERE id = ?;", (id,))
    ad = cur.fetchone()
    db_close(conn, cur)

    if ad:
        return render_template("view_ad.html", ad=ad)
    else:
        flash("Объявление не найдено.", "danger")
        return redirect(url_for("home"))


@app.route("/delete_ad/<int:id>", methods=["POST"])
def delete_ad(id):
    if 'user_id' not in session:
        flash("Пожалуйста, войдите в систему.", "warning")
        return redirect(url_for("login"))

    conn, cur = db_connect()
    if current_app.config['DB_TYPE'] == 'postgres':
        cur.execute("SELECT user_id FROM ads WHERE id = %s;", (id,))
    else:
        cur.execute("SELECT user_id FROM ads WHERE id = ?;", (id,))
    ad = cur.fetchone()

    if ad:
        # Логирование для проверки
        print(f"Trying to delete ad {id} by user {session.get('user_id')} (admin: {is_admin()})")

        if ad['user_id'] == session.get('user_id') or ('user_id' in session and is_admin()):
            if current_app.config['DB_TYPE'] == 'postgres':
                cur.execute("DELETE FROM ads WHERE id = %s;", (id,))
            else:
                cur.execute("DELETE FROM ads WHERE id = ?;", (id,))
            conn.commit()
            flash("Объявление успешно удалено!", "success")
        else:
            flash("Вы не можете удалить это объявление.", "danger")
    else:
        flash("Объявление не найдено.", "danger")

    db_close(conn, cur)
    return redirect(url_for("home"))



@app.route('/ads/edit/<int:ad_id>', methods=['GET', 'POST'])
def edit_ad(ad_id):
    if 'user_id' not in session:
        flash('Вы должны войти в систему для редактирования объявлений.', 'error')
        return redirect(url_for('login'))

    conn, cur = db_connect()
    if current_app.config['DB_TYPE'] == 'postgres':
        cur.execute("SELECT user_id, title, description, photo FROM ads WHERE id = %s;", (ad_id,))
    else:
        cur.execute("SELECT user_id, title, description, photo FROM ads WHERE id = ?;", (ad_id,))
    ad = cur.fetchone()
    db_close(conn, cur)

    if not ad:
        flash('Объявление не найдено.', 'error')
        return redirect(url_for('home'))

    ad_user_id = ad['user_id']  # Получаем user_id из объявления (используем ключ)
    if ad_user_id != session['user_id'] and not is_admin():  # Проверяем владельца
        flash('У вас нет прав на редактирование этого объявления.', 'error')
        return redirect(url_for('home'))

    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        photo = request.files.get('photo')
        photo_filename = None

        if photo and allowed_file(photo.filename):
            photo_filename = f"{uuid.uuid4()}_{secure_filename(photo.filename)}"
            photo.save(os.path.join(app.config['UPLOAD_FOLDER'], photo_filename))

        conn, cur = db_connect()
        if photo_filename:
            cur.execute("""
                UPDATE ads
                SET title = %s, description = %s, photo = %s
                WHERE id = %s;
            """, (title, description, photo_filename, ad_id))
        else:
            cur.execute("""
                UPDATE ads
                SET title = %s, description = %s
                WHERE id = %s;
            """, (title, description, ad_id))
        db_close(conn, cur)

        flash('Объявление обновлено успешно.', 'success')
        return redirect(url_for('home'))

    return render_template('edit_ad.html', ad=ad)

@app.route('/delete_account', methods=['POST'])
def delete_account():
    if 'user_id' not in session:
        return redirect('/login')  # Если пользователь не авторизован

    user_id = session['user_id']

    conn, cur = db_connect()

    try:
        # Удаляем пользователя и связанные данные
        if current_app.config['DB_TYPE'] == 'postgres':
            cur.execute("DELETE FROM ads WHERE user_id = %s;", (user_id,))  # Удаляем объявления пользователя
        else:
            cur.execute("DELETE FROM ads WHERE user_id = ?;", (user_id,))

        if current_app.config['DB_TYPE'] == 'postgres':
            cur.execute("DELETE FROM users WHERE id = %s;", (user_id,))
        else:
            cur.execute("DELETE FROM users WHERE id = ?;", (user_id,))    # Удаляем сам аккаунт
        conn.commit()
        db_close(conn, cur)

        # Завершаем сессию
        session.pop("user_id", None)
        session.pop("username", None)
        session.pop("email", None)

        flash("Ваш аккаунт был успешно удалён.", "success")
        return redirect('/')
    except Exception as e:
        conn.rollback()
        db_close(conn, cur)
        flash(f"Произошла ошибка: {str(e)}", "danger")
        return redirect('/profile')


if __name__ == "__main__":
    app.run(debug=True)