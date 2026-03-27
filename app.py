import sqlite3
import json
import os
import datetime
from flask import Flask, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from flasgger import Swagger

app = Flask(__name__)
app.json.ensure_ascii = False

# Настройка Swagger
app.config['SWAGGER'] = {
    'title': 'School Management API',
    'uiversion': 3,
    'description': 'API для управления событиями, задачами и аналитикой посещаемости'
}
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
            points INTEGER DEFAULT 0, -- НОВОЕ ПОЛЕ
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


# --- МЕТОДЫ ПОЛЬЗОВАТЕЛЕЙ (Без изменений) ---

@app.route('/register', methods=['POST'])
def register():
    """
    Регистрация нового пользователя
    ---
    tags: [Users]
    parameters:
      - name: body
        in: body
        required: true
        schema:
          properties:
            username: {type: string, example: "ivanov_jr"}
            phone: {type: string, example: "89991234567"}
            password: {type: string, example: "qwerty123"}
            is_admin: {type: integer, enum: [0, 1], example: 0}
    responses:
      201:
        description: Пользователь успешно создан
      400:
        description: Ошибка валидации или пользователь уже существует
    """
    data = request.get_json()
    conn = get_db_connection()
    try:
        if data['username'] and data['phone']:
            hashed_pw = generate_password_hash(data['password'])
            cursor = conn.execute(
                'INSERT INTO users (username, phone, password, event, list_task, points, is_admin) VALUES (?, ?, ?, ?, ?, ?, ?)',
                (data['username'], data['phone'], hashed_pw, json.dumps([]), json.dumps([]), 0, data['is_admin'])
            )
            user_id = cursor.lastrowid
            conn.commit()
            return jsonify({"status": "success", "user_id": user_id}), 201
        return jsonify({"status": "error", "message": 'non_string'}), 400
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400
    finally:
        conn.close()


@app.route('/login', methods=['POST'])
def login():
    """
    Авторизация пользователя
    ---
    tags: [Users]
    parameters:
      - name: body
        in: body
        required: true
        schema:
          properties:
            username: {type: string, example: "ivanov_jr"}
            password: {type: string, example: "qwerty123"}
    responses:
      200:
        description: Авторизация успешна
      401:
        description: Неверные учетные данные
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
    Получение данных профиля пользователя
    ---
    tags: [Users]
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
      404:
        description: Пользователь не найден
    """
    data = request.get_json()
    conn = get_db_connection()
    user = conn.execute('SELECT username, phone, event, list_task, points FROM users WHERE id = ?',
                        (data['id'],)).fetchone()
    conn.close()
    if user:
        return jsonify({
            'status': 'success',
            'username': user['username'],
            'phone': user['phone'],
            'points': user['points'],
            'event': json.loads(user['event']) if user['event'] else [],
            'list_task': json.loads(user['list_task']) if user['list_task'] else []
        })
    return jsonify({'status': 'error', 'message': 'User not found'}), 404


# --- АНАЛИТИКА И УПРАВЛЕНИЕ ---

@app.route('/upload_data', methods=['POST'])
def upload_data():
    """
    Привязка задач и событий к пользователю
    ---
    tags: [Operations]
    parameters:
      - name: body
        in: body
        required: true
        schema:
          properties:
            id: {type: integer, example: 1, description: "ID пользователя"}
            event: {type: array, items: {type: string}, example: ["1", "2"]}
            list_task: {type: array, items: {type: string}, example: ["101"]}
    responses:
      200:
        description: Списки успешно обновлены
    """
    data = request.get_json()
    user_id = data.get('id')
    conn = get_db_connection()
    try:
        db_data = conn.execute('SELECT list_task, event FROM users WHERE id = ?', (user_id,)).fetchone()
        if not db_data:
            return jsonify({"status": "error", "message": "User not found"}), 404

        current_tasks = json.loads(db_data['list_task']) if db_data['list_task'] else []
        for tid in data.get('list_task', []):
            if not any(t['id'] == tid for t in current_tasks):
                current_tasks.append({"id": tid, "status": "in_progress"})

        current_events = json.loads(db_data['event']) if db_data['event'] else []
        current_events.extend(data.get('event', []))

        conn.execute('UPDATE users SET list_task = ?, event = ? WHERE id = ?',
                     (json.dumps(current_tasks), json.dumps(list(set(current_events))), user_id))
        conn.commit()
        return jsonify({"status": "success"})
    finally:
        conn.close()


@app.route('/complete_task', methods=['POST'])
def complete_task():
    """
    Перевод задачи в статус 'выполнено' (и начисление очков)
    ---
    tags: [Operations]
    parameters:
      - name: body
        in: body
        required: true
        schema:
          properties:
            user_id: {type: integer, example: 1}
            task_id: {type: string, example: "101"}
    responses:
      200:
        description: Задача успешно завершена
    """
    data = request.get_json()
    u_id, t_id = data.get('user_id'), data.get('task_id')
    conn = get_db_connection()
    user = conn.execute('SELECT list_task FROM users WHERE id = ?', (u_id,)).fetchone()
    if user:
        tasks = json.loads(user['list_task'])
        found = False
        for t in tasks:
            if str(t['id']) == str(t_id) and t['status'] != 'completed':
                t['status'] = 'completed'
                found = True

        if found:
            # Обновляем задачи И начисляем +10 очков
            conn.execute('UPDATE users SET list_task = ?, points = points + 10 WHERE id = ?', (json.dumps(tasks), u_id))
            conn.commit()
            conn.close()
            return jsonify({"status": "success", "message": "Task completed, +10 points"})

    conn.close()
    return jsonify({"status": "error"}), 404


@app.route('/get_analytics', methods=['POST'])
def get_analytics():
    """
    Сводная статистика (посещаемость и задачи)
    ---
    tags: [Analytics]
    parameters:
      - name: body
        in: body
        required: true
        schema:
          properties:
            user_id: {type: integer, example: 1}
    responses:
      200:
        description: Статистика пользователя
        schema:
          properties:
            status: {type: string}
            tasks_completed: {type: integer}
            tasks_in_progress: {type: integer}
            events_joined: {type: integer}
    """
    data = request.get_json()
    u_id = data.get('user_id')
    conn = get_db_connection()
    user = conn.execute('SELECT list_task, event FROM users WHERE id = ?', (u_id,)).fetchone()
    if not user:
        conn.close()
        return jsonify({"status": "error"}), 404
    tasks = json.loads(user['list_task']) if user['list_task'] else []
    events = json.loads(user['event']) if user['event'] else []
    res = {
        "status": "success",
        "tasks_completed": len([t for t in tasks if t.get('status') == 'completed']),
        "tasks_in_progress": len([t for t in tasks if t.get('status') == 'in_progress']),
        "events_joined": len(events)
    }
    conn.close()
    return jsonify(res)


@app.route('/attendance', methods=['POST'])
def attendance():
    """
    Отметка присутствия на мероприятии
    ---
    tags: [Operations]
    parameters:
      - name: body
        in: body
        required: true
        schema:
          properties:
            id_event: {type: integer, example: 1}
            id_user: {type: integer, example: 1}
    responses:
      200:
        description: Посещение зафиксировано
      400:
        description: Слишком рано или неверные данные
    """
    data = request.get_json()
    e_id, u_id = data.get("id_event"), data.get("id_user")
    conn = get_db_connection()
    try:
        event = conn.execute('SELECT date, users_event FROM events WHERE id_event = ?', (e_id,)).fetchone()
        if not event:
            return jsonify({"status": "error", "message": "Event not found"}), 404
        current_ts = int(datetime.datetime.now().timestamp())
        if current_ts >= (event['date'] or 0):
            users_list = json.loads(event['users_event']) if event['users_event'] else []
            if u_id not in users_list:
                users_list.append(u_id)
                conn.execute('UPDATE events SET users_event = ? WHERE id_event = ?', (json.dumps(users_list), e_id))
                conn.commit()
            return jsonify({"status": "success", "message": "Посещение засчитано"}), 200
        return jsonify({"status": "error", "message": "Событие еще не началось"}), 400
    finally:
        conn.close()


# --- МЕТОДЫ СПИСКОВ И СОЗДАНИЯ ---

@app.route('/add_event', methods=['POST'])
def add_event():
    """
    Создание общего события
    ---
    tags: [Admin]
    parameters:
      - name: body
        in: body
        required: true
        schema:
          properties:
            name: {type: string, example: "День открытых дверей"}
            description: {type: string, example: "Встреча с абитуриентами"}
            attach: {type: string, example: "http://link.com/img.jpg"}
            date: {type: integer, example: 1711472400, description: "Unix Timestamp"}
    responses:
      201:
        description: Событие создано
    """
    data = request.get_json()
    conn = get_db_connection()
    try:
        cursor = conn.execute(
            'INSERT INTO events (name, description, attach, date, users_event) VALUES (?, ?, ?, ?, ?)',
            (data['name'], data.get('description', ""), data.get('attach', ""), data.get('date', 0), json.dumps([])))
        conn.commit()
        return jsonify({"status": "success", "event_id": cursor.lastrowid}), 201
    finally:
        conn.close()


@app.route('/get_all_events', methods=['GET'])
def get_all_events():
    """
    Список всех событий в системе
    ---
    tags: [Lists]
    responses:
      200:
        description: Массив всех событий
    """
    conn = get_db_connection()
    res = [dict(r) for r in conn.execute('SELECT * FROM events').fetchall()]
    conn.close()
    return jsonify(res)


@app.route('/add_task', methods=['POST'])
def add_task():
    """
    Создание общей задачи
    ---
    tags: [Admin]
    parameters:
      - name: body
        in: body
        required: true
        schema:
          properties:
            name: {type: string, example: "Подготовка отчета"}
            description: {type: string, example: "Сдать до конца недели"}
            attach: {type: string, example: "file_id_45"}
    """
    data = request.get_json()
    conn = get_db_connection()
    try:
        cursor = conn.execute('INSERT INTO tasks (name, description, attach) VALUES (?, ?, ?)',
                              (data['name'], data.get('description', ""), data.get('attach', "")))
        conn.commit()
        return jsonify({"status": "success", "task_id": cursor.lastrowid}), 201
    finally:
        conn.close()


@app.route('/get_all_tasks', methods=['GET'])
def get_all_tasks():
    """
    Список всех задач в системе
    ---
    tags: [Lists]
    responses:
      200:
        description: Массив всех задач
    """
    conn = get_db_connection()
    res = [dict(r) for r in conn.execute('SELECT * FROM tasks').fetchall()]
    conn.close()
    return jsonify(res)


@app.route('/get_all_users', methods=['GET'])
def get_all_users():
    """
    Список всех пользователей (для администрирования)
    ---
    tags: [Admin]
    responses:
      200:
        description: Массив участников
    """
    conn = get_db_connection()
    users = conn.execute('SELECT id, username, phone, points, is_admin FROM users').fetchall()
    conn.close()
    return jsonify([dict(row) for row in users])


@app.route('/get_sorted_users', methods=['GET'])
def get_sorted_users():
    """
    Получить список пользователей, отсортированных по загруженности
    ---
    tags: [Admin]
    parameters:
      - name: sort
        in: query
        type: string
        enum: [asc, desc]
        default: asc
        description: "asc - от менее загруженных к более, desc - наоборот"
    responses:
      200:
        description: Отсортированный список волонтеров с их нагрузкой
    """
    sort_type = request.args.get('sort', 'asc')
    conn = get_db_connection()

    try:
        users = conn.execute('SELECT id, username, phone, list_task, points, is_admin FROM users').fetchall()
        user_list = []

        for row in users:
            user_data = dict(row)
            tasks = json.loads(user_data['list_task']) if user_data['list_task'] else []
            active_tasks_count = len([t for t in tasks if t.get('status') == 'in_progress'])
            user_data['load_score'] = active_tasks_count
            user_data.pop('list_task')
            user_list.append(user_data)

        reverse_order = True if sort_type == 'desc' else False
        user_list.sort(key=lambda x: x['load_score'], reverse=reverse_order)

        return jsonify(user_list), 200
    finally:
        conn.close()


# --- НОВЫЙ МЕТОД: ТОП ЛИДЕРОВ ---

@app.route('/get_top_users', methods=['GET'])
def get_top_users():
    """
    Топ пользователей по очкам (пагинация)
    ---
    tags: [Analytics]
    parameters:
      - name: limit
        in: query
        type: integer
        default: 10
        description: "Сколько пользователей вернуть"
      - name: offset
        in: query
        type: integer
        default: 0
        description: "Сколько пропустить (например, 4 для старта с 5-го места)"
    responses:
      200:
        description: Список лидеров
    """
    limit = request.args.get('limit', 10, type=int)
    offset = request.args.get('offset', 0, type=int)
    conn = get_db_connection()
    try:
        query = 'SELECT id, username, points FROM users ORDER BY points DESC LIMIT ? OFFSET ?'
        users = conn.execute(query, (limit, offset)).fetchall()
        result = []
        for i, row in enumerate(users):
            d = dict(row)
            d['rank'] = offset + i + 1
            result.append(d)
        return jsonify(result), 200
    finally:
        conn.close()


# --- МЕТОДЫ ДЛЯ ВОЛОНТЕРОВ ---

@app.route('/get_free_tasks', methods=['GET'])
def get_free_tasks():
    """
    Получить список задач, которые еще не выбраны волонтерами
    ---
    tags: [Volunteer]
    responses:
      200:
        description: Список свободных задач
    """
    conn = get_db_connection()
    try:
        all_tasks = conn.execute('SELECT * FROM tasks').fetchall()
        all_users_data = conn.execute('SELECT list_task FROM users').fetchall()

        occupied_ids = set()
        for row in all_users_data:
            if row['list_task']:
                user_tasks = json.loads(row['list_task'])
                for t in user_tasks:
                    occupied_ids.add(str(t.get('id')))

        free_tasks = [dict(task) for task in all_tasks if str(task['id_tasks']) not in occupied_ids]
        return jsonify(free_tasks), 200
    finally:
        conn.close()


@app.route('/assign_task', methods=['POST'])
def assign_task():
    """
    Выбор волонтером свободной задачи
    ---
    tags: [Volunteer]
    parameters:
      - name: body
        in: body
        required: true
        schema:
          properties:
            user_id: {type: integer, example: 1}
            task_id: {type: string, example: "5"}
    responses:
      200:
        description: Задача успешно закреплена
    """
    data = request.get_json()
    u_id = data.get('user_id')
    t_id = str(data.get('task_id'))

    conn = get_db_connection()
    try:
        check_query = conn.execute("SELECT id FROM users WHERE list_task LIKE ?", (f'%"{t_id}"%',)).fetchone()
        if check_query:
            return jsonify({"status": "error", "message": "Task already assigned"}), 400

        user = conn.execute('SELECT list_task FROM users WHERE id = ?', (u_id,)).fetchone()
        if not user:
            return jsonify({"status": "error", "message": "User not found"}), 404

        current_tasks = json.loads(user['list_task']) if user['list_task'] else []
        current_tasks.append({"id": t_id, "status": "in_progress"})

        conn.execute('UPDATE users SET list_task = ? WHERE id = ?', (json.dumps(current_tasks), u_id))
        conn.commit()
        return jsonify({"status": "success", "message": "Task successfully assigned"}), 200
    finally:
        conn.close()


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)