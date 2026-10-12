# -*- coding: utf-8 -*-
import base64
import json
import os
import re
import shutil
from sqlite3 import dbapi2 as sqlite3
from hashlib import md5
from datetime import datetime
from flask import Flask, request, session, url_for, redirect, \
    render_template, abort, g, flash, _app_ctx_stack
from openai import OpenAI
from werkzeug.security import check_password_hash, generate_password_hash
import time
import openai
from flask import Flask, render_template, request, jsonify, send_from_directory

#CONFIGURATION
DATABASE = 'book.db'
DEBUG = True
SECRET_KEY = 'development key'
MANAGER_NAME = 'root'
MANAGER_PWD = 'root'
app = Flask(__name__)
app.config['DEBUG'] = True
app.config.from_object(__name__)
app.config.from_envvar('FLASKR_SETTINGS', silent=True)


def get_db():
    top = _app_ctx_stack.top
    if not hasattr(top, 'sqlite_db'):
        top.sqlite_db = sqlite3.connect(app.config['DATABASE'])
        top.sqlite_db.row_factory = sqlite3.Row
    return top.sqlite_db


@app.teardown_appcontext
def close_database(exception):
    top = _app_ctx_stack.top
    if hasattr(top, 'sqlite_db'):
        top.sqlite_db.close()


def init_db():
    with app.app_context():
        db = get_db()
        with app.open_resource('book.sql', mode='r') as f:
            db.cursor().executescript(f.read())
        db.commit()


def query_db(query, args=(), one=False):
    cur = get_db().execute(query, args)
    rv = cur.fetchall()
    return (rv[0] if rv else None) if one else rv


def execute_db(query, args=()):
    """执行数据库操作（如 INSERT、UPDATE、DELETE）"""
    db = get_db()  # 获取数据库连接
    cursor = db.cursor()  # 创建游标
    try:
        cursor.execute(query, args)  # 执行 SQL 语句
        db.commit()  # 提交事务
    except sqlite3.Error as e:
        print(f"数据库操作失败: {e}")  # 打印错误信息
        raise e  # 抛出异常
    finally:
        cursor.close()  # 关闭游标


def check_table_structure():
    db = get_db()
    cursor = db.cursor()
    cursor.execute('PRAGMA table_info(users)')
    columns = cursor.fetchall()
    print("表结构:", columns)  # 输出表结构
    cursor.close()


def get_user_id(username):
    rv = query_db('select user_id from users where user_name = ?',
                  [username], one=True)
    return rv[0] if rv else None


def get_recommendations():
    db = get_db()
    cursor = db.cursor()

    try:
        cursor.execute('SELECT DISTINCT book_id FROM borrows')
        book_ids = cursor.fetchall()
        print(f"Book IDs: {book_ids}")  # 调试信息

        recommendations = []
        for book_id in book_ids:
            cursor.execute('SELECT book_id, book_name, data FROM books WHERE book_id = ?', (book_id['book_id'],))
            book_info = cursor.fetchone()

            if book_info:
                print(f"Book info: {book_info}")  # 调试信息

                image_data = base64.b64encode(book_info['data']).decode('utf-8')
                recommendations.append({
                    'id': book_info['book_id'],
                    'book_name': book_info['book_name'],
                    'image_data': image_data
                })

        return recommendations

    except sqlite3.Error as e:
        print("Database error:", e)
        return []
    finally:
        cursor.close()


@app.before_request
def before_request():
    g.user = None
    if 'user_id' in session:
        g.user = session['user_id']


@app.route('/')
def index():
    books_p = [
        {"book_name": "狗狗", "image_name": "b.png", "rating": 5.0},
        {"book_name": "柯基", "image_name": "f.png", "rating": 4.0},
        {"book_name": "萨摩耶", "image_name": "d.png", "rating": 3.0},
    ]

    # 找到评分最高的宠物
    top_pet = max(books_p, key=lambda pet: pet["rating"]) if books_p else None

    return render_template('index1.html', books_p=books_p, top_pet=top_pet)


@app.route('/manager_login', methods=['GET', 'POST'])
def manager_login():
    error = None
    if request.method == 'POST':
        manager = query_db('''select * from manager_info where manager_id = ?''',
                           [request.form['user_id']], one=True)
        if manager is None:
            error = 'Invalid username'
        elif not check_password_hash(manager['password'], request.form['password']):
            error = 'Invalid password'
        else:
            session['user_id'] = app.config['MANAGER_NAME']
            return redirect(url_for('manager'))
    return render_template('manager_login.html', error=error)


@app.route('/reader_login', methods=['GET', 'POST'])
def reader_login():
    error = None
    if request.method == 'POST':
        user = query_db('''select * from users where user_name = ?''',
                        [request.form['username']], one=True)
        if user is None:
            error = 'Invalid username'
        elif not check_password_hash(user['pwd'], request.form['password']):
            error = 'Invalid password'
        else:
            session['user_id'] = user['user_name']
            return redirect(url_for('reader'))
    return render_template('reader_login.html', error=error)


@app.route('/about', methods=['GET'])
def about():
    return render_template('about_us.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    error = None
    if request.method == 'POST':
        if not request.form['username']:
            error = 'You have to enter a username'
        elif not request.form['password']:
            error = 'You have to enter a password'
        elif request.form['password'] != request.form['password2']:
            error = 'The two passwords do not match'
        elif get_user_id(request.form['username']) is not None:
            error = 'The username is already taken'
        else:
            db = get_db()
            db.execute('''insert into users (user_name, pwd, college, num, email)
   values (?, ?, ?, ?, ?) ''', [request.form['username'], generate_password_hash(
                request.form['password']), request.form['college'], request.form['number'],
                                request.form['email']])
            db.commit()
            return redirect(url_for('reader_login'))
    return render_template('register.html', error=error)


from flask import Flask, request, jsonify


@app.route('/recommend_books', methods=['POST'])
@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('index'))


# 添加简单的安全性检查
def manager_judge():
    if not session.get('user_id'):
        error = 'Invalid manager, please login'
        return render_template('manager_login.html', error=error)
    else:
        return None


def reader_judge():
    if not session['user_id']:
        error = 'Invalid reader, please login'
        return render_template('reader_login.html', error=error)


@app.route('/manager/books')
def manager_books():
    manager_judge()
    return render_template('manager_books.html',
                           books=query_db('select * from books', []))


@app.route('/manager')
def manager():
    manager_judge()
    return render_template('manager.html')


@app.route('/reader')
def reader():
    reader_judge()
    return render_template('reader.html')


@app.route('/manager/users')
def manager_users():
    manager_judge()
    users = query_db('''select * from users''', [])
    return render_template('manager_users.html', users=users)


@app.route('/manager/user/modify/<id>', methods=['GET', 'POST'])
def manger_user_modify(id):
    # user_judge()
    error = None
    user = query_db('''select * from users where user_id = ?''', [id], one=True)
    if request.method == 'POST':
        if not request.form['username']:
            error = 'You have to input your name'
        elif not request.form['password']:
            db = get_db()
            db.execute('''update users set user_name=?, college=?, num=? \
				, email=? where user_id=? ''', [request.form['username'],
                                                request.form['college'], request.form['number'],
                                                request.form['email'], id])
            db.commit()
            return redirect(url_for('manager_user', id=id))
        else:
            db = get_db()
            db.execute('''update users
set user_name=?
  , pwd=?
  , college=?
  , num=?
  , email=?
where user_id = ? ''', [request.form['username'],
                        generate_password_hash(request.form['password']),
                        request.form['college'], request.form['number'],
                        request.form['email'], id])
            db.commit()
            return redirect(url_for('manager_user', id=id))
    return render_template('manager_user_modify.html', user=user, error=error)


@app.route('/manager/user/deleter/<id>', methods=['GET', 'POST'])
def manger_user_delete(id):
    manager_judge()
    db = get_db()
    db.execute('''delete from users where user_id=? ''', [id])
    db.commit()
    return redirect(url_for('manager_users'))


@app.route('/register_admin', methods=['GET', 'POST'])
def register_admin():
    error = None
    if request.method == 'POST':
        if not request.form.get('password'):
            error = 'You have to input your password'
        # 检查 manager_id 是否存在
        elif not request.form.get('manager_id'):
            error = 'You have to input your manager_id'
        else:
            # 获取表单数据
            password = request.form['password']
            manager_id = request.form['manager_id']

            # 连接数据库
            db = get_db()

            # 插入数据到数据库
            db.execute('''
                    INSERT INTO manager_info (manager_id, password)
                    VALUES (?, ?)
                ''', (manager_id, generate_password_hash(password)))
            db.commit()
            flash('Registration successful!', 'success')
        return redirect(url_for('manager_login'))
    return render_template('register_admin.html', error=error)


@app.route('/manager/books/add', methods=['GET', 'POST'])
def manager_books_add():
    manager_judge()
    error = None
    if request.method == 'POST':
        if not request.form['id']:
            error = 'You have to input the book ISBN'
        elif not request.form['name']:
            error = 'You have to input the book name'
        elif not request.form['author']:
            error = 'You have to input the book author'
        elif not request.form['company']:
            error = 'You have to input the publish company'
        elif not request.form['date']:
            error = 'You have to input the publish date'
        else:
            db = get_db()
            db.execute('''insert into books (book_id, book_name, author, publish_com,
				publish_date) values (?, ?, ?, ?, ?) ''', [request.form['id'],
                                                           request.form['name'], request.form['author'],
                                                           request.form['company'],
                                                           request.form['date']])
            db.commit()
            return redirect(url_for('manager_books'))
    return render_template('manager_books_add.html', error=error)


@app.route('/manager/books/delete', methods=['GET', 'POST'])
def manager_books_delete():
    manager_judge()
    error = None
    if request.method == 'POST':
        if not request.form['id']:
            error = 'You have to input the book name'
        else:
            book = query_db('''select * from books where book_id = ?''',
                            [request.form['id']], one=True)
            if book is None:
                error = 'Invalid book id'
            else:
                db = get_db()
                db.execute('''delete from books where book_id=? ''', [request.form['id']])
                db.commit()
                return redirect(url_for('manager_books'))
    return render_template('manager_books_delete.html', error=error)


@app.route('/manager/book/<id>', methods=['GET', 'POST'])
def manager_book(id):
    manager_judge()
    book = query_db('''select * from books where book_id = ?''', [id], one=True)
    reader = query_db('''select * from borrows where book_id = ?''', [id], one=True)
    name = query_db('''select user_name from borrows where book_id = ?''', [id], one=True)

    current_time = time.strftime('%Y-%m-%d', time.localtime(time.time()))
    if request.method == 'POST':
        db = get_db()
        db.execute('''update histroys set status = ?, date_return = ?  where book_id=?
			and user_name=? and status=? ''',
                   ['retruned', current_time, id, name[0], 'not return'])
        db.execute('''delete from borrows where book_id = ? ''', [id])
        db.commit()
        return redirect(url_for('manager_book', id=id))

    return render_template('manager_book.html', book=book, reader=reader)


@app.route('/manager/user/<id>', methods=['GET', 'POST'])
def manager_user(id):
    manager_judge()
    user = query_db('''select * from users where user_id = ?''', [id], one=True)
    books = None
    return render_template('manager_userinfo.html', user=user, books=books)


@app.route('/manager/modify/<id>', methods=['GET', 'POST'])
def manager_modify(id):
    manager_judge()
    error = None
    book = query_db('''select * from books where book_id = ?''', [id], one=True)
    if request.method == 'POST':
        if not request.form['name']:
            error = 'You have to input the book name'
        elif not request.form['author']:
            error = 'You have to input the book author'
        elif not request.form['company']:
            error = 'You have to input the publish company'
        elif not request.form['date']:
            error = 'You have to input the publish date'
        else:
            db = get_db()
            db.execute('''update books set book_name=?, author=?, publish_com=?, publish_date=? where book_id=? ''',
                       [request.form['name'], request.form['author'], request.form['company'], request.form['date'],
                        id])
            db.commit()
            return redirect(url_for('manager_book', id=id))
    return render_template('manager_modify.html', book=book, error=error)


@app.route('/reader/info', methods=['GET', 'POST'])
def reader_info():
    reader_judge()
    user = query_db('''SELECT * FROM users WHERE user_name=? ''', [g.user], one=True)

    if request.method == 'POST':
        user_tag = request.form.get('user_tag')  # 获取用户选择的标签
        if user_tag:
            # 更新用户标签到数据库
            execute_db('''UPDATE users SET college=? WHERE user_name=?''', [user_tag, g.user])
            flash('标签已更新！', 'success')
        else:
            flash('请选择一个标签！', 'error')

    return render_template('reader_info.html', user=user)


@app.route('/reader/modify', methods=['GET', 'POST'])
def reader_modify():
    reader_judge()
    error = None
    user = query_db('''select * from users where user_name = ?''', [g.user], one=True)
    id = user[0]
    if request.method == 'POST':
        if not request.form['username']:
            error = 'You have to input your name'
        elif not request.form['password']:
            db = get_db()
            db.execute('''update users set user_name=?, college=?, num=? \
				, email=? where user_id=? ''', [request.form['username'],
                                                request.form['college'], request.form['number'],
                                                request.form['email'], id])
            db.commit()
            return redirect(url_for('reader_info'))
        else:
            db = get_db()
            db.execute('''update users set user_name=?, pwd=?, college=?, num=? \
				, email=? where user_id=? ''', [request.form['username'],
                                                generate_password_hash(request.form['password']),
                                                request.form['college'], request.form['number'],
                                                request.form['email'], id])
            db.commit()
            return redirect(url_for('reader_info'))
    return render_template('reader_modify.html', user=user, error=error)


def reader_want():
    reader_judge()


@app.route('/reader/query', methods=['GET', 'POST'])
def reader_query():
    reader_judge()
    error = None
    books = None
    if request.method == 'POST':
        if request.form['item'] == 'name':
            if not request.form['query']:
                error = 'You have to input the book name'
            else:
                books = query_db('''select * from books where book_name = ?''',
                                 [request.form['query']])
                if not books:
                    error = 'Invalid book name'
        else:
            if not request.form['query']:
                error = 'You have to input the book author'
            else:
                books = query_db('''select * from books where author = ?''',
                                 [request.form['query']])
                if not books:
                    error = 'Invalid book author'
    return render_template('reader_query.html', books=books, error=error)


@app.route('/reader/book/<id>', methods=['GET', 'POST'])
def reader_book(id):
    reader_judge()
    error = None
    book = query_db('''select * from books where book_id = ?''', [id], one=True)
    reader = query_db('''select * from borrows where book_id = ?''', [id], one=True)
    count = query_db('''select count(book_id) from borrows where user_name = ? ''',
                     [g.user], one=True)

    current_time = time.strftime('%Y-%m-%d', time.localtime(time.time()))
    return_time = time.strftime('%Y-%m-%d', time.localtime(time.time() + 2600000))
    if request.method == 'POST':
        if reader:
            error = 'The book has already borrowed.'
        else:
            if count[0] == 3:
                error = 'You can\'t borrow more than three books.'
            else:
                db = get_db()
                db.execute('''insert into borrows (user_name, book_id, date_borrow, 
					date_return) values (?, ?, ?, ?) ''', [g.user, id,
                                                           current_time, return_time])
                db.execute('''insert into histroys (user_name, book_id, date_borrow, 
					status) values (?, ?, ?, ?) ''', [g.user, id,
                                                      current_time, 'not return'])
                db.commit()
                return redirect(url_for('reader_book', id=id))
    return render_template('reader_book.html', book=book, reader=reader, error=error)


@app.route('/reader/histroy', methods=['GET', 'POST'])
def reader_histroy():
    reader_judge()
    histroys = query_db(
        '''select * from histroys, books where histroys.book_id = books.book_id and histroys.user_name=? ''', [g.user],
        one=False)

    return render_template('reader_histroy.html', histroys=histroys)


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()


def get_book_by_name(book_name):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM books WHERE book_name = ?", (book_name,))
    book = cursor.fetchone()
    cursor.close()
    return book


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()


@app.route('/remark', methods=['GET', 'POST'])
def remark():
    if request.method == 'POST':
        book_name = request.form.get('book_name')
        if not book_name:
            return "书籍名称未提供", 400
        book = get_book_by_name(book_name)
        if not book:
            return "书籍未找到", 404

        name = request.form.get('name')
        rating = request.form.get('rating')
        review_text = request.form.get('review')

        if not all([name, rating, review_text]):
            return "所有字段都是必填的", 400

        db = get_db()
        try:
            with db:
                cursor = db.cursor()
                cursor.execute("INSERT INTO reviews (name, rating, review_text, book_id) VALUES (?, ?, ?, ?)",
                               (name, rating, review_text, book['book_id']))
        except sqlite3.IntegrityError as e:
            app.logger.error(f"Database error: {e}")
            return "内部服务器错误", 500
        return redirect(url_for('remark', book_name=book_name))
    else:
        book_name = request.args.get('book_name')
        if not book_name:
            return "书籍名称未提供", 400
        book = get_book_by_name(book_name)
        print(book)
        if not book:
            return "书籍未找到", 404
        db = get_db()
        with db:
            cursor = db.cursor()
            cursor.execute('SELECT * FROM reviews WHERE book_id = ?', [book['book_id']])
            reviews = cursor.fetchall()
            print(reviews)

            return render_template('remark.html', book=book, reviews=reviews)


class OpenApiConnect:
    def __init__(self, model_pattern, temperature=1):
        self.temperature = temperature
        self.__api_key = 'sk-RHOoG7f0dNDwQ6yQvmHkfz8N7QHXWTJcQIteGNrI7loI1Rv6'
        self.__api_url = 'https://api.wlai.vip/v1'

    def get_response(self, messages, model_pattern):
        client = openai.OpenAI(
            base_url=self.__api_url,
            api_key=self.__api_key,
        )
        response = client.chat.completions.create(
            model=model_pattern,
            messages=messages,
            temperature=self.temperature,
        )
        if response and hasattr(response, 'choices'):
            if response.choices:
                assistant_response_content = response.choices[0].message.content
                return assistant_response_content
            else:
                return 'No choice available in the response'
        else:
            return 'Invalid response'


def get_openai_conn(model_pattern):
    return OpenApiConnect(model_pattern)


def convert_to_openai_messages(chat_history):
    messages = []
    for history in chat_history:
        role = history.get('role', history.get('sender'))
        if role == 'w':
            role = 'user'
        elif role not in ['system', 'assistant', 'user', 'function']:
            role = 'user'

        content = history.get('content', history.get('message', ''))
        messages.append({"role": role, "content": content})
    return messages


@app.route('/gpt')
def gpt():
    return render_template('gpt_me.html')


@app.route('/images/<filename>')
def serve_images(filename):
    return send_from_directory('templates/images', filename)


@app.route('/js/<filename>')
def serve_js(filename):
    return send_from_directory('templates/js', filename)


@app.route('/css/<filename>')
def serve_css(filename):
    return send_from_directory('templates/css', filename)


# 全局配置
MAX_RETRIES = 3  # 最大重试次数
RETRY_DELAY = 2  # 重试延迟时间（秒）


@app.route('/get_gpt_response', methods=['POST'])
def get_gpt_response():
    try:
        # 获取请求的 JSON 数据
        data = request.json

        # 提取请求中的关键信息
        user_message = data.get('message')
        chat_history = data.get('chatHistory', [])
        model_pattern = data.get('model_pattern')
        json_file = data.get('jsonFile')

        # 验证用户消息是否为空
        if not user_message:
            return jsonify({'error': 'Please enter a message.'}), 400

        # 验证 JSON 文件参数是否存在
        if not json_file:
            return jsonify({'error': 'jsonFile parameter is missing.'}), 400

        # 构建 JSON 文件的完整路径
        base_dir = os.path.dirname(os.path.abspath(__file__))
        json_file_path = os.path.join(base_dir, json_file)

        # 尝试读取角色描述文件
        try:
            with open(json_file_path, 'r', encoding='utf-8') as file:
                role_description = json.load(file)
                role_description_str = f"你现在扮演{role_description['role']}，{role_description['description']}"
        except FileNotFoundError:
            return jsonify({'error': f'Role description JSON file {json_file} not found.'}), 400
        except json.JSONDecodeError:
            return jsonify(
                {'error': f'Role description JSON file {json_file} 格式错误，请检查文件内容是否为有效的 JSON。'}), 400

        # 构建系统消息和新的消息列表
        system_message = {"role": "system", "content": role_description_str}
        new_messages = [system_message] + chat_history + [{"role": 'user', "content": user_message}]

        # 获取 OpenAI 连接
        openai_conn = get_openai_conn(model_pattern)
        messages = convert_to_openai_messages(new_messages)

        # 重试机制，尝试调用 OpenAI 接口
        for attempt in range(MAX_RETRIES):
            try:
                # 调用 OpenAI 接口获取回复
                assistant_response = openai_conn.get_response(messages, model_pattern)
                return jsonify({'reply': assistant_response,
                                'role': role_description['role'], }
                               )
            except openai.error.OpenAIError as e:
                # OpenAI 服务错误处理
                if attempt < MAX_RETRIES - 1:
                    print(f"请求失败，错误信息: {e}，将在 {RETRY_DELAY} 秒后重试...")
                    time.sleep(RETRY_DELAY)
                else:
                    return jsonify({'error': f'请求重试 {MAX_RETRIES} 次后仍然失败，错误信息: {e}'}), 503
            except Exception as e:
                # 捕获其他未知错误
                return jsonify({'error': f'发生未知错误: {e}'}), 500

    except Exception as e:
        # 捕获请求处理中的任何其他错误
        return jsonify({'error': f'请求处理出错: {e}'}), 500


# 初始化 OpenAI 客户端
client = OpenAI(base_url="https://yunwu.ai/v1",
                api_key="sk-DtqUh94seeYdFpOr6jv1WVREBN9TXaDKZbfLadE52Oz1ADjV")


@app.route('/upload-avatar', methods=['POST'])
def upload_avatar():
    global full_path
    try:
        # 获取上传的图片
        uploaded_file = request.files.get('image')
        print(uploaded_file)
        match = re.search(r"'([^']+)'", str(uploaded_file))
        if match:
            filename = match.group(1)
            base_path = r"D:\宠物聊天系统\templates\images"
            full_path = f"{base_path}\\{filename}"
            print(full_path)
        else:
            print("未找到有效的文件名。")
        if not uploaded_file:
            return jsonify({'success': False, 'error': '未上传图片'})

        # 调用 OpenAI API 处理图片
        prompt = "转换成动漫的风格"
        result = client.images.edit(
            model="gpt-image-1",
            image=open(str(full_path), 'rb'),
            prompt=prompt
        )

        # 获取处理后的图片数据
        image_base64 = result.data[0].b64_json
        image_bytes = base64.b64decode(image_base64)

        # 保存处理后的图片到服务器
        processed_image_path = "static/processed-avatar.png"
        with open(processed_image_path, "wb") as f:
            f.write(image_bytes)
            print(f'已保存到{processed_image_path}')

        # 目标路径
        target_path = r"D:\宠物聊天系统\templates\images\processed-avatar.png"

        try:
            # 复制文件
            shutil.copy2(processed_image_path, target_path)
            print(f'已成功复制到{target_path}')
        except FileNotFoundError:
            print("源文件未找到，请检查路径是否正确。")
        except PermissionError:
            print("没有足够的权限进行文件复制操作，请检查文件和目标文件夹的权限设置。")
        except Exception as e:
            print(f"发生未知错误：{e}")

        # 返回处理后的图片路径给前端
        return jsonify({'success': True, 'image_url': f'/{processed_image_path}'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/diary')
def diary():
    return render_template('diary.html')


@app.route('/get-diary', methods=['POST'])
def get_diary():
    try:
        # 获取前端传来的 chatHistory
        data = request.json
        chat_history = data.get('chatHistory', [])

        # 将 chatHistory 转换为文本
        diary_text = ""
        for entry in chat_history:
            sender = entry.get('sender', '未知')
            message = entry.get('message', '')
            diary_text += f"{sender}: {message}\n\n"

        return jsonify({'success': True, 'text': diary_text})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/remark_pet', methods=['GET'])
def remark_pet():
    return render_template('remark_pet.html')


if __name__ == '__main__':
    init_db()
    app.run(debug=True)
