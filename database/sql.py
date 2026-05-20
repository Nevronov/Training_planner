import sqlite3
from sqlite3 import Error

def connection(): # создание соединения с базой данных
    try:
        connect = sqlite3.connect("../database/workouts.db")
    except Error:
        print(Error)
    return connect

def insert(con, table, values): # запрос на создание строки для таблицы
    # table - название таблицы в любом регистре
    # values - массив данных для записи строки
    # пример ввода значения Null insert(con, 'workouts', [1,1,1,(None)])
    a = con.cursor()
    table = table.lower()
    if table == 'users':
        a.execute("INSERT INTO users(u_name, u_login, u_password) VALUES (?,?,?)",values)
    elif table == 'workouts':
        a.execute("INSERT INTO Workouts(w_user, w_name, w_description, w_date_time) VALUES (?,?,?,?)", values)
    elif table == 'muscle_groups':
        a.execute("INSERT INTO Muscle_groups(m_name) VALUES (?)", values)
    elif table == 'exercises':
        a.execute("INSERT INTO Exercises(e_name, e_muscle, e_description, e_user) VALUES (?,?,?,?)", values)
    elif table == 'exercises_list':
        a.execute("INSERT INTO Exercises_list(el_workout, el_exercises, el_number_of_sets, el_weight) VALUES (?,?,?,?)", values)
    elif table == 'weight_logs':
        a.execute("INSERT INTO Weight_logs(wl_user, wl_weight, wl_date) VALUES (?,?,?)", values)
    con.commit()

def select(con, request,beautiful_select = False): # запрос на вывод строк через запрос select в виде массива строк
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

def delete(con, table,additional_condition=''): # удаление строк таблицы
    # additional_condition - переменная для дополнительного условия, вроде where
    cursor = con.cursor()
    cursor.execute(f"delete from {table}\n"+additional_condition)
    con.commit()

def update(con, table, column, value, additional_condition=''): # обновление строк в таблице
    # colum - столбец для редактирования
    # value - значение, на которые будут заменены ячейки
    # additional_condition - переменная для дополнительного условия, вроде where
    cursor = con.cursor()
    print(f"update {table} set {column} = '{value}'\n" + additional_condition)
    cursor.execute(f"update {table} set {column} = '{value}'\n" + additional_condition)
    con.commit()

def delete_all_db(con):
    cursor = con.cursor()
    cursor.executescript(f"""DELETE FROM Exercises_list;
                             DELETE FROM Workouts;
                             DELETE FROM Exercises;
                             DELETE FROM Users;
                             DELETE FROM Muscle_groups;
                             DELETE FROM sqlite_sequence;""")
    con.commit()
    print('Отчистка произведена')

delete_all_db(connection())
print(select(connection(),'select * from users'))