import sqlite3

# 连接到数据库
db = sqlite3.connect('book.db')

try:
    # 检查是否存在唯一索引
    cursor = db.cursor()
    cursor.execute("PRAGMA index_list(reviews)")
    indexes = cursor.fetchall()
    for index in indexes:
        if 'unique' in index and index['unique'] == 1:
            index_name = index['name']
            cursor.execute(f"DROP INDEX {index_name}")

    # 插入新记录
    cursor.execute("INSERT INTO reviews (name, rating, review_text, book_id) VALUES (?, ?, ?, ?)",
                   (name, rating, review_text, book['book_id']))
    db.commit()
except sqlite3.IntegrityError as e:
    app.logger.error(f"Database error: {e}")
    db.rollback()
    return "内部服务器错误", 500
finally:
    cursor.close()