import sqlite3
import json
import os
from flask import Flask, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from flasgger import Swagger

app = Flask(__name__)
app.json.ensure_ascii = False
swagger = Swagger(app)
db_name = 'users.db'


def init_db():
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            phone TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            event TEXT,
            list_task TEXT,
            is_admin INTEGER CHECK (is_admin IN (0, 1))
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS events (
            id_event INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT NOT NULL,
            attach TEXT,
            date INTEGER,
            users_event TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id_tasks INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT NOT NULL,
            attach TEXT
        )
    ''')
    conn.commit()
    conn.close()


def get_db_connection():
    conn = sqlite3.connect(db_name)
    conn.row_factory = sqlite3.Row
    return conn


init_db()


# --- МЕТОДЫ ПОЛЬЗОВАТЕЛЕЙ ---

@app.route('/register', methods=['POST'])
def register():
    """
    Регистрация нового пользователя
    ---
    parameters:
      - name: body
        in: body
        required: true
        schema:
          properties:
            username: {type: string, example: "ivan_ivanov"}
            phone: {type: string, example: "89001112233"}
            password: {type: string, example: "12345"}
            is_admin: {type: integer, enum: [0, 1], example: 1}
    responses:
      201:
        description: Пользователь успешно создан
        schema:
          properties:
            status: {type: string, example: "success"}
            user_id: {type: integer, example: 1}
      400:
        description: Ошибка (пользователь уже есть)
    """
    data = request.get_json()
    conn = get_db_connection()
    try:
        hashed_pw = generate_password_hash(data['password'])
        cursor = conn.execute(
            'INSERT INTO users (username, phone, password, event, list_task, is_admin) VALUES (?, ?, ?, ?, ?, ?)',
            (data['username'], data['phone'], hashed_pw, json.dumps([]), json.dumps([]), data['is_admin'])
        )
        user_id = cursor.lastrowid
        conn.commit()
        return jsonify({"status": "success", "user_id": user_id}), 201
    except sqlite3.IntegrityError:
        return jsonify({"status": "error", "message": "User already exists"}), 400
    finally:
        conn.close()


@app.route('/login', methods=['POST'])
def login():
    """
    Авторизация
    ---
    parameters:
      - name: body
        in: body
        required: true
        schema:
          properties:
            username: {type: string, example: "ivan_ivanov"}
            password: {type: string, example: "12345"}
    responses:
      200:
        description: Успешный вход
        schema:
          properties:
            status: {type: string, example: "success"}
            user_id: {type: integer, example: 1}
      401:
        description: Неверный логин или пароль
    """
    data = request.get_json()
    conn = get_db_connection()
    user = conn.execute('SELECT id, password FROM users WHERE username = ?', (data['username'],)).fetchone()
    conn.close()
    if user and check_password_hash(user['password'], data['password']):
        return jsonify({"status": "success", "user_id": user['id']}), 200
    return jsonify({"status": "error", "message": "Неверный логин или пароль"}), 401


@app.route('/get_data', methods=['POST'])
def get_data():
    """
    Данные профиля пользователя
    ---
    parameters:
      - name: body
        in: body
        required: true
        schema:
          properties:
            id: {type: integer, example: 1}
    responses:
      200:
        description: Данные профиля возвращены
        schema:
          properties:
            status: {type: string, example: "success"}
            username: {type: string}
            phone: {type: string}
            event: {type: array, items: {type: string}}
            list_task: {type: array, items: {type: string}}
      404:
        description: Пользователь не найден
    """
    data = request.get_json()
    conn = get_db_connection()
    user = conn.execute('SELECT username, phone, event, list_task FROM users WHERE id = ?', (data['id'],)).fetchone()
    conn.close()
    if user:
        return jsonify({
            'status': 'success',
            'username': user['username'],
            'phone': user['phone'],
            'event': json.loads(user['event']) if user['event'] else [],
            'list_task': json.loads(user['list_task']) if user['list_task'] else []
        })
    return jsonify({'status': 'error', 'message': 'User not found'}), 404


@app.route('/upload_data', methods=['POST'])
def upload_data():
    """
    Добавить ID событий или задач в список пользователя
    ---
    parameters:
      - name: body
        in: body
        required: true
        schema:
          properties:
            id: {type: integer, example: 1}
            event: {type: array, items: {type: string}, example: ["1"]}
            list_task: {type: array, items: {type: string}, example: ["5"]}
    responses:
      200:
        description: Данные успешно обновлены
        schema:
          properties:
            status: {type: string, example: "success"}
    """
    data = request.get_json()
    user_id = data.get('id')
    conn = get_db_connection()
    db_data = conn.execute('SELECT list_task, event FROM users WHERE id = ?', (user_id,)).fetchone()
    if not db_data:
        conn.close()
        return jsonify({"status": "error", "message": "User not found"}), 404

    updated_tasks = (json.loads(db_data['list_task']) if db_data['list_task'] else []) + data.get('list_task', [])
    updated_events = (json.loads(db_data['event']) if db_data['event'] else []) + data.get('event', [])

    conn.execute('UPDATE users SET list_task = ?, event = ? WHERE id = ?',
                 (json.dumps(updated_tasks, ensure_ascii=False), json.dumps(updated_events, ensure_ascii=False),
                  user_id))
    conn.commit()
    conn.close()
    return jsonify({"status": "success"})


# --- МЕТОДЫ ОБЩИХ СОБЫТИЙ И ЗАДАЧ ---

@app.route('/add_event', methods=['POST'])
def add_event():
    """
    Создать новое общее событие
    ---
    parameters:
      - name: body
        in: body
        required: true
        schema:
          properties:
            name: {type: string, example: "Конференция"}
            description: {type: string, example: "Описание"}
            attach: {type: string, example: "link"}
    responses:
      201:
        description: Событие создано
        schema:
          properties:
            status: {type: string}
            event_id: {type: integer}
    """
    data = request.get_json()
    conn = get_db_connection()
    try:
        cursor = conn.execute(
            'INSERT INTO events (name, description, attach, date, users_event) VALUES (?, ?, ?, ?, ?)',
            (data['name'], data.get('description', ""), data.get('attach', ""), data.get('date', ""), json.dumps([])))

        event_id = cursor.lastrowid
        conn.commit()
        return jsonify({"status": "success", "event_id": event_id}), 201
    except sqlite3.IntegrityError:
        return jsonify({"status": "error", "message": "Событие уже существует"}), 400
    finally:
        conn.close()


@app.route('/add_task', methods=['POST'])
def add_task():
    """
    Создать новую общую задачу
    ---
    parameters:
      - name: body
        in: body
        required: true
        schema:
          properties:
            name: {type: string, example: "ДЗ по Математике"}
            description: {type: string, example: "Параграф 5"}
            attach: {type: string, example: "link"}
    responses:
      201:
        description: Задача создана
        schema:
          properties:
            status: {type: string}
            task_id: {type: integer}
    """
    data = request.get_json()
    conn = get_db_connection()
    try:
        cursor = conn.execute('INSERT INTO tasks (name, description, attach) VALUES (?, ?, ?)',
                              (data['name'], data.get('description', ""), data.get('attach', "")))
        task_id = cursor.lastrowid
        conn.commit()
        return jsonify({"status": "success", "task_id": task_id}), 201
    except sqlite3.IntegrityError:
        return jsonify({"status": "error", "message": "Задача уже существует"}), 400
    finally:
        conn.close()


@app.route('/get_all_events', methods=['GET'])
def get_all_events():
    """
    Получить список всех событий
    ---
    responses:
      200:
        description: Массив всех событий
        schema:
          type: array
          items:
            properties:
              id_event: {type: integer}
              name: {type: string}
              description: {type: string}
              attach: {type: string}
    """
    conn = get_db_connection()
    events = conn.execute('SELECT * FROM events').fetchall()
    conn.close()
    return jsonify([dict(row) for row in events])


@app.route('/get_all_tasks', methods=['GET'])
def get_all_tasks():
    """
    Получить список всех задач
    ---
    responses:
      200:
        description: Массив всех задач
        schema:
          type: array
          items:
            properties:
              id_tasks: {type: integer}
              name: {type: string}
              description: {type: string}
              attach: {type: string}
    """
    conn = get_db_connection()
    tasks = conn.execute('SELECT * FROM tasks').fetchall()
    conn.close()
    return jsonify([dict(row) for row in tasks])


@app.route('/attendance', methods=['POST'])
def attendance():
    import datetime
    data = request.get_json()
    conn = get_db_connection()
    try:
        date = conn.execute('SELECT date, users_event FROM events WHERE id_event = ?',
                            (data.get("id_event"))).fetchone()
        conn.close()
        if datetime.date.today() < date['date'] and date['users_event']:
            return jsonify({"status": "success", "message": "Событие случилось"}), 200
        else:
            return jsonify({"status": "success", "message": "Событие не случилось"}), 200
    except sqlite3.IntegrityError:
        return jsonify({"status": "error"}), 400


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
