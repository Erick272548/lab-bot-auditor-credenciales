"""Inserta usuarios de ejemplo (ficticios) para que la demo de sqlmap tenga datos."""
import pymysql

CONEXION = dict(host="127.0.0.1", port=3350, user="lab_app",
                password="Pr0y3ct0_T3st_2026!", database="lab_usuarios", charset="utf8mb4")

USUARIOS = [
    ("Ana Prueba", "ana@example.com", "hash$ficticio$ana"),
    ("Beto Lab", "beto@example.com", "hash$ficticio$beto"),
    ("Carla Test", "carla@example.com", "hash$ficticio$carla"),
    ("Admin Ficticio", "admin@example.com", "hash$ficticio$admin"),
]

with pymysql.connect(**CONEXION) as conn, conn.cursor() as cur:
    cur.execute(
        """CREATE TABLE IF NOT EXISTS usuarios (
               id INT AUTO_INCREMENT PRIMARY KEY,
               nombre VARCHAR(100) NOT NULL,
               email VARCHAR(150) NOT NULL UNIQUE,
               password_hash VARCHAR(255) NOT NULL,
               creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"""
    )
    for nombre, email, pwd in USUARIOS:
        cur.execute(
            "INSERT INTO usuarios (nombre, email, password_hash) VALUES (%s,%s,%s) "
            "ON DUPLICATE KEY UPDATE nombre=VALUES(nombre)",
            (nombre, email, pwd),
        )
    conn.commit()
    cur.execute("SELECT COUNT(*) FROM usuarios")
    print("usuarios en la base:", cur.fetchone()[0])
