from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import psycopg2
import os
import uuid

app = Flask(__name__)
app.config['SECRET_KEY'] = 'секретно-секретный ключ'  # Убедитесь, что ключ безопасный

# Папка для хранения загруженных файлов
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Функция для подключения к базе данных
def db_connect():
    conn = psycopg2.connect(
        host='127.0.0.1',
        database='rgz',
        user='admin',
        password='5522369',  # Замените на свой пароль
    )
    cur = conn.cursor()
    return conn, cur

# Функция для закрытия соединения с базой
def db_close(conn, cur):
    cur.close()
    conn.commit()
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
        cur.execute("SELECT avatar FROM users WHERE id = %s;", (session.get('user_id'),))
        user = cur.fetchone()
        db_close(conn, cur)
        
        if user and user[0]:
            avatar = user[0]  # Если аватар есть, добавляем его в сессию

    session['avatar'] = avatar  # Сохраняем аватар в сессию

    conn, cur = db_connect()

    # Получаем все объявления и добавляем поле user_id
    cur.execute(""" 
        SELECT ads.id, ads.title, ads.description, ads.photo, users.name, users.email, ads.user_id
        FROM ads
        JOIN users ON ads.user_id = users.id;
    """)

    ads = cur.fetchall()
    db_close(conn, cur)

    # Скрыть email для неавторизованных пользователей
    if not session.get('user_id'):
        ads = [(ad[0], ad[1], ad[2], ad[3], ad[4], None, ad[6]) for ad in ads]

    return render_template("index.html", user=username, ads=ads)



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

        cur.execute("SELECT * FROM users WHERE login=%s;", (username,))
        if cur.fetchone():
            db_close(conn, cur)
            flash("Пользователь с таким именем уже существует.", "danger")
            return render_template("register.html")

        cur.execute("SELECT * FROM users WHERE email=%s;", (email,))
        if cur.fetchone():
            db_close(conn, cur)
            flash("Пользователь с таким email уже существует.", "danger")
            return render_template("register.html")

        password_hash = generate_password_hash(password)

        if avatar_filename:
            cur.execute("INSERT INTO users (login, password, name, email, avatar) VALUES (%s, %s, %s, %s, %s);", 
                        (username, password_hash, name, email, avatar_filename))
        else:
            cur.execute("INSERT INTO users (login, password, name, email) VALUES (%s, %s, %s, %s);", 
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
        cur.execute("SELECT id, password, email FROM users WHERE login = %s", (username,))
        user = cur.fetchone()
        db_close(conn, cur)

        if user and check_password_hash(user[1], password):
            session["user_id"] = user[0]
            session["username"] = username
            session["email"] = user[2]  # Сохраняем email в сессии
            flash("Добро пожаловать!", "success")
            print(f"User session: {session}")  # Отладочный вывод
            return redirect(url_for("home"))
        else:
            flash("Неверное имя пользователя или пароль", "error")
            return render_template("login.html")

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
        cur.execute(
            "INSERT INTO ads (user_id, title, description, photo) VALUES (%s, %s, %s, %s);",
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
    cur.execute("SELECT * FROM ads WHERE id = %s;", (id,))
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
    cur.execute("SELECT user_id FROM ads WHERE id = %s;", (id,))
    ad = cur.fetchone()

    if ad:
        # Логирование для проверки
        print(f"Trying to delete ad {id} by user {session.get('user_id')} (admin: {is_admin()})")

        if ad[0] == session.get('user_id') or ('user_id' in session and is_admin()):
            cur.execute("DELETE FROM ads WHERE id = %s;", (id,))
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
    cur.execute("SELECT user_id, title, description, photo FROM ads WHERE id = %s;", (ad_id,))
    ad = cur.fetchone()
    db_close(conn, cur)

    if not ad:
        flash('Объявление не найдено.', 'error')
        return redirect(url_for('home'))

    ad_user_id = ad[0]  # Получаем user_id из объявления
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

if __name__ == "__main__":
    app.run(debug=True)
