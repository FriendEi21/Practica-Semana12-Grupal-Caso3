"""Script de carga inicial Caso 3: 5 áreas, 12 empleados, 55 asistencias y 12 permisos."""

import os
from datetime import date, time, timedelta
from decimal import Decimal
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.contrib.auth.models import Group, Permission, User  # pylint: disable=wrong-import-position
from django.utils import timezone  # pylint: disable=wrong-import-position
from asistencia.models import Area, Asistencia, Empleado, Permiso  # pylint: disable=wrong-import-position


def poblar_caso3() -> None:
    """Genera grupos/permisos, 5 áreas, 12 empleados, 55 asistencias y 12 permisos."""
    hoy = None
    g_rrhh = None
    g_jefe = None
    g_emp = None
    g_cont = None
    p_reg = None
    p_sol = None
    p_apr = None
    p_rep_area = None
    p_rep_glob = None
    p_corr = None
    areas_map = {}
    empleados_spec = []
    empleados_lista = []
    creado = False
    idx = 0

    hoy = timezone.localdate()

    g_rrhh, _ = Group.objects.get_or_create(name="Admin RRHH")
    g_jefe, _ = Group.objects.get_or_create(name="Jefe de Área")
    g_emp, _ = Group.objects.get_or_create(name="Empleado")
    g_cont, _ = Group.objects.get_or_create(name="Contador")

    p_reg = Permission.objects.get(codename="registrar_asistencia")
    p_sol = Permission.objects.get(codename="solicitar_permiso")
    p_apr = Permission.objects.get(codename="aprobar_permiso")
    p_rep_area = Permission.objects.get(codename="ver_reportes_area")
    p_rep_glob = Permission.objects.get(codename="ver_reportes_globales")
    p_corr = Permission.objects.get(codename="corregir_asistencia")

    g_rrhh.permissions.set([p_reg, p_sol, p_apr, p_rep_area, p_rep_glob, p_corr])
    g_jefe.permissions.set([p_reg, p_sol, p_apr, p_rep_area])
    g_emp.permissions.set([p_reg, p_sol])
    g_cont.permissions.set([p_reg, p_sol, p_rep_glob])

    for nombre_a in ("Sistemas", "Contabilidad", "Ventas", "Logística", "RRHH"):
        area_obj, _ = Area.objects.get_or_create(
            nombre=nombre_a,
            defaults={"descripcion": f"Gerencia de {nombre_a} - TecnoAndes S.A.C."},
        )
        areas_map[nombre_a] = area_obj

    empleados_spec = [
        ("admin_rrhh", "72000001", "Valeria", "Salazar Ríos", "Gerente RRHH", "RRHH", date(2020, 3, 10), "planilla", Decimal("6500.00"), True, True, g_rrhh, True),
        ("jefe_sistemas", "72000002", "Diego", "Poma Huamán", "Jefe de Sistemas", "Sistemas", date(2021, 5, 15), "planilla", Decimal("5400.00"), False, False, g_jefe, True),
        ("jefe_ventas", "72000003", "Claudia", "Ramos Quispe", "Jefe de Ventas", "Ventas", date(2021, 8, 1), "planilla", Decimal("5100.00"), False, False, g_jefe, True),
        ("contador1", "72000004", "Luis", "Vargas Medina", "Contador Planilla", "Contabilidad", date(2022, 2, 20), "planilla", Decimal("4200.00"), False, False, g_cont, True),
        ("empleado1", "72000005", "Andrés", "Lozano Díaz", "Analista Backend", "Sistemas", date(2023, 1, 10), "planilla", Decimal("3600.00"), False, False, g_emp, True),
        ("empleado2", "72000006", "Sofía", "Castro Meza", "Soporte TI", "Sistemas", date(2024, 4, 1), "locacion", Decimal("2800.00"), False, False, g_emp, True),
        ("empleado3", "72000007", "Mateo", "Gómez Soto", "Ejecutivo Comercial", "Ventas", date(2022, 11, 5), "planilla", Decimal("3100.00"), False, False, g_emp, True),
        ("empleado4", "72000008", "Camila", "Peña Flores", "Asistente Ventas", "Ventas", date(2024, 6, 12), "locacion", Decimal("2400.00"), False, False, g_emp, True),
        ("empleado5", "72000009", "Renzo", "Cárdenas Vega", "Coordinador Almacén", "Logística", date(2021, 9, 18), "planilla", Decimal("3300.00"), False, False, g_emp, True),
        ("empleado6", "72000010", "Luciana", "Núñez Prado", "Analista Compras", "Logística", date(2023, 7, 3), "planilla", Decimal("3200.00"), False, False, g_emp, True),
        ("empleado7", "72000011", "Kevin", "Ortega Cruz", "Asistente Contable", "Contabilidad", date(2023, 10, 9), "planilla", Decimal("2700.00"), False, False, g_emp, True),
        ("emp_bloqueado", "72000012", "Jorge", "Méndez Lara", "Ex-Operador TI", "Sistemas", date(2022, 4, 4), "locacion", Decimal("2500.00"), False, False, g_emp, False),
    ]

    for uname, dni, nom, ape, car, area_n, f_ing, cont, sal, staff, superu, grp, activo in empleados_spec:
        correo = f"{uname}@tecnoandes.pe"
        u_obj, creado = User.objects.get_or_create(
            username=uname,
            defaults={"email": correo, "is_staff": staff, "is_superuser": superu},
        )
        if creado:
            u_obj.set_password("Tecno2026!")
            u_obj.save()
        u_obj.groups.add(grp)

        emp_obj, _ = Empleado.objects.get_or_create(
            usuario=u_obj,
            defaults={
                "dni": dni,
                "nombres": nom,
                "apellidos": ape,
                "cargo": car,
                "area": areas_map[area_n],
                "fecha_ingreso": f_ing,
                "tipo_contrato": cont,
                "email_corporativo": correo,
                "salario": sal,
                "activo": activo,
            },
        )
        empleados_lista.append(emp_obj)

    # 55 registros de asistencia (incluye jornadas >8h para probar reporte de horas extras)
    if Asistencia.objects.count() == 0:
        for idx in range(55):
            emp = empleados_lista[idx % 11]  # Empleados activos
            dia_atras = (idx // 11) + 1
            fecha_a = hoy - timedelta(days=dia_atras)
            h_ent = time(8, 0)
            h_sal = time(18, 30) if idx % 3 == 0 else time(17, 0)

            asist = Asistencia(
                empleado=emp,
                fecha=fecha_a,
                hora_entrada=h_ent,
                hora_salida=h_sal,
            )
            asist.calcular_jornada()
            asist.save()

    # 12 permisos (pendientes, aprobados y rechazados en diferentes áreas)
    if Permiso.objects.count() == 0:
        tipos = ["personal", "medico", "duelo", "maternidad_paternidad", "otro"]
        for idx in range(12):
            emp = empleados_lista[(idx % 10) + 1]
            f_ini = hoy + timedelta(days=(idx + 1) * 3)
            f_fin = f_ini + timedelta(days=(idx % 3))
            estado_p = "pendiente" if idx < 5 else ("aprobado" if idx < 10 else "rechazado")
            revisor = empleados_lista[0].usuario if estado_p != "pendiente" else None

            Permiso.objects.create(
                empleado=emp,
                tipo=tipos[idx % len(tipos)],
                fecha_inicio=f_ini,
                fecha_fin=f_fin,
                motivo=f"Solicitud formal de permiso #{idx + 1} por motivos debidamente justificados ante jefatura.",
                adjunto_descripcion=f"documento_sustento_{idx + 1}.pdf",
                estado=estado_p,
                revisado_por=revisor,
                fecha_revision=timezone.now() if revisor else None,
            )

    print(
        f"[OK] Poblado Caso 3: {Area.objects.count()} áreas, {Empleado.objects.count()} empleados, "
        f"{Asistencia.objects.count()} asistencias, {Permiso.objects.count()} permisos."
    )
# Fin def poblar_caso3()


if __name__ == "__main__":
    poblar_caso3()
