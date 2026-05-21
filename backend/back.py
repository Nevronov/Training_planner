from http.client import responses
from typing import Optional

from fastapi import FastAPI, Request, Form, Depends, Cookie, Query
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field, ValidationError
import uvicorn
from database import sql
import datetime

import hashlib
import bcrypt

app = FastAPI()

templates = Jinja2Templates(directory='../frontend')
# Исключение для проверки авторизации пользователя
class UserNotLoggedIn(Exception):
    pass
# Проверка авторизации пользователя
def get_cookie_user(user_id: str = Cookie(None)):
    if user_id == None:
        raise UserNotLoggedIn()
    return int(user_id)
# Результат выполнения, в случае захода не авторизированным
@app.exception_handler(UserNotLoggedIn)
async def auth_exception_handler(request: Request, exc: UserNotLoggedIn):
    return RedirectResponse(url="/login", status_code=303)

# Выход из аккаунта
@app.get("/logout")
def logout():
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("user_login") # Удаляем «пропуск» из браузера
    return response

### УПРАВЛЕНИЕ СТРАНИЦЕЙ LOGIN

@app.get("/login", response_class=HTMLResponse)
async def get_login_page(request: Request):
    return templates.TemplateResponse(request=request, name="login.html")

class LoginInput(BaseModel):
    u_login: str
    u_password: str

def login_form(u_login: str = Form(), u_password: str = Form()):
    return LoginInput(u_login=u_login, u_password=u_password)

@app.post("/login", response_class=HTMLResponse)
async def check_password(request: Request, check_input: LoginInput = Depends(login_form)):
    con = sql.connection()
    u_data = sql.select(con,f"""SELECT u_password, u_id FROM Users
                  WHERE u_login = '{check_input.u_login}'""")
    con.close()
    try:
        print(u_data)
        ver_pas = not verify_password(check_input.u_password, u_data[0][0])
        if ver_pas: raise IndexError
    except IndexError:
        return templates.TemplateResponse(request=request, name="login.html",
                                          context={"message": "Неверный логин или пароль"})
    else:
        # Переход на главную страницу и внесение куки
        response = RedirectResponse(url='/', status_code=303)
        response.set_cookie(key="user_id", value=u_data[0][1], httponly=True)
        return response

### ХЕШИРОВАНИЕ ПАРОЛЯ

def hash_password(password: str):
    # 1. Хэшируем в SHA-256 (выдает 64 символа)
    sha256_hash = hashlib.sha256(password.encode('utf-8')).hexdigest()

    # 2. Генерируем соль и хэшируем через чистый bcrypt
    # переводя строку SHA-256 в байты перед этим
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(sha256_hash.encode('utf-8'), salt)

    # Возвращаем строкой для сохранения в БД
    return hashed.decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    # 1. Повторяем SHA-256 для проверяемого пароля
    sha256_hash = hashlib.sha256(plain_password.encode('utf-8')).hexdigest()

    # 2. Проверяем соответствие через bcrypt
    # Обязательно кодируем обе строки в байты для библиотеки
    return bcrypt.checkpw(sha256_hash.encode('utf-8'), hashed_password.encode('utf-8'))

### УПРАВЛЕНИЕ СТРАНИЦЕЙ РЕГИСТРАЦИЯ

@app.get("/register", response_class=HTMLResponse)
async def get_register_page(request: Request):
    return templates.TemplateResponse(request=request, name="register.html")

class RegisterInput(BaseModel):
    u_name: str = Field(max_length=25)
    u_weight: Optional[float] = None
    u_login: str = Field(min_length=3, max_length=25)
    u_password: str = Field(min_length=3, max_length=25)
    u_confirm_password: str = Field(min_length=3, max_length=25)

@app.post("/register", response_class=HTMLResponse)
async def registration(request: Request):
    label_color = '#ff4d4d'
    con = None
    form_data = dict(await request.form())
    if form_data.get("u_weight") == "":
        form_data["u_weight"] = None
    try:
        register = RegisterInput(**form_data)
        if register.u_confirm_password != register.u_password:
            return templates.TemplateResponse(request=request, name="register.html", context={
                "message": "Пароли не совпадают", "u_name": register.u_name, "u_weight": register.u_weight,
                "u_login": register.u_login, "label_color": label_color})
        con = sql.connection()
        logins = sql.select(con, f"SELECT * FROM Users where u_login = '{register.u_login}'")
        if len(logins) > 0:
            con.close()
            return templates.TemplateResponse(request=request, name="register.html", context={
                "message": "Логин занят", "u_name": register.u_name, "u_weight": register.u_weight,
                "u_login": register.u_login, "label_color": label_color})
        print(register.u_password)
        hash_pass = hash_password(register.u_password)
        print(hash_pass)
        sql.insert(con, 'users', [register.u_name, register.u_login, hash_pass])
        id = sql.select(con,'select u_id from Users order by u_id desc limit 1')[0][0]
        if register.u_weight != None:
            sql.insert(con,'weight_logs',[id, register.u_weight, datetime.datetime.now().strftime('%Y-%m-%d')])
        con.close()
        label_color = '#7fc7ff'
        return templates.TemplateResponse(request=request, name="register.html", context={
            "message": "Регистрация прошла успешно", "u_name": register.u_name, "u_weight": register.u_weight,
            "u_login": register.u_login, "label_color": label_color})
    except ValidationError as e:
        if con:
            con.close()
        error_detail = e.errors()[0]
        error_field = error_detail['loc'][0]
        if error_field == 'u_name':
            message = "Имя пользователя не должно превышать 25 символов."
        elif error_field == 'u_login':
            message = "Логин должен быть от 3 до 25 символов."
        elif error_field == 'u_password':
            message = "Пароль должен быть от 3 до 25 символов."
        elif error_field == 'u_confirm_password':
            message = "Подтверждение пароля должно быть от 3 до 25 символов."
        elif error_field == 'u_weight':
            message = "Некорректный формат веса. Введите число (например: 75.5)."
        else:
            message = "Проверьте правильность заполнения полей."
        u_name = form_data.get("u_name", "")
        u_login = form_data.get("u_login", "")
        u_weight = form_data.get("u_weight", "")
        return templates.TemplateResponse(request=request, name="register.html", context={
            "message": message, "u_name": u_name,
            "u_login": u_login, "u_weight": u_weight, "label_color": label_color})

### Главная страница

@app.get("/", response_class=HTMLResponse)
async def get_register_page(request: Request):
    return templates.TemplateResponse(request=request, name="main.html")

### Профиль

def data_profile(current_user):
    con = sql.connection()
    u_data = sql.select(con, f"""sELECT u_name, COUNT(w_id),
                                    MAX(wc_date) FROM Users
                                    LEFT JOIN Workouts ON Users.u_id = Workouts.w_user
                                    LEFT JOIN Conducting_Workouts ON Conducting_Workouts.wc_workout = Workouts.w_id
                                    WHERE u_id = {current_user}
                                    GROUP BY u_id, u_name""")
    w_data = sql.select(con, f"""select wl_weight, wl_date from Weight_logs
                                             where wl_user = {current_user}
                                             order by wl_date desc 
                                             limit 20""")
    w_data_reversed = w_data[::-1]
    weight_dates = [row[1] for row in w_data_reversed]
    weight_values = [row[0] for row in w_data_reversed]
    con.close()
    date = None
    print(current_user)
    print(u_data)
    try:
        date = u_data[0][2][:10]
    except:
        pass
    return u_data[0][0], u_data[0][1], date, weight_dates, weight_values

@app.get("/profile", response_class=HTMLResponse)
async def get_profile_page(request: Request, current_user = Depends(get_cookie_user), ms_status: Optional[str] = None):
    message = ''
    label_color = "#7fc7ff"
    if ms_status == "weight":
        message = "Добавлен новый вес"
    elif ms_status == "password":
        message = "Пароль изменён"
    elif ms_status == "unpassword":
        message = "Неверный пароль"
        label_color = '#ff4d4d'
    print(message)
    data = data_profile(current_user)
    return templates.TemplateResponse(request=request, name="profile.html",
                                      context={"message": message,'u_name': data[0], 'total_workouts': data[1], 'last_workout_date': data[2],
                                               "weight_dates": data[3], "weight_values": data[4], 'label_color': label_color})
class PasUpdate(BaseModel):
    old_password: Optional[str] = None
    new_weight: Optional[float] = Field(default=None, ge=20.0, le=300.0)
    new_password: Optional[str] = Field(default=None, min_length=3, max_length=25)

@app.post("/profile", response_class=HTMLResponse)
async def update_password(request: Request, current_user = Depends(get_cookie_user)):
    con = sql.connection()
    message = ''
    status = 'success'
    user_db = sql.select(con, f"SELECT u_password, u_name FROM Users WHERE u_id = {current_user}")
    try:
        form_data = dict(await request.form())
        form_data = {k: (v if v.strip() != "" else None) for k, v in form_data.items()}
        passwords = PasUpdate(**form_data)
        if passwords.new_weight is not None:
            sql.insert(con, 'weight_logs', [current_user, passwords.new_weight, datetime.datetime.now().strftime('%Y-%m-%d')])
            status = 'weight'
        elif passwords.old_password is not None or passwords.new_password is not None:
            print(verify_password(passwords.old_password,user_db[0][0]))
            if verify_password(passwords.old_password,user_db[0][0]):
                hash_pass = hash_password(passwords.new_password)
                sql.update(con,'Users','u_password',f"{hash_pass}",f"WHERE u_id = {current_user}")
                status = 'password'
            else:
                status = 'unpassword'
    except ValidationError as e:
        print(e)
        error_detail = e.errors()[0]
        error_field = error_detail['loc'][0]
        print(e)
        label_color = '#ff4d4d'
        if error_field == 'new_weight':
            message = "Вес должен быть от 20 до 300"
        data = data_profile(current_user)
        return templates.TemplateResponse(request=request, name="profile.html",
                                          context={"message": message, "label_color": label_color, 'u_name': data[0],
                                                   'total_workouts': data[1], 'last_workout_date': data[2],
                                                   "weight_dates": data[3], "weight_values": data[4]})
    finally:
        if con:
            con.close()
    return RedirectResponse(url=f"/profile?ms_status={status}", status_code=303)

### Список шаблонов

@app.get("/templates", response_class=HTMLResponse)
async def get_templates_page(request: Request, current_user = Depends(get_cookie_user)):
    con = sql.connection()
    workouts = sql.select(con, f'SELECT w_id, w_name FROM Workouts WHERE w_user = {current_user}')
    con.close()
    templates_list = []
    for row in workouts:
        templates_list.append({
            "id": row[0],
            "name": row[1]
        })
    print(templates_list)
    return templates.TemplateResponse(request=request, name="templates.html", context={"templates": templates_list})

### Создание/редактирование шаблонов

@app.get("/templates/edit", response_class=HTMLResponse)
async def get_templates_edit_page(request: Request, current_user=Depends(get_cookie_user),
                                  workout_id: Optional[str] = None):
    con = sql.connection()
    all_exercises_raw = sql.select(con, f"""SELECT e_id, e_name, m_name, e_description FROM Exercises 
                                           JOIN Muscle_groups ON Exercises.e_muscle = Muscle_groups.m_id
                                           WHERE e_user = 1 or e_user = {current_user}""")
    all_exercises = []
    for row in all_exercises_raw:
        all_exercises.append({
            "id": row[0],
            "name": row[1],
            "muscle": row[2],
            "description": row[3],
            "default_sets": 3,  # Можно поставить жесткий дефолт или взять из базы: row[3]
            "default_weight": 0  # Можно поставить жесткий дефолт или взять из базы: row[4]
        })

    exercises_list = None
    w_name = None
    w_description = None
    w_edit = "Создать"

    if workout_id is not None:
        exercises = sql.select(con, f"""SELECT e_id, e_name, m_name, el_number_of_sets, el_weight FROM Exercises_list
                                    JOIN Exercises ON Exercises_list.el_exercises = Exercises.e_id
                                    JOIN Muscle_groups ON Exercises.e_muscle = Muscle_groups.m_id
                                    WHERE el_workout = {workout_id}""")
        try:
            workout = sql.select(con,
                                 f"""SELECT w_name, w_description, w_user FROM Workouts WHERE w_id = {workout_id}""")
            user = workout[0][2]
            if user != current_user:
                raise
        except:
            con.close()
            return RedirectResponse(url=f"/", status_code=303)
        if workout:
            w_name = workout[0][0]
            w_description = workout[0][1]
            w_edit = "Изменить"
        exercises_list = []
        for row in exercises:
            exercises_list.append({
                "id": row[0],
                "name": row[1],
                "muscle": row[2],
                "sets": row[3],
                "weight": row[4]
            })

    con.close()
    return templates.TemplateResponse(request=request, name="edit_templates.html", context={
        'w_name': w_name,
        'w_edit': w_edit,
        'w_description': w_description,
        'template': workout_id,
        "exercises": exercises_list,
        "all_exercises": all_exercises
    })

@app.post("/templates/edit", response_class=HTMLResponse)
async def edit_template(request: Request,
    w_name: str = Form(min_length=3, max_length=30),
    w_description: Optional[str] = Form(None),
    workout_id: Optional[int] = Form(None),
    exercise_ids: list[int] = Form([]),
    current_user = Depends(get_cookie_user),
    sets_count: list[str] = Form([]),            # Принимаем как строки, чтобы избежать 422 ошибки при пустом инпуте
    weight: list[str] = Form([])):
    con = sql.connection()
    print(workout_id)
    if workout_id:
        sql.update(con,'Workouts','w_name', w_name,
                   f", w_description = '{w_description}' WHERE w_id = {workout_id}")
        sql.delete(con, 'Exercises_list',f"WHERE el_workout = {workout_id}")
        for i, e_id in enumerate(exercise_ids):
            # Берем из списков элементы, которые стоят на той же позиции (i), что и текущее упражнение
            current_sets = int(sets_count[i]) if sets_count[i] != "" else 1
            current_weight = float(weight[i]) if weight[i] != "" else None
            sql.insert(con, 'Exercises_list', [workout_id, e_id, current_sets, current_weight])
    else:
        sql.insert(con, 'Workouts',[current_user, w_name, w_description])
        w_id = sql.select(con,'select w_id from Workouts order by w_id desc limit 1')[0][0]
        for i, e_id in enumerate(exercise_ids):
            # Берем из списков элементы, которые стоят на той же позиции (i), что и текущее упражнение
            current_sets = int(sets_count[i]) if sets_count[i] != "" else 1
            current_weight = float(weight[i]) if weight[i] != "" else None
            sql.insert(con, 'Exercises_list', [w_id, e_id, current_sets, current_weight])
    con.close()
    return RedirectResponse(url=f"/templates", status_code=303)

@app.post("/templates/delete", response_class=HTMLResponse)
async def delete_template(template_id: Optional[int] = Form(None), current_user = Depends(get_cookie_user)):
    con = sql.connection()
    try:
        if not template_id:
            print("ОШИБКА: Бэкенд получил пустой template_id (None)")
            raise ValueError
        workout = sql.select(con, f"""SELECT w_name, w_description, w_user FROM Workouts WHERE w_id = {template_id}""")

        user = workout[0][2]
        if user != current_user:
            print(f"ОШИБКА: Доступ запрещен! Шаблон принадлежит юзеру {user}, а пытается удалить {current_user}")
            con.close()
            raise
    except Exception as e:
        con.close()
        print(e, template_id)
        return RedirectResponse(url=f"/", status_code=303)
    sql.delete(con, 'Exercises_list', f"where el_workout = {template_id}")
    sql.delete(con, 'Workouts', f"where w_id = {template_id}")
    con.close()
    return RedirectResponse(url=f"/templates", status_code=303)

@app.get("/exercises", response_class=HTMLResponse)
async def delete_template(request: Request, current_user = Depends(get_cookie_user)):
    con = sql.connection()
    exercises = sql.select(con,
                          f'SELECT e_id, e_name, m_name, e_user FROM Exercises '
                          f'join Muscle_groups on Muscle_groups.m_id = Exercises.e_muscle'
                          f' WHERE e_user = {current_user} or e_user = 1')
    con.close()
    exercises_list = []
    for row in exercises:
        exercises_list.append({
            "id": row[0],
            "name": row[1],
            "muscle": row[2],
            "u_id": row[3]
        })
    print(exercises_list)
    return templates.TemplateResponse(request=request, name="exercises.html", context={"exercises": exercises_list})


@app.get("/exercises/edit", response_class=HTMLResponse)
async def get_exercises_edit(request: Request, current_user=Depends(get_cookie_user),
                             exercise_id: Optional[str] = None):
    con = sql.connection()

    # Инициализация переменных
    exercise = None
    workouts_list = []
    e_name = e_description = e_user = e_muscle = None
    e_edit = "Создать"

    if exercise_id is not None:
        # 1. Получаем упражнение (используем параметризацию)
        data = sql.select(con,
                          f"SELECT e_name, e_description, e_muscle, e_user FROM Exercises WHERE e_id = {exercise_id}")
        print(data)
        if not data:
            con.close()
            return RedirectResponse(url="/", status_code=303)

        row = data[0]

        # Проверка прав: если это не админ и не владелец — редирект
        if current_user != 1 and row[3] != current_user and row[3] != 1:
            print(current_user, row[3])
            con.close()
            return RedirectResponse(url="/", status_code=303)

        e_name, e_description, e_muscle, e_user = row
        e_edit = "Изменить"

        # 2. Получаем связанные шаблоны
        workouts = sql.select(con, f"""SELECT w_id, w_name FROM Exercises_list
                                    JOIN Workouts ON Exercises_list.el_workout = Workouts.w_id
                                    WHERE el_exercises = {exercise_id} AND w_user = {current_user}""")
        workouts_list = [{"id": r[0], "name": r[1]} for r in workouts]

    # 3. Группы мышц
    muscle_groups = sql.select(con, "SELECT m_id, m_name FROM Muscle_groups")
    all_muscle_groups = [{"id": r[0], "name": r[1]} for r in muscle_groups]

    con.close()

    return templates.TemplateResponse(request=request, name="edit_exercises.html", context={
        'e_id': exercise_id,
        'e_edit': e_edit,
        'e_name': e_name,
        'e_description': e_description,
        'e_muscle': e_muscle,
        'e_user': e_user,
        'user_id': current_user,
        "related_workouts": workouts_list,
        "all_muscle_groups": all_muscle_groups
    })

@app.post("/exercises/edit", response_class=HTMLResponse)
async def edit_template(request: Request,
    e_name: str = Form(min_length=3, max_length=30),
    e_description: Optional[str] = Form(None),
    exercises_id: Optional[int] = Form(None),
    e_muscle: Optional[int] = Form(None),
    current_user = Depends(get_cookie_user)):
    con = sql.connection()
    print(exercises_id)
    if exercises_id:
        sql.update(con,'Exercises','e_name', e_name,
                   f", e_description = '{e_description}', e_muscle = {e_muscle} WHERE e_id = {exercises_id}")
    else:
        sql.insert(con, 'Exercises',[e_name, e_muscle, e_description, current_user])
    con.close()
    return RedirectResponse(url=f"/exercises", status_code=303)

@app.get("/calendar", response_class=HTMLResponse)
async def get_calendar_page(request: Request, current_user = Depends(get_cookie_user)):
    con = sql.connection()
    workouts = sql.select(con, f"""select w_id, w_name from Workouts where w_user = {current_user}""")
    templ = []
    for tem in workouts:
        templ.append({'id': tem[0], 'name': tem[1]})
    cont_workouts = sql.select(con, f"""select wc_id, wc_date, w_name, w_id, wc_status from Conducting_Workouts
                                                Join Workouts on Workouts.w_id = Conducting_Workouts.wc_workout
                                                WHERE Workouts.w_user = {current_user}""")
    scheduled_workouts = []
    for sch in cont_workouts:
        scheduled_workouts.append({'id': sch[0], 'date': sch[1], 'name': sch[2], 'completed': bool(sch[4]), 'template_id': sch[3]})
    con.close()
    return templates.TemplateResponse(request=request, name="calendar.html", context={'templates': templ, 'scheduled_workouts': scheduled_workouts})

@app.post('/calendar/delete')
async def delete_conducting_workouts(id: int = Form(None), current_user = Depends(get_cookie_user)):
    con = sql.connection()
    sql.delete(con, 'Conducting_Workouts', f'where wc_id = {id}')
    con.close()
    return RedirectResponse(url=f"/calendar", status_code=303)

@app.post('/calendar/toggle')
async def update_conducting_workouts(status: bool = Form(None), id: int = Form(None), current_user = Depends(get_cookie_user)):
    con = sql.connection()
    status = sql.select(con,f'select wc_status from Conducting_Workouts where wc_id = {id}')[0][0]
    if status:
        status = 0
    else:
        status = 1
    sql.update(con, 'Conducting_Workouts', 'wc_status', status,f'where wc_id = {id}')
    con.close()
    return RedirectResponse(url=f"/calendar", status_code=303)

@app.post('/calendar/save')
async def add_conducting_workouts(request: Request, date: str = Form(...),
    template_id: int = Form(...), current_user = Depends(get_cookie_user)):
    con = sql.connection()
    print(template_id, date, False,'\nZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZ')
    sql.insert(con, 'conducting_workouts', [template_id, date, False])
    con.close()
    return RedirectResponse(url=f"/calendar", status_code=303)


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)