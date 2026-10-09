-- 宠物聊天系统数据库 schema（幂等：只建缺失的表，不删除任何数据）
-- 用法：python run.py --init-db
-- 与线上 book.db 的实际表结构保持一致（含历史遗留的 books/borrows/histroys）。

create table if not exists users (
        user_id integer primary key autoincrement,
        user_name text not null,
        pwd text not null,
        college text,
        num text,
        email text
);

create table if not exists manager_info (
  "id" INTEGER,
  "manager_id" INTEGER NOT NULL,
  "password" TEXT NOT NULL,
  PRIMARY KEY ("id")
);

create table if not exists books (
  "book_id" text,
  "book_name" text NOT NULL,
  "author" text NOT NULL,
  "publish_com" text NOT NULL,
  "publish_date" text NOT NULL,
  "data" text,
  "summary" text,
  "author_jj" TEXT,
  PRIMARY KEY ("book_id")
);

create table if not exists borrows (
       user_name text not null,
       book_id text not null,
       date_borrow text not null,
       date_return text not null,
       primary key (user_name, book_id)
);

create table if not exists histroys (
       histroy_id integer primary key autoincrement,
       book_id text not null,
       user_name text not null,
       date_borrow text not null,
       date_return text,
       status text not null default 'not return'
);

-- 宠物/图书评价（宠物评分通过 book_id='petN' 关联，见 app/routes/chat.py）
create table if not exists reviews (
  "id" INTEGER PRIMARY KEY AUTOINCREMENT,
  "book_id" text NOT NULL,
  "name" text NOT NULL,
  "rating" integer,
  "review_text" text
);
