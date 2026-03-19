create table Users
(
  u_id integer primary key AUTOINCREMENT,
  u_name varchar(25) not null,
  u_login varchar(25) unique not null,
  u_password varchar(20) not null
);

create table Workouts
(
  w_id integer primary key autoincrement,
  w_user integer references users(u_id) not null,
  w_time time not null,
  w_description text,
  w_date date not null
);

create table Muscle_groups
(
  m_id integer primary key autoincrement,
  m_name varchar(25) unique not null
);

create table Exercises
(
  e_id integer primary key autoincrement,
  e_name varchar(50) not null,
  e_muscle integer references Muscle_group(m_id) not null,
  e_description text
);

create table Exercises_list
(
  el_id integer primary key autoincrement,
  el_workout integer references workouts(w_id) not null,
  el_exercises integer references Exercises(e_id) not null,
  el_number_of_sets integer not null
);
