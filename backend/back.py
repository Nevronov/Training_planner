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
class UserNotLoggedIn(Exception):
    pass
def get_cookie_user(user_id: str = Cookie(None)):
    if user_id == None:
        raise UserNotLoggedIn()
    return int(user_id)
@app.exception_handler(UserNotLoggedIn)
async def auth_exception_handler(request: Request, exc: UserNotLoggedIn):
    return RedirectResponse(url="/login", status_code=303)

@app.get("/logout")
def logout():
    response = RedirectResponse(url="/login", status_code=303)
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
        ver_pas = not verify_password(check_input.u_password, u_data[0][0])
        if ver_pas: raise IndexError
    except IndexError:
        return templates.TemplateResponse(request=request, name="login.html",
                                          context={"message": "Неверный логин или пароль"})
    else:
        response = RedirectResponse(url='/', status_code=303)
        response.set_cookie(key="user_id", value=u_data[0][1], httponly=True)
        return response

### ХЕШИРОВАНИЕ ПАРОЛЯ

def hash_password(password: str):
    sha256_hash = hashlib.sha256(password.encode('utf-8')).hexdigest()

    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(sha256_hash.encode('utf-8'), salt)

    return hashed.decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    sha256_hash = hashlib.sha256(plain_password.encode('utf-8')).hexdigest()

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
        hash_pass = hash_password(register.u_password)
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
            if verify_password(passwords.old_password,user_db[0][0]):
                hash_pass = hash_password(passwords.new_password)
                sql.update(con,'Users','u_password',f"{hash_pass}",f"WHERE u_id = {current_user}")
                status = 'password'
            else:
                status = 'unpassword'
    except ValidationError as e:
        error_detail = e.errors()[0]
        error_field = error_detail['loc'][0]
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

### Шаблоны

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
    return templates.TemplateResponse(request=request, name="templates.html", context={"templates": templates_list})

@app.get("/templates/edit", response_class=HTMLResponse)
async def get_templates_edit_page(request: Request, current_user=Depends(get_cookie_user),
                                  workout_id: Optional[str] = None):
    con = sql.connection()

    all_exercises_raw = sql.select(con, f"""
        SELECT e.e_id, e.e_name, e.e_description, GROUP_CONCAT(mg.m_name, ', ')
        FROM Exercises e
        LEFT JOIN Muscles_list ml ON e.e_id = ml.ml_exercises
        LEFT JOIN Muscle_groups mg ON ml.ml_muscle = mg.m_id
        WHERE e.e_user = 1 OR e.e_user = {current_user}
        GROUP BY e.e_id, e.e_name, e.e_description
    """)

    all_exercises = []
    for row in all_exercises_raw:
        all_exercises.append({
            "id": row[0],
            "name": row[1],
            "description": row[2],
            "muscle": row[3] if row[3] else "Не указано",
            "default_sets": 3,
            "default_weight": 0
        })

    exercises_list = None
    w_name = None
    w_description = None
    w_edit = "Создать"

    if workout_id is not None:
        try:
            workout = sql.select(con, f"SELECT w_name, w_description, w_user FROM Workouts WHERE w_id = {workout_id}")
            if not workout:
                raise Exception()

            user = workout[0][2]
            if user != current_user:
                raise Exception()
        except:
            con.close()
            return RedirectResponse(url=f"/", status_code=303)

        w_name = workout[0][0]
        w_description = workout[0][1]
        w_edit = "Изменить"

        exercises = sql.select(con, f"""
            SELECT e.e_id, e.e_name, el.el_number_of_sets, el.el_weight, GROUP_CONCAT(mg.m_name, ', ') 
            FROM Exercises_list el
            JOIN Exercises e ON el.el_exercises = e.e_id
            LEFT JOIN Muscles_list ml ON e.e_id = ml.ml_exercises
            LEFT JOIN Muscle_groups mg ON ml.ml_muscle = mg.m_id
            WHERE el.el_workout = {workout_id}
            GROUP BY el.el_id, e.e_id, e.e_name, el.el_number_of_sets, el.el_weight
        """)

        exercises_list = []
        for row in exercises:
            exercises_list.append({
                "id": row[0],
                "name": row[1],
                "sets": row[2],
                "weight": row[3],
                "muscle": row[4] if row[4] else "Не указано"
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
    sets_count: list[str] = Form([]),
    weight: list[str] = Form([])):
    con = sql.connection()
    if workout_id:
        sql.update(con,'Workouts','w_name', w_name,
                   f", w_description = '{w_description}' WHERE w_id = {workout_id}")
        sql.delete(con, 'Exercises_list',f"WHERE el_workout = {workout_id}")
        for i, e_id in enumerate(exercise_ids):
            current_sets = int(sets_count[i]) if sets_count[i] != "" else 1
            current_weight = float(weight[i]) if weight[i] != "" else None
            sql.insert(con, 'Exercises_list', [workout_id, e_id, current_sets, current_weight])
    else:
        sql.insert(con, 'Workouts',[current_user, w_name, w_description])
        w_id = sql.select(con,'select w_id from Workouts order by w_id desc limit 1')[0][0]
        for i, e_id in enumerate(exercise_ids):
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
            print(f"ОШИБКА: Доступ запрещен! Шаблон принадлежит пользователю {user}, а пытается удалить {current_user}")
            con.close()
            raise
    except Exception as e:
        con.close()
        return RedirectResponse(url=f"/", status_code=303)
    sql.delete(con, 'Exercises_list', f"where el_workout = {template_id}")
    sql.delete(con, 'Workouts', f"where w_id = {template_id}")
    con.close()
    return RedirectResponse(url=f"/templates", status_code=303)

### Упражнения

@app.get("/exercises", response_class=HTMLResponse)
async def get_exercises_page(request: Request, current_user=Depends(get_cookie_user)):
    con = sql.connection()

    exercises = sql.select(con,
                           f"SELECT e_id, e_name, e_user FROM Exercises WHERE e_user = {current_user} OR e_user = 1"
                           )

    exercises_list = []

    for row in exercises:
        e_id, e_name, e_user = row[0], row[1], row[2]

        muscle_rows = sql.select(con, f"""
            SELECT m_name 
            FROM Muscle_groups
            JOIN Muscles_list ON Muscle_groups.m_id = Muscles_list.ml_muscle
            WHERE ml_exercises = {e_id}
        """)

        muscle_names = [m[0] for m in muscle_rows]

        exercises_list.append({
            "id": e_id,
            "name": e_name,
            "muscles": muscle_names,
            "u_id": e_user
        })

    con.close()
    return templates.TemplateResponse(request=request, name="exercises.html", context={"exercises": exercises_list})

@app.get("/exercises/edit", response_class=HTMLResponse)
async def get_exercises_edit(request: Request, current_user=Depends(get_cookie_user),
                             exercise_id: Optional[str] = None):
    con = sql.connection()

    workouts_list = []
    e_name = e_description = e_user = muscle_ids_str = None
    e_edit = "Создать"

    if exercise_id is not None:
        data = sql.select(con,
                          f"SELECT e_name, e_description, e_user FROM Exercises WHERE e_id = {exercise_id}")
        if not data:
            con.close()
            return RedirectResponse(url="/", status_code=303)

        row = data[0]

        if current_user != 1 and row[2] != current_user and row[2] != 1:
            con.close()
            return RedirectResponse(url="/", status_code=303)

        e_name, e_description, e_user = row
        e_edit = "Изменить"

        workouts = sql.select(con, f"""SELECT w_id, w_name FROM Exercises_list
                                    JOIN Workouts ON Exercises_list.el_workout = Workouts.w_id
                                    WHERE el_exercises = {exercise_id} AND w_user = {current_user}""")
        workouts_list = [{"id": r[0], "name": r[1]} for r in workouts]
        muscle_list = sql.select(con, f"SELECT ml_muscle FROM Muscles_list where ml_exercises = {exercise_id}")
        muscle_ids_str = ",".join([str(m[0]) for m in muscle_list]) if muscle_list else ""

    muscle_groups = sql.select(con, "SELECT m_id, m_name FROM Muscle_groups")
    all_muscle_groups = [{"id": r[0], "name": r[1]} for r in muscle_groups]

    con.close()

    return templates.TemplateResponse(request=request, name="edit_exercises.html", context={
        'e_id': exercise_id,
        'e_edit': e_edit,
        'e_name': e_name,
        'e_description': e_description,
        'e_muscle': muscle_ids_str,
        'e_user': e_user,
        'user_id': current_user,
        "related_workouts": workouts_list,
        "all_muscle_groups": all_muscle_groups
    })

@app.post("/exercises/edit", response_class=HTMLResponse)
async def edit_exercises(request: Request,
    e_name: str = Form(min_length=3, max_length=30),
    e_description: Optional[str] = Form(None),
    exercises_id: Optional[int] = Form(None),
    e_muscle: Optional[str] = Form(None),
    current_user = Depends(get_cookie_user)):
    con = sql.connection()
    if exercises_id:
        sql.update(con, 'Exercises', 'e_name', e_name,
                   f", e_description = '{e_description}', e_muscle = 0 WHERE e_id = {exercises_id}")

        target_exercise_id = exercises_id

        sql.delete(con, f"DELETE FROM Muscles_list WHERE _exercises = {target_exercise_id}")
    else:
        sql.insert(con, 'Exercises', [e_name, e_description, current_user])

        target_exercise_id = sql.select(con, 'select e_id from Exercises order by e_id DESC limit 1')[0][0]

    print(e_muscle, target_exercise_id)
    if e_muscle and target_exercise_id:
        muscle_ids = [int(m_id) for m_id in e_muscle.split(',') if m_id.strip()]
        print(muscle_ids)

        for m_id in muscle_ids:
            sql.insert(con, 'Muscles_list', [m_id, target_exercise_id])

    con.close()
    return RedirectResponse(url=f"/exercises", status_code=303)

### Календарь

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
    sql.insert(con, 'conducting_workouts', [template_id, date, False])
    con.close()
    return RedirectResponse(url=f"/calendar", status_code=303)


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)