create table Users
(
  u_id integer primary key AUTOINCREMENT,
  u_name varchar(25) not null,
  u_login varchar(25) unique not null,
  u_password varchar(20) not null
);

create table Weight_logs
(
  wl_id integer primary key autoincrement,
  wl_user integer references users(u_id) not null,
  wl_weight real not null,
  wl_date text not null
);

create table Workouts
(
  w_id integer primary key autoincrement,
  w_user integer references users(u_id) not null,
  w_name text not null,
  w_description text
);

create table Conducting_Workouts
(
  wc_id integer primary key autoincrement,
  wc_date text,
  wc_workout integer references workouts(w_id) not null,
  wc_status integer default 0
);

create table Muscle_groups
(
  m_id integer primary key autoincrement,
  m_name varchar(25) unique not null
);

create table Muscles_list
(
  ml_id integer primary key autoincrement,
  ml_muscle integer references Muscle_groups(m_id) not null,
  ml_exercises integer references Exercises(e_id) not null
);

create table Exercises
(
  e_id integer primary key autoincrement,
  e_name text not null,
  e_muscle integer references Muscle_groups(m_id) not null,
  e_user integer references users(u_id) not null,
  e_description text
);

create table Exercises_list
(
  el_id integer primary key autoincrement,
  el_workout integer references workouts(w_id) not null,
  el_exercises integer references Exercises(e_id) not null,
  el_number_of_sets integer not null,
  el_weight real
);
