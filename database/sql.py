import sqlite3
from sqlite3 import Error

def connection(): # создание соединения с базой данных
    try:
        connect = sqlite3.connect("workouts.db")
    except Error:
        print(Error)
    return connect

def select(con,request,beautiful_select = False): # запрос на вывод строк через запрос select в виде массива строк
    # request принимает на вход sql-запрос select
    cursor = con.cursor()
    cursor.execute(request)
    rows = cursor.fetchall()
    if beautiful_select:
        names = []
        for description in cursor.description:
            names.append(description[0])
        rows.insert(0, names)
        col = []
        s = len((rows[0]))
        for i in range(s):
            column = []
            for j in range(len(rows)):
                column.append(len(str(rows[j][i])))
            col.append(max(column) + 2)
        unite = sum(col)
        string = ''
        for i in col:
            string+='{:<'+str(i)+'}'
        print(string.format(*rows[0]))
        print('-'*unite,end='')
        print()
        rows.pop(0)
        for row in rows:
            safe_row = [str(val) if val is not None else "None" for val in row]
            print(string.format(*safe_row))
    return rows

def delete(con,table,additional_condition=''): # удаление строк таблицы
    # additional_condition - переменная для дополнительного условия, вроде where
    cursor = con.cursor()
    cursor.execute(f"delete from {table}\n"+additional_condition)
    con.commit()

def update(con, table, column, value, additional_condition=''): # обновление строк в таблице
    # colum - столбец для редактирования
    # value - значение, на которые будут заменены ячейки
    # additional_condition - переменная для дополнительного условия, вроде where
    cursor = con.cursor()
    cursor.execute(f"update {table} set {column} = {value}\n" + additional_condition)
    con.commit()

con = connection()
