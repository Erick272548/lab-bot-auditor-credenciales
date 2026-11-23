-- Prepara MySQL/MariaDB de XAMPP (puerto 3350) para el laboratorio.
-- Ejecutar:  C:\xampp5001\mysql\bin\mysql.exe -u root -P 3350 -h 127.0.0.1 < bd\setup_mysql.sql
-- La contrasena es la misma credencial FICTICIA que se "filtra" en el commit 2.
CREATE DATABASE IF NOT EXISTS lab_usuarios CHARACTER SET utf8mb4;
CREATE USER IF NOT EXISTS 'lab_app'@'localhost' IDENTIFIED BY 'Pr0y3ct0_T3st_2026!';
CREATE USER IF NOT EXISTS 'lab_app'@'127.0.0.1' IDENTIFIED BY 'Pr0y3ct0_T3st_2026!';
GRANT ALL PRIVILEGES ON lab_usuarios.* TO 'lab_app'@'localhost';
GRANT ALL PRIVILEGES ON lab_usuarios.* TO 'lab_app'@'127.0.0.1';
FLUSH PRIVILEGES;
