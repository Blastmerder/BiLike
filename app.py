import sqlite3
from flask import Flask, request, jsonify

app = Flask(__name__)
db_name = 'epshtein.db'
def init_db_epshtein():
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            phone TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            class INTEGER CHECK (class IN (0, 1))
        )
    ''')
    conn.commit()
    conn.close()

def get_db_connection():
    conn = sqlite3.connect(db_name)
    conn.row_factory = sqlite3.Row
    return conn

init_db_epshtein()


@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    conn = get_db_connection()
    try:
        cursor = conn.execute(
            'INSERT INTO users (username, phone, password, class) VALUES (?, ?, ?, ?)',
            (data['username'], data['phone'], data['password'], data['class'])
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

if __name__ == '__main__':
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
