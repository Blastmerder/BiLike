import sqlite3
from flask import Flask, request, jsonify
import json


app = Flask(__name__)
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
            class INTEGER CHECK (class IN (0, 1))
        )
    ''')
    conn.commit()
    conn.close()

def get_db_connection():
    conn = sqlite3.connect(db_name)
    conn.row_factory = sqlite3.Row
    return conn

init_db()


@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    conn = get_db_connection()
    try:
        cursor = conn.execute(
            'INSERT INTO users (username, phone, password, event, list_task, class) VALUES (?, ?, ?, ?, ?, ?)',
            (data['username'], data['phone'], data['password'], json.dumps([]), json.dumps([]), data['class'])
        )
        user_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return jsonify({"status": "success", "user_id": user_id}), 201
    except sqlite3.IntegrityError:
        return jsonify({"status": "error", "message": "User already exists"}), 400


@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    conn = get_db_connection()
    user = conn.execute(
        'SELECT id, username FROM users WHERE username = ? AND password = ?',
        (data['username'], data['password'])
    ).fetchone()
    conn.close()
    if user:
        return jsonify({"status": "success", "user_id": user['id']}), 200
    else:
        return jsonify({"status": "error", "message": "Неверный логин или пароль"}), 401


@app.route('/get_data', methods=['POST'])
def get_data():
    data = request.get_json()
    conn = get_db_connection()
    user = conn.execute(
        'SELECT username, phone, event, list_task FROM users WHERE id = ?',
        (data['id'],)
    ).fetchone()
    conn.close()
    if user:
        return jsonify({'status': 'success', 'username': user['username'], 'phone': user['phone'],
                        'event': user['event'], 'list_task': user['list_task']})
    else:
        return jsonify({'status': 'error', 'message': 'Ошибка'})


@app.route('/upload_data', methods=['POST'])
def upload_data():
    data = request.get_json()
    user_id = data.get('id')
    new_event = data.get('event', [])
    new_tasks = data.get('list_task', [])
    conn = get_db_connection()
    db_data = conn.execute(
        'SELECT list_task, event FROM users WHERE id = ?',
        (user_id,)
    ).fetchone()
    if db_data is None:
        conn.close()
        return jsonify({"status": "error", "message": "Пользователь не найден"}), 404
    old_tasks = json.loads(db_data['list_task']) if db_data['list_task'] else []
    old_events = json.loads(db_data['event']) if db_data['event'] else []
    updated_tasks = old_tasks + new_tasks
    updated_events = old_events + new_event
    conn.execute(
        'UPDATE users SET list_task = ?, event = ? WHERE id = ?',
        (json.dumps(updated_tasks, ensure_ascii=False),
         json.dumps(updated_events, ensure_ascii=False),
         user_id)
    )
    conn.commit()
    conn.close()
    return jsonify({"status": "success"})


if __name__ == '__main__':
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
