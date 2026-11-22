# Caso 3: Sistema de Control de Asistencia y Permisos (TecnoAndes S.A.C.)

Aplicación web fullstack en Django 6.1.3 desarrollada para la Práctica Grupal Semana 12 (IS093A). Automatiza el registro diario de asistencia con cálculo de horas extras, gestión jerárquica de permisos/vacaciones, reportes corporativos exportables en texto y auditoría integral mediante middleware.

## 1. Matriz de Roles Jerárquicos y Permisos

+--------------+------------+-----------+-----------+-----------+-----------+-----------+
| Rol / Grupo  | reg_asist  | sol_perm  | apr_perm  | rep_area  | rep_glob  | corr_asist|
+--------------+------------+-----------+-----------+-----------+-----------+-----------+
| Admin RRHH   | SI         | SI        | SI (Todo) | SI        | SI (+Sal) | SI        |
| Jefe de Área | SI         | SI        | SI (Área) | SI (Área) | NO        | NO        |
| Contador     | SI         | SI        | NO        | NO        | SI (Lect) | NO        |
| Empleado     | SI         | SI        | NO        | NO        | NO        | NO        |
+--------------+------------+-----------+-----------+-----------+-----------+-----------+

## 2. Arquitectura y Reglas Implementadas
* **RF1 (Empleados y Áreas):** 5 áreas corporativas, validación de DNI único (8 dígitos), correo `@tecnoandes.pe`, antigüedad calculada en años y meses, y confidencialidad de salarios (ocultos fuera de RRHH).
* **RF2 (Asistencia y Correcciones):** Marcación con timestamp automático, bloqueo de doble entrada abierta, cálculo de horas trabajadas y extras (>8h/día), y formulario de corrección exclusivo de RRHH con justificación mínima de 50 caracteres.
* **RF3 (Permisos y Vacaciones):** Validación de motivo (>=30 caracteres), fechas (`fin >= inicio`), bloqueo de superposición de permisos y verificación de saldo de vacaciones (30 días - días aprobados).
* **RF5 (Middleware Corporativo):** `ControlYAuditoriaRRHHMiddleware` bloquea cuentas desactivadas, emite recordatorios en días laborables, restringe marcaciones a +/- 2h del horario real y audita cambios/accesos 403.
* **RF6 (Admin y Exportación):** Filtros diarios por área y fecha, acción masiva *"Aprobar permisos seleccionados"* y exportación de reportes en texto plano (`/reportes/exportar/`).

## 3. Instalación y Datos de Prueba
1. `python -m venv venv` y `venv\Scripts\activate`
2. `pip install -r requirements.txt`
3. `python manage.py makemigrations` y `python manage.py migrate`
4. Poblar base de datos (5 áreas, 12 empleados, 55 asistencias, 12 permisos):
   `python poblar_datos.py`
5. `python manage.py runserver`

## 4. Credenciales de Prueba (Clave general: `Tecno2026!`)
* Admin RRHH: `admin_rrhh`
* Jefes de Área: `jefe_sistemas`, `jefe_ventas`
* Contador: `contador1`
* Empleados: `empleado1` ... `empleado7`
* Cuenta desactivada (prueba de bloqueo): `emp_bloqueado`

---
© 2026 Todos los derechos reservados por FriendEi21.