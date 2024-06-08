from flask_sqlalchemy import SQLAlchemy
from flask import Flask, render_template, request, flash, redirect, url_for
import os
import click
from flask_login import LoginManager, UserMixin
from flask_login import current_user, logout_user, login_user, login_required
from datetime import datetime

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(app.root_path, 'data.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev')
db = SQLAlchemy(app)

login_manager = LoginManager(app)


@login_manager.user_loader
def load_user(user_name):
    user = User.query.get(user_name)
    if user:
        return user
    else:
        administrator = Administrator.query.get(user_name)
        return administrator


login_manager.login_view = 'login'


class User(db.Model, UserMixin):
    name = db.Column(db.String(20), primary_key=True)
    password = db.Column(db.String(50))

    def get_id(self):
        return self.name


class Book(db.Model):
    id = db.Column(db.String(3), primary_key=True)
    title = db.Column(db.String(20))
    writer = db.Column(db.String(20))
    press = db.Column(db.String(50))
    kind = db.Column(db.String(20))
    total = db.Column(db.Integer)
    available = db.Column(db.Integer)
    is_available = db.Column(db.Boolean, default=True)


class BorrowRecord(db.Model):
    id = db.Column(db.String(3), db.ForeignKey('book.id'), primary_key=True)
    reader = db.Column(db.String(20), db.ForeignKey('user.name'), primary_key=True)
    borrow_time = db.Column(db.String(20), primary_key=True)
    return_time = db.Column(db.String(20))
    return_status = db.Column(db.String(20))

    # 添加外键关联；borrow_records允许User类型来访问BorrowRecord，只能有一个外键，不能把book中的title和id同时作为外键否则会出现错误
    user = db.relationship('User', backref=db.backref('user_borrow_records', lazy='dynamic'), foreign_keys=[reader])
    book = db.relationship('Book', backref=db.backref('book_borrow_records', lazy='dynamic'), foreign_keys=[id])


class Administrator(db.Model, UserMixin):
    name = db.Column(db.String(20), primary_key=True)
    password = db.Column(db.String(50))

    def get_id(self):
        return self.name


@app.cli.command()
@click.option('--drop', is_flag=True, help='Create after drop.')
def initdb(drop):
    """Initialize the database."""
    if drop:
        db.drop_all()
    db.create_all()
    click.echo('Initialized database.')


# 管理员登录
@app.cli.command()
@click.option('--username', prompt=True, help='The username used to login.')
@click.option('--password', prompt=True, hide_input=True, confirmation_prompt=True, help='The password used to login.')
def admin(username, password):
    """Create Administrator."""
    user = User.query.filter_by(name=username).first()
    if user is not None:
        click.echo('User already exist...')
    else:
        click.echo('Creating user...')
        administrator = Administrator(name=username, password=password)
        db.session.add(administrator)
        db.session.commit()
        click.echo('User created.')


@app.errorhandler(404)  # 传入要处理的错误代码
def page_not_found(e):  # 接受异常对象作为参数
    flag = 0
    if isinstance(current_user, User):
        flag = 1
    elif isinstance(current_user, Administrator):
        flag = 2
    return render_template('errors/404.html', flag=flag), 404


@app.errorhandler(400)
def bad_request(e):
    flag = 0
    if isinstance(current_user, User):
        flag = 1
    elif isinstance(current_user, Administrator):
        flag = 2
    return render_template('errors/400.html', flag=flag), 400


@app.errorhandler(500)
def internal_server_error(e):
    flag = 0
    if isinstance(current_user, User):
        flag = 1
    elif isinstance(current_user, Administrator):
        flag = 2
    return render_template('errors/500.html', flag=flag), 500


@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if not username or not password:
            flash('Please enter')
            return redirect(url_for('login'))

        user = User.query.filter_by(name=username).first()
        if user is None:
            flash('User does not exist')
            return redirect(url_for('login'))
        if user.password != password:
            flash('Wrong password')
            return redirect(url_for('login'))

        login_user(user)
        return redirect(url_for('reader_borrow'))

    return render_template('login.html')


@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if not username or not password:
            flash('Please enter')
            return redirect(url_for('admin_login'))

        administrator = Administrator.query.filter_by(name=username).first()
        if administrator is None:
            flash('User does not exist')
            return redirect(url_for('admin_login'))
        if administrator.password != password:
            flash('Wrong password')
            return redirect(url_for('admin_login'))

        login_user(administrator)
        return redirect(url_for('book_manage'))

    return render_template('admin_login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        re_password = request.form['re_password']

        if not username or not password or not re_password:
            flash('Please enter')
            return redirect(url_for('register'))

        user = User.query.filter_by(name=username).first()
        if user is not None:
            flash('User already exists')
            return redirect(url_for('login'))

        if password != re_password:
            flash('Passwords do not match')
            return redirect(url_for('register'))

        user = User(name=username, password=password)
        db.session.add(user)
        db.session.commit()

        return redirect(url_for('login'))

    return render_template('register.html')


# 管理端

# 书籍管理
@app.route('/manage/book_manage', methods=['POST', 'GET'])
@login_required
def book_manage():
    if not isinstance(current_user, Administrator):
        flash("Access denied - Administrators only!")
        return redirect(url_for('index'))
    books = Book.query.filter_by(is_available=True).all()
    return render_template('/manage/book_manage.html', books=books)


# 添加图书
@app.route('/manage/book_add', methods=['GET', 'POST'])
@login_required
def book_add():
    if not isinstance(current_user, Administrator):
        flash("Access denied - Administrators only!")
        return redirect(url_for('index'))

    if request.method == 'POST':
        id = request.form['id']
        title = request.form['title']
        writer = request.form['writer']
        press = request.form['press']
        kind = request.form['kind']
        total = request.form['total']
        available = request.form['available']

        if not id or not title or not writer or not press or not kind or not total or not available:
            flash('Please enter')
            return redirect(url_for('add_book'))
        ex_book = Book.query.filter_by(id=id).first()
        if ex_book is not None:
            if ex_book.is_available is True:
                flash('Book already exists')
                return redirect(url_for('add_book'))
            else:
                ex_book.title = title
                ex_book.writer = writer
                ex_book.press = press
                ex_book.kind = kind
                ex_book.total = total
                ex_book.available = available
                ex_book.is_available = True
                db.session.commit()
                return redirect(url_for('book_manage'))
        book = Book(id=id, title=title, writer=writer, press=press, kind=kind, total=total, available=available)
        db.session.add(book)
        db.session.commit()

        return redirect(url_for('book_manage'))

    return render_template('/manage/book_add.html')


# 查找书籍
@app.route('/manage/book_search', methods=['GET', 'POST'])
@login_required
def book_search():
    if not isinstance(current_user, Administrator):
        flash("Access denied - Administrators only!")
        return redirect(url_for('index'))

    book_id = request.form['id']
    book = Book.query.filter((Book.id == book_id) & (Book.is_available == True)).first()
    if book is None:
        flash('书籍不存在或者已被下架')
        return redirect(url_for('book_manage'))

    return render_template('/manage/book_search.html', book=book)


# 下架书籍  是直接删除还是修改可借阅数为0？
@app.route('/manage/book_delete/<string:book_id>', methods=['GET', 'POST'])
@login_required
def book_delete(book_id):
    if not isinstance(current_user, Administrator):
        flash("Access denied - Administrators only!")
        return redirect(url_for('index'))

    book = Book.query.get_or_404(book_id)
    is_record = BorrowRecord.query.filter((BorrowRecord.id == book_id) & (BorrowRecord.return_status == "未归还")).first()
    if is_record is not None:
        flash('有书籍正在出借，书籍无法下架')
        return redirect(url_for('book_manage'))
    book.is_available = False
    db.session.commit()
    flash('书籍下架成功')
    return redirect(url_for('book_manage'))


# 修改书籍
@app.route('/manage/book_edit/<string:book_id>', methods=['GET', 'POST'])
@login_required
def book_edit(book_id):
    if not isinstance(current_user, Administrator):
        flash("Access denied - Administrators only!")
        return redirect(url_for('index'))

    book = Book.query.get_or_404(book_id)

    if request.method == 'POST':
        book.title = request.form['title']
        book.writer = request.form['writer']
        book.press = request.form['press']
        book.kind = request.form['kind']
        book.total = request.form['total']
        book.available = request.form['available']

        db.session.commit()
        flash('Book updated')
        return redirect(url_for('book_manage'))

    return render_template('/manage/book_edit.html', book=book)


# 用户管理
@app.route('/manage/user_manage', methods=['GET', 'POST'])
@login_required
def user_manage():
    if not isinstance(current_user, Administrator):
        flash("Access denied - Administrators only!")
        return redirect(url_for('index'))

    users = User.query.all()
    return render_template('/manage/user_manage.html', users=users)


# 搜索用户
@app.route('/manage/user_search', methods=['GET', 'POST'])
@login_required
def user_search():
    if not isinstance(current_user, Administrator):
        flash("Access denied - Administrators only!")
        return redirect(url_for('index'))

    user_name = request.form['name']
    user = User.query.filter_by(name=user_name).first()
    if user is None:
        flash('User does not exist')
        return redirect(url_for('user_manage'))

    return render_template('/manage/user_search.html')


# 修改用户信息（密码）
@app.route('/manage/user_edit/<string:user_name>', methods=['GET', 'POST'])
@login_required
def user_edit(user_name):
    if not isinstance(current_user, Administrator):
        flash("Access denied - Administrators only!")
        return redirect(url_for('index'))

    user = User.query.get_or_404(user_name)

    if request.method == 'POST':
        user.password = request.form['password']

        db.session.commit()
        flash('User updated')
        return redirect(url_for('user_manage'))

    return render_template('/manage/user_edit.html', user=user)


# 查看用户借书情况
@app.route('/manage/user_detail/<string:user_name>', methods=['GET'])
@login_required
def user_detail(user_name):
    if not isinstance(current_user, Administrator):
        flash("Access denied - Administrators only!")
        return redirect(url_for('index'))

    records = BorrowRecord.query.filter_by(reader=user_name)
    return render_template('/manage/user_detail.html', records=records)


# 查看所有借书情况
@app.route('/manage/borrow_manage', methods=['POST', 'GET'])
@login_required
def borrow_manage():
    if not isinstance(current_user, Administrator):
        flash("Access denied - Administrators only!")
        return redirect(url_for('index'))
    records = BorrowRecord.query.all()
    return render_template('/manage/borrow_manage.html', records=records)


# 修改管理员个人信息
@app.route('/manage/admin_manage', methods=['POST', 'GET'])
@login_required
def admin_manage():
    if not isinstance(current_user, Administrator):
        flash("Access denied - Administrators only!")
        return redirect(url_for('index'))

    if request.method == 'POST':
        old_password = request.form['old_password']
        new_password = request.form['new_password']
        re_password = request.form['re_password']
        if not old_password or not new_password or not re_password:
            flash('Please enter')
            return redirect(url_for('admin_manage'))

        if old_password != current_user.password:
            flash('Wrong password')
            return redirect(url_for('admin_manage'))

        if new_password != re_password:
            flash('Passwords do not match')
            return redirect(url_for('admin_manage'))
        current_user.password = new_password
        db.session.commit()
        flash('User updated')
        return redirect(url_for('book_manage'))

    return render_template('/manage/admin_manage.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


# 读者端

# 借阅界面， 对于已借阅的书籍做特殊处理
@app.route('/reader/reader_borrow', methods=['POST', 'GET'])
@login_required
def reader_borrow():
    if not isinstance(current_user, User):
        flash("Access denied - User only!")
        return redirect(url_for('index'))
    books = Book.query.filter((Book.available > 0) & (Book.is_available == True)).all()
    records = BorrowRecord.query.filter((BorrowRecord.reader == current_user.name) & (BorrowRecord.return_status == "未归还")).all()
    borrowed_book_ids = [record.id for record in records]

    return render_template('/reader/reader_borrow.html', books=books, borrowed_book_ids=borrowed_book_ids)


# 搜索要借阅的书籍
@app.route('/reader/reader_search', methods=['POST', 'GET'])
@login_required
def reader_search():
    if not isinstance(current_user, User):
        flash("Access denied - User only!")
        return redirect(url_for('index'))

    book_id = request.form['id']
    book = Book.query.filter((Book.id == book_id) & (Book.is_available == True)).first()
    if book is None:
        flash('Book does not exist')
        return redirect(url_for('reader_borrow'))

    return render_template('/reader/reader_search.html')


# 借阅书籍
@app.route('/reader/is_borrow/<string:book_id>', methods=['POST', 'GET'])
@login_required
def is_borrow(book_id):
    if not isinstance(current_user, User):
        flash("Access denied - User only!")
        return redirect(url_for('index'))

    book = Book.query.get_or_404(book_id)

    if request.method == 'POST':
        records = BorrowRecord.query.filter((BorrowRecord.reader == current_user.name) & (BorrowRecord.return_status == "未归还")).all()
        borrowed_book_ids = [record.id for record in records]

        if book_id in borrowed_book_ids:
            flash('Book already borrowed')
            return redirect(url_for('reader_borrow'))

        borrow_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        record = BorrowRecord(id=book.id, reader=current_user.name, borrow_time=borrow_time, return_status="未归还")
        db.session.add(record)
        db.session.commit()

        book.available -= 1
        db.session.commit()
        flash('Book borrowed')
        return redirect(url_for('reader_borrow'))

    return render_template('/reader/is_borrow.html')


# 个人借阅信息
@app.route('/reader/reader_detail', methods=['POST', 'GET'])
@login_required
def reader_detail():
    if not isinstance(current_user, User):
        flash("Access denied - User only!")
        return redirect(url_for('index'))

    records = BorrowRecord.query.filter((BorrowRecord.reader == current_user.name) & (BorrowRecord.return_status == "未归还")).all()
    return render_template('/reader/reader_detail.html', records=records)


# 归还书籍
@app.route('/reader/is_return/<string:record_id>', methods=['POST', 'GET'])
@login_required
def is_return(record_id):
    if not isinstance(current_user, User):
        flash("Access denied - User only!")
        return redirect(url_for('index'))

    record = BorrowRecord.query.filter_by(id=record_id, reader=current_user.name).first_or_404()
    book = Book.query.get_or_404(record.id)

    if request.method == 'POST':
        record.return_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        record.return_status = "已归还"
        book.available += 1
        db.session.commit()
        flash('Book returned')
        return redirect(url_for('reader_detail'))

    return render_template('/reader/is_return.html')


# 用户个人信息修改
@app.route('/reader/reader_info', methods=['POST', 'GET'])
@login_required
def reader_info():
    if not isinstance(current_user, User):
        flash("Access denied - User only!")
        return redirect(url_for('index'))

    if request.method == 'POST':
        old_password = request.form['old_password']
        new_password = request.form['new_password']
        re_password = request.form['re_password']
        if not old_password or not new_password or not re_password:
            flash('Please enter')
            return redirect(url_for('reader_info'))

        if old_password != current_user.password:
            flash('Wrong password')
            return redirect(url_for('reader_info'))

        if new_password != re_password:
            flash('Passwords do not match')
            return redirect(url_for('reader_info'))
        current_user.password = new_password
        db.session.commit()
        flash('User updated')
        return redirect(url_for('reader_borrow'))

    return render_template('/reader/reader_info.html')
