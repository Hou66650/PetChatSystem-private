from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

app = Flask(__name__)
#mysql所在的主机名
HOSTNAME = 'localhost'
#连接sql的用户名
USERNAME = 'root'
#连接mysql的密码
PASSWORD = 'root'
#mysql的数据库名称
DATABASE = 'database_learn'
app.config['SQLALCHEMY_DATABASE_URI'] = f'mysql+pymysql://{USERNAME}:{PASSWORD}@{HOSTNAME}/{DATABASE}?charset=utf8'
# 在app.config中设置好连接数据库的一些信息
# 使用SQLAlchemy创建一个db对象
# SQLAlchemy会读取app.config中的信息
db = SQLAlchemy(app)
migrate = Migrate(app, db)
# 映射三部曲
# flask db init只需要做一次



# #测试是否连接成功
# with app.app_context():
#     with db.engine.connect() as conn:
#         rs = conn.execute('select 1')
#         print(rs.fetchone()) #(1,)


# 创建ORM（对象（也就是类）关系映射）
# 其优点是sql语句写得少，且安全性较强，效率很高，灵活性也强

# 创建ORMmx
# ORM每个属性对应table中每个字段

class User(db.Model):
    __tablename__ = 'user'
    #添加字段
    id = db.Column(db.Integer, primary_key=True)  # db.Integer是数据类型
    username = db.Column(db.String(100), unique=True, nullable=False)  # db.string(max_len)->varchar,nullable,是否为空
    password = db.Column(db.String(100), nullable=False)


class Article(db.Model):
    __tablename__ = 'article'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    # 添加作者外键
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    # backref会自动给User模型添加一个articles的属性，用来获取文章列表
    author = db.relationship('User', backref=db.backref('articles', lazy=True))
    #


# user = User.query.get(article.author_id)


# 映射到数据库中.此方法基本不会用
with app.app_context():
    db.create_all()


@app.route('/user/add')
def user_add():
    #创建ORM对象
    user1 = User(username='zhangsan', password='123123')
    user2 = User(username='Lisi', password='123sa123')
    # 将ORM对象添加到db.session中
    db.session.add_all([user1, user2])
    # 将db.session同步到数据库中
    db.session.commit()
    return 'ok'


@app.route('/user/query')
def user_query():
    # get查找，根据主键查找
    User.query.get(1)
    print(f'{User.query.all()}')
    # Queryset:类数组
    users = User.query.filter(User.username == 'zhangsan')
    for user in users:
        print(f'{user.id}, {user.username}, {user.password}')
    return 'ok_pp'


@app.route('/user/update')
def user_update():
    user1 = User.query.filter_by(username='zhangsan')
    user1.password = '72837'
    db.session.commit()
    return 'your update finish'


@app.route('/user/delete')
def user_delete():
    user1 = User.query.get(1)
    db.session.delete(user1)
    db.session.commit()
    return 'your delete finish'


@app.route('/article/add')
def article_add():
    article1 = Article(title='dahsja', content='asdlkajkdsjas')
    article1.author = User.query.get(2)
    article2 = Article(title='hsja', content='asdlas22kajkdsjas')
    article2.author = User.query.get(2)
    db.session.add_all([article1, article2])
    db.session.commit()
    return 'ok'


@app.route('/article/query')
def article_query():
    user = User.query.get(2)
    for article in user.articles:
        print(article.title, article.content)
    return 'oky'


if __name__ == '__main__':
    app.run(debug=True)
