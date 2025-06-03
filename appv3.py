# appv3.py

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import os
import glob
import plotly.express as px
import json

# ==============================
# ARCHIVOS LOCALES / CONFIGURACIÓN
# ==============================

user_data_file = 'user_data.xlsx'
schedule_file = 'blocked_schedules.xlsx'
lab_capacities_file = 'lab_capacities.json'
group_limits_file = 'group_limits.xlsx'
comments_file = 'comments.xlsx'
initial_image_file_B501 = 'initial_image_B501.png'
initial_image_file_C402 = 'initial_image_C402.png'
# (Ya no usamos fondo personalizado)

# ------------------------------
# CARGAR / GUARDAR CAPACIDADES
# ------------------------------
def load_lab_capacities():
    if os.path.exists(lab_capacities_file):
        with open(lab_capacities_file, 'r') as f:
            return json.load(f)
    else:
        capacities = {"B501": 15, "C402": 22}
        with open(lab_capacities_file, 'w') as f:
            json.dump(capacities, f)
        return capacities

def save_lab_capacities(capacities):
    with open(lab_capacities_file, 'w') as f:
        json.dump(capacities, f)

lab_capacities = load_lab_capacities()
laboratories = ["B501", "C402"]

# ------------------------------
# GENERAR FRANJAS HORARIAS
# ------------------------------
def generate_time_slots(start_time, end_time, interval_minutes=30):
    slots = []
    current_time = start_time
    while current_time < end_time:
        slots.append(current_time.strftime("%H:%M"))
        current_time += timedelta(minutes=interval_minutes)
    return slots

hours = generate_time_slots(
    datetime.strptime("08:00", "%H:%M"),
    datetime.strptime("20:00", "%H:%M"),
    interval_minutes=30
)

# --------------------------------
# CARGAR / GUARDAR DATOS DE USUARIOS (Excel local)
# --------------------------------
def load_user_data():
    if os.path.exists(user_data_file):
        df = pd.read_excel(user_data_file, index_col=None)
        df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
        required_columns = [
            'Nombre', 'Apellido', 'Correo', 'Rol',
            'Código', 'Contraseña', 'C402_access', 'Temp_access_expiry'
        ]
        for col in required_columns:
            if col not in df.columns:
                if col == 'Temp_access_expiry':
                    df[col] = pd.NaT
                elif col == 'C402_access':
                    df[col] = 0
                else:
                    df[col] = ''
        return df
    else:
        # Crear DataFrame vacío con columnas requeridas
        df = pd.DataFrame(columns=[
            'Nombre', 'Apellido', 'Correo', 'Rol',
            'Código', 'Contraseña', 'C402_access', 'Temp_access_expiry'
        ])
        return df

def save_user_data(df):
    df.to_excel(user_data_file, index=False)

# --------------------------------
# CARGAR / GUARDAR HORARIOS BLOQUEADOS (Excel local)
# --------------------------------
def load_schedule_data():
    global schedule_data
    if os.path.exists(schedule_file):
        schedule_data = pd.read_excel(schedule_file, index_col=None)
        schedule_data = schedule_data.loc[:, ~schedule_data.columns.str.contains('^Unnamed')]
    else:
        schedule_data = pd.DataFrame(columns=[
            'Día', 'Hora', 'Laboratorio', 'Estado', 'Motivo'
        ])

def save_schedule_data():
    schedule_data.to_excel(schedule_file, index=False)

schedule_data = pd.DataFrame(columns=[
    'Día', 'Hora', 'Laboratorio', 'Estado', 'Motivo'
])

# --------------------------------
# CARGAR / GUARDAR RESERVAS POR DÍA (Excel local)
# --------------------------------
def get_reservations_for_day(date_str):
    reservation_file = f"{date_str}.xlsx"
    required_columns = [
        'Nombre', 'Apellido', 'Código', 'Correo',
        'Laboratorio', 'Hora', 'Propósito', 'Tipo',
        'Grupo', 'Cantidad_alumnos'
    ]
    if os.path.exists(reservation_file):
        reservations = pd.read_excel(reservation_file, index_col=None)
        reservations = reservations.loc[:, ~reservations.columns.str.contains('^Unnamed')]
        for col in required_columns:
            if col not in reservations.columns:
                if col == 'Cantidad_alumnos':
                    reservations[col] = 1
                else:
                    reservations[col] = ''
    else:
        reservations = pd.DataFrame(columns=required_columns)
    return reservations

def save_reservations_for_day(df, date_str):
    df.to_excel(f"{date_str}.xlsx", index=False)

# --------------------------------
# MOSTRAR LINEAMIENTOS DE LABORATORIO
# --------------------------------
def show_rules(lab=None):
    if lab:
        rules_file = f'lineamientos_{lab}.txt'
    else:
        rules_file = 'lineamientos.txt'
    if os.path.exists(rules_file):
        with open(rules_file, 'r') as f:
            rules = f.read()
    else:
        rules = """
        **Lineamientos para la reserva de laboratorios:**
        - Los alumnos deben respetar los equipos y mobiliario.
        - No se permite consumir alimentos ni bebidas dentro del laboratorio.
        - El horario de uso debe respetarse estrictamente.
        - Se debe solicitar permiso para el uso de equipos especiales.
        - Las actividades deben registrarse con anticipación.
        - El laboratorio debe dejarse limpio y ordenado después de cada uso.
        """
        with open(rules_file, 'w') as f:
            f.write(rules)
    st.markdown(rules)

# --------------------------------
# RESET DE VARIABLES TEMPORALES
# --------------------------------
def clear_availability_state():
    keys = ['show_availability', 'desired_start_time', 'desired_end_time', 'desired_hours', 'availability']
    for k in keys:
        if k in st.session_state:
            del st.session_state[k]

# ================================
# MENÚ DE AUTENTICACIÓN → LOGIN / REGISTRAR USUARIO
# ================================
def auth_page():
    st.title("Lab Sync")
    st.subheader("Facultad de Ingeniería - Universidad del Pacífico")
    st.markdown("---")

    option = st.selectbox("¿Qué deseas hacer?", ["Iniciar sesión", "Registrarse"])
    st.write("")  # Espacio extra

    if option == "Iniciar sesión":
        login_form()
    else:
        register_form()

def login_form():
    df_users = load_user_data()
    st.write("### Iniciar sesión")
    with st.form(key='login_form'):
        correo = st.text_input("Correo electrónico", key="login_correo")
        contraseña = st.text_input("Contraseña", type="password", key="login_password")
        submit = st.form_submit_button("Entrar")
    if submit:
        # Admin hardcodeado
        if correo == 'admin@up.edu.pe' and contraseña == 'admin123':
            st.session_state['logged_in'] = True
            st.session_state['role'] = 'admin'
            st.session_state['username'] = correo
            st.success(f"Inicio de sesión exitoso como {correo}.")
            return
        # C402 admin hardcodeado
        if correo.endswith('@c402.up.edu.pe') and contraseña == 'c402admin123':
            st.session_state['logged_in'] = True
            st.session_state['role'] = 'c402_admin'
            st.session_state['username'] = correo
            st.success(f"Inicio de sesión exitoso como {correo}.")
            return
        # Usuario normal desde Excel
        user_row = df_users[
            (df_users['Correo'] == correo) & (df_users['Contraseña'] == contraseña)
        ]
        if not user_row.empty:
            st.session_state['logged_in'] = True
            st.session_state['role'] = user_row.iloc[0]['Rol']
            st.session_state['username'] = correo
            st.success(f"Inicio de sesión exitoso como {correo}.")
            return
        else:
            st.error("Correo o contraseña incorrectos.")

def register_form():
    df_users = load_user_data()
    st.write("### Registro de nuevo usuario")
    with st.form(key='register_form'):
        nombre = st.text_input("Nombre", key="register_nombre")
        apellido = st.text_input("Apellido", key="register_apellido")
        correo = st.text_input("Correo electrónico", key="register_correo")
        codigo = st.text_input("Código de alumno", key="register_codigo")
        contraseña = st.text_input("Contraseña", type="password", key="register_contraseña")
        submit = st.form_submit_button("Registrarse")
    if submit:
        # Verificar si ya existe el correo
        if correo in df_users['Correo'].values:
            st.error("El correo electrónico ya está registrado.")
            return
        # Solo permitimos correos de alumnos con dominio @alum.up.edu.pe
        if not correo.endswith('@alum.up.edu.pe'):
            st.error("Solo los alumnos pueden registrarse con un correo institucional '@alum.up.edu.pe'.")
            return
        # Creamos la fila sin validar formalmente el código
        rol = 'alumno'
        c402_access = 0
        nueva_fila = pd.DataFrame({
            'Nombre': [nombre],
            'Apellido': [apellido],
            'Correo': [correo],
            'Rol': [rol],
            'Código': [codigo],
            'Contraseña': [contraseña],
            'C402_access': [c402_access],
            'Temp_access_expiry': [pd.NaT]
        })
        df_users = pd.concat([df_users, nueva_fila], ignore_index=True)
        save_user_data(df_users)
        st.success("Registro exitoso. Ahora puedes iniciar sesión.")
        return

# ================================================
# CERRAR SESIÓN
# ================================================
def logout():
    for key in list(st.session_state.keys()):
        if key not in ['logged_in', 'role', 'username', 'menu_option']:
            del st.session_state[key]
    st.session_state['logged_in'] = False
    st.session_state['role'] = None
    st.session_state['username'] = ''
    st.session_state['menu_option'] = 'Inicio'
    st.success("Has cerrado sesión correctamente.")
    return

# ================================================
# PANEL DE ADMINISTRACIÓN
# ================================================
def admin_view():
    st.write("## Panel de administración")
    admin_option = st.sidebar.selectbox(
        "Selecciona una opción",
        [
            "Ver Dashboard",
            "Ver reservas",
            "Bloquear horario",
            "Administrar acceso al C402",
            "Editar lineamientos",
            "Eliminar reservas",
            "Administrar cuentas",
            "Gestionar imágenes iniciales",
            "Configurar límites de grupos",
            "Configurar capacidades de laboratorios"
        ],
        key='admin_option'
    )
    if admin_option == "Ver Dashboard":
        show_admin_dashboard()
    elif admin_option == "Ver reservas":
        view_all_reservations()
    elif admin_option == "Bloquear horario":
        block_schedule()
    elif admin_option == "Administrar acceso al C402":
        grant_c402_access()
    elif admin_option == "Editar lineamientos":
        edit_rules()
    elif admin_option == "Eliminar reservas":
        delete_reservations()
    elif admin_option == "Administrar cuentas":
        manage_accounts()
    elif admin_option == "Gestionar imágenes iniciales":
        manage_initial_images()
    elif admin_option == "Configurar límites de grupos":
        configure_group_limits()
    elif admin_option == "Configurar capacidades de laboratorios":
        configure_lab_capacities()

def show_admin_dashboard():
    st.write("### Dashboard administrativo")
    st.write("#### Estadísticas de reservas")
    reservation_files = glob.glob('*.xlsx')
    exclude = [
        user_data_file, schedule_file,
        initial_image_file_B501, initial_image_file_C402,
        group_limits_file, comments_file
    ]
    reservation_files = [f for f in reservation_files if f not in exclude]
    total_reservations = 0
    lab_reservations = {lab: 0 for lab in laboratories}
    reservation_list = []
    for file in reservation_files:
        reservations = pd.read_excel(file, index_col=None)
        reservations = reservations.loc[:, ~reservations.columns.str.contains('^Unnamed')]
        date_str = file.replace('.xlsx', '')
        reservations['Fecha'] = date_str
        reservation_list.append(reservations)
        total_reservations += len(reservations)
        for lab in laboratories:
            lab_reservations[lab] += len(reservations[reservations['Laboratorio'] == lab])

    col1, col2 = st.columns(2)
    with col1:
        st.metric("Total de reservas", total_reservations)
    with col2:
        st.metric("Laboratorios", len(laboratories))

    data = pd.DataFrame.from_dict(lab_reservations, orient='index', columns=['Reservas'])
    data = data.reset_index().rename(columns={'index': 'Laboratorio'})
    fig = px.pie(data, values='Reservas', names='Laboratorio', title='Distribución de reservas por laboratorio')
    st.plotly_chart(fig)

    if reservation_list:
        all_reservations = pd.concat(reservation_list)
        all_reservations = all_reservations.sort_values(['Fecha', 'Hora'])
        reservations_over_time = all_reservations.groupby('Fecha').size().reset_index(name='Reservas')
        fig_time = px.line(reservations_over_time, x='Fecha', y='Reservas', title='Reservas a lo largo del tiempo')
        st.plotly_chart(fig_time)

        peak_hours = all_reservations.groupby('Hora').size().reset_index(name='Reservas')
        peak_hours['Hora'] = pd.to_datetime(peak_hours['Hora'], format='%H:%M')
        peak_hours = peak_hours.sort_values('Hora')
        fig_peak = px.bar(peak_hours, x=peak_hours['Hora'].dt.strftime('%H:%M'), y='Reservas', title='Reservas por hora')
        st.plotly_chart(fig_peak)

        user_reservations = all_reservations.groupby('Correo').size().reset_index(name='Reservas')
        top_users = user_reservations.sort_values('Reservas', ascending=False).head(10)
        fig_users = px.bar(top_users, x='Correo', y='Reservas', title='Top 10 usuarios con más reservas')
        st.plotly_chart(fig_users)
    else:
        st.write("No hay datos suficientes para generar métricas.")

def view_all_reservations():
    st.write("### Todas las reservas")
    reservation_files = glob.glob('*.xlsx')
    exclude = [
        user_data_file, schedule_file,
        initial_image_file_B501, initial_image_file_C402,
        group_limits_file, comments_file
    ]
    reservation_files = [f for f in reservation_files if f not in exclude]
    reservations_list = []
    for file in reservation_files:
        reservations = pd.read_excel(file, index_col=None)
        reservations = reservations.loc[:, ~reservations.columns.str.contains('^Unnamed')]
        date_str = file.replace('.xlsx', '')
        reservations['Fecha'] = date_str
        reservations_list.append(reservations)
    if reservations_list:
        all_reservations = pd.concat(reservations_list)
        all_reservations.sort_values(['Fecha', 'Hora'], inplace=True)
        st.dataframe(all_reservations.reset_index(drop=True))
    else:
        st.write("No hay reservas registradas.")

def block_schedule():
    st.write("### Bloquear horario")
    with st.form(key='block_form'):
        selected_lab = st.selectbox(
            "Seleccionar laboratorio para bloquear",
            laboratories,
            key='admin_lab_block'
        )
        selected_day = st.date_input(
            "Seleccionar fecha para bloquear",
            key='admin_date_block'
        )
        date_str = selected_day.strftime("%Y-%m-%d")
        selected_start_time = st.selectbox(
            "Hora de inicio",
            hours,
            key='admin_start_time_block'
        )
        try:
            start_index = hours.index(selected_start_time) + 1
            available_end_times = hours[start_index:]
            if not available_end_times:
                st.error("No hay horas de fin disponibles después de la hora de inicio seleccionada.")
                selected_end_time = None
            else:
                selected_end_time = st.selectbox(
                    "Hora de fin",
                    available_end_times,
                    key='admin_end_time_block'
                )
        except ValueError:
            st.error("Hora de inicio seleccionada no es válida.")
            selected_end_time = None

        block_reason = st.text_area("Motivo del bloqueo (opcional)", key='admin_block_reason')
        submit_button = st.form_submit_button(label='Bloquear horario')

    if submit_button and selected_end_time:
        global schedule_data
        start_index = hours.index(selected_start_time)
        end_index = hours.index(selected_end_time)
        blocked_hours = hours[start_index:end_index]
        new_rows = pd.DataFrame({
            'Día': [date_str]*len(blocked_hours),
            'Hora': blocked_hours,
            'Laboratorio': [selected_lab]*len(blocked_hours),
            'Estado': [1]*len(blocked_hours),
            'Motivo': [block_reason]*len(blocked_hours)
        })
        schedule_data = pd.concat([schedule_data, new_rows], ignore_index=True)
        save_schedule_data()
        st.success(f"Horario bloqueado en laboratorio {selected_lab} el día {date_str} de {selected_start_time} a {selected_end_time}.")

        affected_reservations = []
        for blocked_hour in blocked_hours:
            reservations = get_reservations_for_day(date_str)
            affected = reservations[
                (reservations['Laboratorio'] == selected_lab) &
                (reservations['Hora'] == blocked_hour)
            ]
            if not affected.empty:
                affected_reservations.append(affected)

        if affected_reservations:
            affected_df = pd.concat(affected_reservations)
            st.write("Se han encontrado las siguientes reservas afectadas:")
            st.dataframe(affected_df.reset_index(drop=True))
            for index, row in affected_df.iterrows():
                st.info(f"Se notificó a {row['Nombre']} {row['Apellido']} ({row['Correo']}) sobre el bloqueo.")
            for blocked_hour in blocked_hours:
                reservations = get_reservations_for_day(date_str)
                updated_reservations = reservations[
                    ~(
                        (reservations['Laboratorio'] == selected_lab) &
                        (reservations['Hora'] == blocked_hour)
                    )
                ]
                save_reservations_for_day(updated_reservations, date_str)
        else:
            st.write("No hay reservas afectadas por este bloqueo.")

def grant_c402_access():
    st.write("### Administrar acceso al laboratorio C402")
    st.write("En esta sección, puedes habilitar o deshabilitar el acceso de los alumnos al laboratorio C402, incluyendo permisos temporales.")
    user_data = load_user_data()
    alumnos = user_data[user_data['Rol'] == 'alumno']
    if alumnos.empty:
        st.write("No hay alumnos registrados.")
    else:
        selected_user = st.selectbox("Selecciona un alumno para cambiar su acceso", alumnos['Correo'], key='grant_access_user')
        user_row = alumnos[alumnos['Correo'] == selected_user].iloc[0]
        current_access = user_row['C402_access']
        temp_expiry = user_row['Temp_access_expiry'] if 'Temp_access_expiry' in user_row else pd.NaT

        access_status = "Habilitado" if current_access == 1 else "Deshabilitado"
        st.write(f"**Acceso actual al C402:** {access_status}")
        if pd.notna(temp_expiry):
            st.write(f"**Permiso temporal hasta:** {temp_expiry}")
        else:
            st.write(f"**Permiso temporal hasta:** No aplica")

        new_access = st.radio(
            "Nuevo estado de acceso",
            ["Habilitar", "Deshabilitar", "Habilitar temporalmente"],
            key='access_option'
        )

        if new_access == "Habilitar":
            if st.button("Actualizar acceso a Habilitado", key='enable_access_button'):
                user_data.loc[user_data['Correo'] == selected_user, 'C402_access'] = 1
                user_data.loc[user_data['Correo'] == selected_user, 'Temp_access_expiry'] = pd.NaT
                save_user_data(user_data)
                st.success(f"Acceso al laboratorio C402 habilitado para {user_row['Nombre']} {user_row['Apellido']}.")
                return

        elif new_access == "Deshabilitar":
            if st.button("Actualizar acceso a Deshabilitado", key='disable_access_button'):
                user_data.loc[user_data['Correo'] == selected_user, 'C402_access'] = 0
                user_data.loc[user_data['Correo'] == selected_user, 'Temp_access_expiry'] = pd.NaT
                save_user_data(user_data)
                st.success(f"Acceso al laboratorio C402 deshabilitado para {user_row['Nombre']} {user_row['Apellido']}.")
                return

        elif new_access == "Habilitar temporalmente":
            with st.form(key='temp_access_form'):
                days = st.number_input("Duración del permiso temporal (días)", min_value=1, max_value=365, value=7, key='temp_days')
                submit_temp = st.form_submit_button("Aplicar permiso temporal")
            if submit_temp:
                expiry_date = datetime.today() + timedelta(days=int(days))
                user_data.loc[user_data['Correo'] == selected_user, 'C402_access'] = 1
                user_data.loc[user_data['Correo'] == selected_user, 'Temp_access_expiry'] = expiry_date.strftime("%Y-%m-%d")
                save_user_data(user_data)
                st.success(f"Acceso temporal al laboratorio C402 habilitado para {user_row['Nombre']} {user_row['Apellido']} hasta {expiry_date.strftime('%Y-%m-%d')}.")
                return

def delete_reservations():
    st.write("### Eliminar reservas")
    user_data = load_user_data()
    current_user = st.session_state['username']
    user_reservations = []
    reservation_files = glob.glob('*.xlsx')
    exclude = [
        user_data_file, schedule_file,
        initial_image_file_B501, initial_image_file_C402,
        group_limits_file, comments_file
    ]
    reservation_files = [f for f in reservation_files if f not in exclude]
    for file in reservation_files:
        reservations = pd.read_excel(file, index_col=None)
        reservations = reservations.loc[:, ~reservations.columns.str.contains('^Unnamed')]
        date_str = file.replace('.xlsx', '')
        required_columns = [
            'Nombre', 'Apellido', 'Código', 'Correo',
            'Laboratorio', 'Hora', 'Propósito', 'Tipo',
            'Grupo', 'Cantidad_alumnos'
        ]
        for col in required_columns:
            if col not in reservations.columns:
                if col == 'Cantidad_alumnos':
                    reservations[col] = 1
                else:
                    reservations[col] = ''
        user_specific = reservations[reservations['Correo'] == current_user]
        if not user_specific.empty:
            user_specific['Fecha'] = date_str
            user_reservations.append(user_specific)

    if user_reservations:
        all_user_reservations = pd.concat(user_reservations)
        all_user_reservations = all_user_reservations.sort_values(['Fecha', 'Hora'])
        display_columns = ['Fecha', 'Laboratorio', 'Hora', 'Propósito', 'Tipo', 'Grupo', 'Cantidad_alumnos']
        for col in display_columns:
            if col not in all_user_reservations.columns:
                all_user_reservations[col] = ''
        st.dataframe(all_user_reservations[display_columns].reset_index(drop=True))

        all_user_reservations = all_user_reservations.reset_index(drop=True)
        selected_reservation = st.selectbox(
            "Seleccionar reserva a eliminar",
            all_user_reservations.index,
            format_func=lambda x: f"{all_user_reservations.loc[x]['Fecha']} - {all_user_reservations.loc[x]['Laboratorio']} - {all_user_reservations.loc[x]['Hora']}"
        )
        if st.button("Eliminar reserva"):
            reservation_row = all_user_reservations.loc[selected_reservation]
            reservation_file = f"{reservation_row['Fecha']}.xlsx"
            reservations = pd.read_excel(reservation_file, index_col=None)
            reservations = reservations.loc[:, ~reservations.columns.str.contains('^Unnamed')]
            condition = (
                (reservations['Correo'] == reservation_row['Correo']) &
                (reservations['Laboratorio'] == reservation_row['Laboratorio']) &
                (reservations['Hora'] == reservation_row['Hora'])
            )
            reservations = reservations[~condition]
            save_reservations_for_day(reservations, reservation_row['Fecha'])
            st.success("Reserva eliminada exitosamente.")
            return
    else:
        st.info("No tienes reservas para eliminar.")

def edit_rules():
    st.write("### Editar lineamientos")
    selected_lab = st.selectbox(
        "Seleccionar laboratorio para editar lineamientos",
        ["Global"] + laboratories,
        key='select_lab_edit_rules'
    )
    if selected_lab == "Global":
        rules_file = 'lineamientos.txt'
    else:
        rules_file = f'lineamientos_{selected_lab}.txt'
    if os.path.exists(rules_file):
        with open(rules_file, 'r') as f:
            rules = f.read()
    else:
        rules = ""
    new_rules = st.text_area("Edita los lineamientos aquí:", value=rules, height=300)
    if st.button("Guardar cambios"):
        with open(rules_file, 'w') as f:
            f.write(new_rules)
        st.success("Lineamientos actualizados exitosamente.")
        return

def manage_accounts():
    st.write("### Administrar cuentas")
    admin_option = st.selectbox(
        "Selecciona una acción",
        ["Agregar administrador", "Agregar C402 Admin"],
        key='manage_accounts_option'
    )
    if admin_option == "Agregar administrador":
        st.write("Agregar nuevas cuentas de administrador.")
        with st.form(key='add_admin_form'):
            nombre = st.text_input("Nombre", key="add_admin_nombre")
            apellido = st.text_input("Apellido", key="add_admin_apellido")
            correo = st.text_input("Correo electrónico", key="add_admin_correo")
            contraseña = st.text_input("Contraseña", type="password", key="add_admin_contraseña")
            submit_button = st.form_submit_button(label='Agregar administrador')
        if submit_button:
            user_data = load_user_data()
            if correo in user_data['Correo'].values:
                st.error("El correo electrónico ya está registrado.")
                return
            elif not correo.endswith('@up.edu.pe'):
                st.error("El correo debe ser institucional '@up.edu.pe'.")
                return
            new_admin = pd.DataFrame({
                'Nombre': [nombre],
                'Apellido': [apellido],
                'Correo': [correo],
                'Rol': ['admin'],
                'Código': ['00000000'],
                'Contraseña': [contraseña],
                'C402_access': [0],
                'Temp_access_expiry': [pd.NaT]
            })
            user_data = pd.concat([user_data, new_admin], ignore_index=True)
            save_user_data(user_data)
            st.success("Nuevo administrador agregado exitosamente.")
            return

    elif admin_option == "Agregar C402 Admin":
        st.write("Agregar nuevas cuentas de C402 Admin.")
        with st.form(key='add_c402_admin_form'):
            nombre = st.text_input("Nombre", key="add_c402_admin_nombre")
            apellido = st.text_input("Apellido", key="add_c402_admin_apellido")
            correo = st.text_input("Correo electrónico", key="add_c402_admin_correo")
            contraseña = st.text_input("Contraseña", type="password", key="add_c402_admin_contraseña")
            submit_button = st.form_submit_button(label='Agregar C402 Admin')
        if submit_button:
            user_data = load_user_data()
            if correo in user_data['Correo'].values:
                st.error("El correo electrónico ya está registrado.")
                return
            elif not correo.endswith('@up.edu.pe'):
                st.error("El correo debe ser institucional '@up.edu.pe'.")
                return
            new_c402_admin = pd.DataFrame({
                'Nombre': [nombre],
                'Apellido': [apellido],
                'Correo': [correo],
                'Rol': ['c402_admin'],
                'Código': ['00000000'],
                'Contraseña': [contraseña],
                'C402_access': [1],
                'Temp_access_expiry': [pd.NaT]
            })
            user_data = pd.concat([user_data, new_c402_admin], ignore_index=True)
            save_user_data(user_data)
            st.success("Nuevo C402 Admin agregado exitosamente.")
            return

def manage_initial_images():
    st.write("### Gestionar imágenes iniciales")
    st.write("Puedes subir imágenes específicas para cada laboratorio.")
    for lab in laboratories:
        st.write(f"#### Imagen para {lab}")
        image_file = f'initial_image_{lab}.png'
        uploaded_file = st.file_uploader(f"Subir imagen para {lab}", type=["png", "jpg", "jpeg"], key=f'upload_initial_image_{lab}')
        if uploaded_file:
            with open(image_file, "wb") as f:
                f.write(uploaded_file.getbuffer())
            st.success(f"Imagen para {lab} subida exitosamente.")
            return
        if os.path.exists(image_file):
            st.image(image_file, caption=f"Imagen actual para {lab}", use_column_width=True)

def configure_group_limits():
    st.write("### Configurar límites de grupos para C402")
    limits_file = group_limits_file
    if os.path.exists(limits_file):
        limits = pd.read_excel(limits_file, index_col=None)
        limits = limits.loc[:, ~limits.columns.str.contains('^Unnamed')]
    else:
        limits = pd.DataFrame(columns=['Tipo', 'Límite'])

    st.write("#### Límites actuales:")
    st.dataframe(limits.reset_index(drop=True))

    with st.form(key='update_limits_form'):
        tipo = st.text_input("Tipo de grupo (e.g., Grupal, Individual)", key='group_type')
        limite = st.number_input("Límite de alumnos por grupo", min_value=1, max_value=100, key='group_limit')
        submit_limit = st.form_submit_button("Actualizar límite")
    if submit_limit:
        if tipo in limits['Tipo'].values:
            limits.loc[limits['Tipo'] == tipo, 'Límite'] = limite
        else:
            new_limit = pd.DataFrame({'Tipo': [tipo], 'Límite': [limite]})
            limits = pd.concat([limits, new_limit], ignore_index=True)
        limits.to_excel(limits_file, index=False)
        st.success("Límite de grupo actualizado exitosamente.")
        return

def configure_lab_capacities():
    st.write("### Configurar capacidades de laboratorios")
    capacities = load_lab_capacities()
    capacity_df = pd.DataFrame(list(capacities.items()), columns=['Laboratorio', 'Capacidad'])
    st.write("#### Capacidades actuales:")
    st.dataframe(capacity_df.reset_index(drop=True))

    with st.form(key='update_capacities_form'):
        selected_lab = st.selectbox("Seleccionar laboratorio para actualizar capacidad", laboratories, key='select_lab_capacity')
        new_capacity = st.number_input(f"Nueva capacidad para {selected_lab}", min_value=1, max_value=100, value=lab_capacities[selected_lab], key='new_capacity')
        submit_capacity = st.form_submit_button("Actualizar capacidad")
    if submit_capacity:
        lab_capacities[selected_lab] = new_capacity
        save_lab_capacities(lab_capacities)
        st.success(f"Capacidad del laboratorio {selected_lab} actualizada a {new_capacity}.")
        return

# ================================================
# ADMINISTRACIÓN C402
# ================================================
def admin_c402_view():
    st.write("## Administración C402")
    admin_option = st.selectbox(
        "Selecciona una opción",
        ["Administrar acceso al C402", "Confirmar reservas cumplidas"],
        key='admin_c402_option'
    )
    if admin_option == "Administrar acceso al C402":
        grant_c402_access()
    elif admin_option == "Confirmar reservas cumplidas":
        confirm_reservations()

def confirm_reservations():
    st.write("### Confirmar reservas cumplidas")
    reservation_files = glob.glob('*.xlsx')
    exclude = [
        user_data_file, schedule_file,
        initial_image_file_B501, initial_image_file_C402,
        group_limits_file, comments_file
    ]
    reservation_files = [f for f in reservation_files if f not in exclude]
    reservations_list = []
    for file in reservation_files:
        reservations = pd.read_excel(file, index_col=None)
        reservations = reservations.loc[:, ~reservations.columns.str.contains('^Unnamed')]
        date_str = file.replace('.xlsx', '')
        reservations = reservations[reservations['Laboratorio'] == 'C402']
        if not reservations.empty:
            reservations['Fecha'] = date_str
            reservations_list.append(reservations)
    if reservations_list:
        all_reservations = pd.concat(reservations_list)
        all_reservations = all_reservations.sort_values(['Fecha', 'Hora'])
        st.dataframe(all_reservations.reset_index(drop=True))
        selected_reservation = st.selectbox(
            "Seleccionar reserva para confirmar",
            all_reservations.index,
            format_func=lambda x: f"{all_reservations.loc[x]['Fecha']} - {all_reservations.loc[x]['Hora']} - {all_reservations.loc[x]['Correo']}"
        )
        if st.button("Confirmar que se cumplió la reserva"):
            reservation_row = all_reservations.loc[selected_reservation]
            reservation_file = f"{reservation_row['Fecha']}.xlsx"
            reservations = pd.read_excel(reservation_file, index_col=None)
            reservations = reservations.loc[:, ~reservations.columns.str.contains('^Unnamed')]
            condition = (
                (reservations['Correo'] == reservation_row['Correo']) &
                (reservations['Hora'] == reservation_row['Hora'])
            )
            if 'Confirmado' not in reservations.columns:
                reservations['Confirmado'] = False
            reservations.loc[condition, 'Confirmado'] = True
            save_reservations_for_day(reservations, reservation_row['Fecha'])
            st.success("Reserva confirmada exitosamente.")
            return
    else:
        st.info("No hay reservas para confirmar.")

# ================================================
# MIS RESERVAS (Alumno)
# ================================================
def view_user_reservations():
    st.write("### Mis reservas")
    user_data = load_user_data()
    current_user = st.session_state['username']
    user_reservations = []
    reservation_files = glob.glob('*.xlsx')
    exclude = [
        user_data_file, schedule_file,
        initial_image_file_B501, initial_image_file_C402,
        group_limits_file, comments_file
    ]
    reservation_files = [f for f in reservation_files if f not in exclude]
    for file in reservation_files:
        reservations = pd.read_excel(file, index_col=None)
        reservations = reservations.loc[:, ~reservations.columns.str.contains('^Unnamed')]
        date_str = file.replace('.xlsx', '')
        required_columns = [
            'Nombre', 'Apellido', 'Código', 'Correo',
            'Laboratorio', 'Hora', 'Propósito', 'Tipo',
            'Grupo', 'Cantidad_alumnos'
        ]
        for col in required_columns:
            if col not in reservations.columns:
                if col == 'Cantidad_alumnos':
                    reservations[col] = 1
                else:
                    reservations[col] = ''
        user_specific = reservations[reservations['Correo'] == current_user]
        if not user_specific.empty:
            user_specific['Fecha'] = date_str
            user_reservations.append(user_specific)

    if user_reservations:
        all_user_reservations = pd.concat(user_reservations)
        all_user_reservations = all_user_reservations.sort_values(['Fecha', 'Hora'])
        display_columns = ['Fecha', 'Laboratorio', 'Hora', 'Propósito', 'Tipo', 'Grupo', 'Cantidad_alumnos']
        for col in display_columns:
            if col not in all_user_reservations.columns:
                all_user_reservations[col] = ''
        st.dataframe(all_user_reservations[display_columns].reset_index(drop=True))

        all_user_reservations = all_user_reservations.reset_index(drop=True)
        selected_reservation = st.selectbox(
            "Seleccionar reserva a eliminar",
            all_user_reservations.index,
            format_func=lambda x: f"{all_user_reservations.loc[x]['Fecha']} - {all_user_reservations.loc[x]['Laboratorio']} - {all_user_reservations.loc[x]['Hora']}"
        )
        if st.button("Eliminar reserva"):
            reservation_row = all_user_reservations.loc[selected_reservation]
            reservation_file = f"{reservation_row['Fecha']}.xlsx"
            reservations = pd.read_excel(reservation_file, index_col=None)
            reservations = reservations.loc[:, ~reservations.columns.str.contains('^Unnamed')]
            condition = (
                (reservations['Correo'] == reservation_row['Correo']) &
                (reservations['Laboratorio'] == reservation_row['Laboratorio']) &
                (reservations['Hora'] == reservation_row['Hora'])
            )
            reservations = reservations[~condition]
            save_reservations_for_day(reservations, reservation_row['Fecha'])
            st.success("Reserva eliminada exitosamente.")
            return
    else:
        st.info("No tienes reservas registradas.")

# ================================================
# ZONA DE COMENTARIOS (Alumno)
# ================================================
def comments_section():
    st.write("### Zona de comentarios")
    with st.form(key='comments_form'):
        nombre = st.text_input("Nombre", key='comment_nombre')
        correo = st.text_input("Correo electrónico", key='comment_correo')
        comentario = st.text_area("Comentario", key='comment_text')
        submit_comment = st.form_submit_button("Enviar comentario")
    if submit_comment:
        if not nombre or not correo or not comentario:
            st.error("Por favor, completa todos los campos.")
        else:
            if os.path.exists(comments_file):
                comments = pd.read_excel(comments_file, index_col=None)
                comments = comments.loc[:, ~comments.columns.str.contains('^Unnamed')]
            else:
                comments = pd.DataFrame(columns=['Nombre', 'Correo', 'Comentario', 'Fecha'])
            new_comment = pd.DataFrame({
                'Nombre': [nombre],
                'Correo': [correo],
                'Comentario': [comentario],
                'Fecha': [datetime.now().strftime("%Y-%m-%d %H:%M:%S")]
            })
            comments = pd.concat([comments, new_comment], ignore_index=True)
            comments.to_excel(comments_file, index=False)
            st.success("Comentario enviado exitosamente.")
            return

    if os.path.exists(comments_file):
        st.write("#### Comentarios recientes:")
        comments = pd.read_excel(comments_file, index_col=None)
        comments = comments.loc[:, ~comments.columns.str.contains('^Unnamed')]
        comments = comments.sort_values('Fecha', ascending=False).head(10)
        st.dataframe(comments.reset_index(drop=True))

# ================================================
# RESERVA DE LABORATORIO (Alumno)
# ================================================
def student_view():
    st.write("## Reserva de laboratorio")
    user_data = load_user_data()
    current_user = st.session_state['username']
    user_row = user_data[user_data['Correo'] == current_user].iloc[0]

    # Determinar laboratorios accesibles
    if user_row['C402_access'] == 1:
        if pd.notna(user_row['Temp_access_expiry']):
            expiry_date = pd.to_datetime(user_row['Temp_access_expiry'])
            if datetime.today() > expiry_date:
                user_data.loc[user_data['Correo'] == current_user, 'C402_access'] = 0
                user_data.loc[user_data['Correo'] == current_user, 'Temp_access_expiry'] = pd.NaT
                save_user_data(user_data)
                st.warning("Tu acceso temporal al laboratorio C402 ha expirado.")
                accessible_labs = ["B501"]
            else:
                accessible_labs = ["B501", "C402"]
        else:
            accessible_labs = ["B501", "C402"]
    else:
        accessible_labs = ["B501"]

    # ---------- Paso 1: Seleccionar laboratorio y fecha ----------
    st.write("### Paso 1: Seleccionar laboratorio y fecha")
    selected_lab = st.selectbox(
        "Seleccionar laboratorio",
        accessible_labs,
        key='student_lab_select',
        on_change=clear_availability_state
    )
    selected_day = st.date_input(
        "Seleccionar fecha",
        min_value=datetime.today().date(),
        key='student_date_select',
        on_change=clear_availability_state
    )

    # Mostrar imagen inicial si existe
    image_file = f'initial_image_{selected_lab}.png'
    if os.path.exists(image_file):
        st.image(image_file, caption=f"Horarios disponibles para {selected_lab}", use_column_width=True)

    # ---------- Paso 2: Verificar disponibilidad ----------
    if selected_lab and selected_day:
        date_str = selected_day.strftime("%Y-%m-%d")
        show_rules(selected_lab)

        st.write("### Paso 2: Seleccionar horario y verificar disponibilidad")
        with st.form(key='availability_form'):
            col1, col2 = st.columns(2)
            with col1:
                selected_start_time = st.selectbox(
                    "Hora de inicio",
                    hours,
                    key='student_start_time_select'
                )
            with col2:
                # Calcular horas de fin disponibles basadas en inicio
                try:
                    start_index = hours.index(selected_start_time) + 1
                    available_end_times = hours[start_index:]
                    if not available_end_times:
                        st.error("No hay horas de fin disponibles después de la hora de inicio seleccionada.")
                        selected_end_time = None
                    else:
                        selected_end_time = st.selectbox(
                            "Hora de fin",
                            available_end_times,
                            key='student_end_time_select'
                        )
                except ValueError:
                    st.error("Hora de inicio seleccionada no es válida.")
                    selected_end_time = None

            submit_avail = st.form_submit_button("Verificar disponibilidad")

        if submit_avail:
            if not selected_start_time or not selected_end_time:
                st.error("Debes seleccionar hora de inicio y hora de fin válidas.")
            else:
                # Validar límites de B501
                if selected_lab == "B501":
                    max_time = "17:30"
                    if selected_start_time > max_time or selected_end_time > max_time:
                        st.error(f"Las reservas en {selected_lab} solo están permitidas hasta las {max_time}.")
                        return

                # Calcular horas deseadas
                try:
                    start_i = hours.index(selected_start_time)
                    end_i = hours.index(selected_end_time)
                    desired_hours = hours[start_i:end_i]
                except ValueError:
                    st.error("Error al parsear las horas seleccionadas.")
                    return

                # Cargar datos del día
                reservations = get_reservations_for_day(date_str)
                lab_reservations = reservations[reservations['Laboratorio'] == selected_lab]
                blocked = schedule_data[
                    (schedule_data['Día'] == date_str) &
                    (schedule_data['Laboratorio'] == selected_lab)
                ]

                # Verificar si alguna hora está bloqueada
                is_blocked = blocked['Hora'].isin(desired_hours).any()
                if is_blocked:
                    st.error(f"El horario seleccionado está bloqueado en {selected_lab}.")
                    return

                # Calcular disponibilidad
                capacity = lab_capacities[selected_lab]
                total_res = lab_reservations.groupby('Hora').size().reset_index(name='count')
                availability = {}
                for hour in desired_hours:
                    count = total_res[total_res['Hora'] == hour]['count'].sum()
                    available_spots = capacity - count if not pd.isna(count) else capacity
                    availability[hour] = available_spots

                # Chequear si todas las horas tienen cupo
                if not all(availability[hour] > 0 for hour in desired_hours):
                    st.error("No hay suficientes cupos en el rango seleccionado.")
                    return

                # Guardar en session_state para mostrar disponibilidad abajo
                st.session_state['show_availability'] = True
                st.session_state['desired_start_time'] = selected_start_time
                st.session_state['desired_end_time'] = selected_end_time
                st.session_state['desired_hours'] = desired_hours
                st.session_state['availability'] = availability
                st.session_state['available_capacity'] = capacity

        # ---------- Mostrar disponibilidad si ya fue calculada ----------
        if st.session_state.get('show_availability', False):
            st.write("### Disponibilidad por horario:")
            availability = st.session_state['availability']
            capacity = st.session_state['available_capacity']
            for hour in st.session_state['desired_hours']:
                avail_spots = availability[hour]
                if avail_spots <= 0:
                    st.markdown(f"**{hour}** - No disponible")
                    st.progress(0)
                else:
                    st.markdown(f"**{hour}** - {avail_spots} cupos disponibles")
                    st.progress(avail_spots / capacity)

            # ---------- Paso 3: Confirmar reserva ----------
            st.write("### Paso 3: Confirmar reserva")
            with st.form(key='confirm_reservation_form'):
                if selected_lab == 'C402':
                    st.write("#### Detalles de la reserva")
                    reservation_type = st.radio("Tipo de reserva", ['Individual', 'Grupal'], key='reservation_type_confirm')
                    if reservation_type == 'Grupal':
                        grupo = st.text_input("Nombre del grupo", key='group_name_confirm')
                        cantidad_alumnos = st.number_input(
                            "Cantidad de alumnos",
                            min_value=2,
                            max_value=lab_capacities['C402'],
                            key='group_size_confirm'
                        )
                    else:
                        grupo = ""
                        cantidad_alumnos = 1
                    propósito = st.text_input("Propósito de la reserva", key='reservation_purpose_confirm')
                else:
                    propósito = ""
                    reservation_type = ""
                    grupo = ""
                    cantidad_alumnos = 1

                submit_confirm = st.form_submit_button("Confirmar reserva")

            if submit_confirm:
                # Prevenir reservas pasadas si la fecha es hoy
                if selected_day == datetime.today().date():
                    current_time = datetime.now().strftime("%H:%M")
                    if st.session_state['desired_start_time'] <= current_time:
                        st.error("No puedes reservar en horarios pasados.")
                        return

                # Verificar acceso C402
                if selected_lab == 'C402' and user_row['C402_access'] == 0:
                    st.error("No tienes acceso al laboratorio C402.")
                    return

                # Límite grupal para C402
                if selected_lab == 'C402' and reservation_type == 'Grupal':
                    if os.path.exists(group_limits_file):
                        limits = pd.read_excel(group_limits_file, index_col=None)
                        limits = limits.loc[:, ~limits.columns.str.contains('^Unnamed')]
                    else:
                        limits = pd.DataFrame(columns=['Tipo', 'Límite'])
                    grp_lim = limits[limits['Tipo'] == 'Grupal']['Límite'].values
                    if len(grp_lim) > 0 and cantidad_alumnos > grp_lim[0]:
                        st.error(f"El límite de alumnos por grupo es {grp_lim[0]}.")
                        return

                # Verificar capacidad global en C402
                if selected_lab == 'C402':
                    current_total = sum(lab_reservations['Cantidad_alumnos'])
                    new_total = current_total + cantidad_alumnos
                    if new_total > lab_capacities['C402']:
                        st.error(
                            f"Al agregar esta reserva, total ({new_total}) excede capacidad máxima ({lab_capacities['C402']})."
                        )
                        return

                # Guardar la reserva
                reservations_all = get_reservations_for_day(date_str)
                new_entries = pd.DataFrame({
                    'Nombre': [user_row['Nombre']] * len(st.session_state['desired_hours']),
                    'Apellido': [user_row['Apellido']] * len(st.session_state['desired_hours']),
                    'Código': [user_row['Código']] * len(st.session_state['desired_hours']),
                    'Correo': [user_row['Correo']] * len(st.session_state['desired_hours']),
                    'Laboratorio': [selected_lab] * len(st.session_state['desired_hours']),
                    'Hora': st.session_state['desired_hours'],
                    'Propósito': [propósito] * len(st.session_state['desired_hours']),
                    'Tipo': [reservation_type] * len(st.session_state['desired_hours']),
                    'Grupo': [grupo] * len(st.session_state['desired_hours']),
                    'Cantidad_alumnos': [cantidad_alumnos] * len(st.session_state['desired_hours'])
                })
                if reservations_all.empty:
                    reservations_all = new_entries
                else:
                    reservations_all = pd.concat([reservations_all, new_entries], ignore_index=True)
                save_reservations_for_day(reservations_all, date_str)
                st.success(f"Reserva exitosa para el {date_str} de {st.session_state['desired_start_time']} a {st.session_state['desired_end_time']} en {selected_lab}.")
                # Limpiar estado de disponibilidad
                clear_availability_state()
                return

    # ------------------------------
    # SECCIÓN DE COMENTARIOS
    # ------------------------------
    st.write("---")
    comments_section()

# ================================================
# VISTA PRINCIPAL (DESPUÉS DE LOGIN)
# ================================================
def main_app():
    load_schedule_data()

    # CSS global (sin fondo completo)
    css = """
    <style>
    body {
        background-color: #f0f2f6;
        color: #000000;
        font-family: 'Helvetica Neue', sans-serif;
    }
    h1, h2 {
        color: #002D62;
    }
    .stButton>button {
        background-color: #002D62;
        color: #FFFFFF;
        border-radius: 5px;
        width: 100%;
    }
    .stSelectbox>div>div>div>div {
        color: #002D62;
    }
    .sidebar .sidebar-content {
        background-color: #FFFFFF;
    }
    .footer {
        position: fixed;
        left: 0;
        bottom: 0;
        width: 100%;
        background-color: #002D62;
        color: white;
        text-align: center;
        padding: 10px;
    }
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)

    # Inicializar session_state si no existe
    if 'logged_in' not in st.session_state:
        st.session_state['logged_in'] = False
    if 'role' not in st.session_state:
        st.session_state['role'] = None
    if 'username' not in st.session_state:
        st.session_state['username'] = ''
    if 'menu_option' not in st.session_state:
        st.session_state['menu_option'] = 'Inicio'

    # Si no está logueado, ir a la pantalla de login/registro
    if not st.session_state['logged_in']:
        auth_page()
        return

    # Ya está logueado, obtenemos user_row
    user_data = load_user_data()
    current_user = st.session_state['username']
    if current_user == 'admin@up.edu.pe':
        user_row = pd.Series({
            'Nombre': 'Admin',
            'Apellido': 'User',
            'Correo': 'admin@up.edu.pe',
            'Rol': 'admin',
            'C402_access': 0,
            'Temp_access_expiry': pd.NaT
        })
    elif current_user.endswith('@c402.up.edu.pe'):
        user_row = pd.Series({
            'Nombre': 'C402',
            'Apellido': 'Admin',
            'Correo': current_user,
            'Rol': 'c402_admin',
            'C402_access': 1,
            'Temp_access_expiry': pd.NaT
        })
    else:
        user_row = user_data[user_data['Correo'] == current_user].iloc[0]

    # Menú lateral según rol
    st.sidebar.write(f"**Usuario:** {user_row['Nombre']} {user_row['Apellido']}")
    if st.session_state['role'] == 'admin':
        menu = ["Inicio", "Administración", "Cerrar sesión"]
    elif st.session_state['role'] == 'c402_admin':
        menu = ["Inicio", "Administración C402", "Cerrar sesión"]
    else:
        menu = ["Inicio", "Reservar laboratorio", "Mis reservas", "Zona de comentarios", "Cerrar sesión"]

    choice = st.sidebar.selectbox("Menú", menu, index=menu.index(st.session_state['menu_option']))
    if choice != st.session_state['menu_option']:
        st.session_state['menu_option'] = choice

    # Renderizado según la opción seleccionada
    if choice == "Inicio":
        st.write(f"### Bienvenido a Lab Sync, {user_row['Nombre']} {user_row['Apellido']}.")
        st.write("Selecciona una opción en el menú para comenzar.")
        st.write("O puedes usar los siguientes accesos directos:")
        col1, col2 = st.columns(2)
        if st.session_state['role'] not in ['admin', 'c402_admin']:
            with col1:
                if st.button("Reservar laboratorio"):
                    st.session_state['menu_option'] = "Reservar laboratorio"
            with col2:
                if st.button("Mis reservas"):
                    st.session_state['menu_option'] = "Mis reservas"
            with st.container():
                if st.button("Zona de comentarios"):
                    st.session_state['menu_option'] = "Zona de comentarios"
        if st.session_state['role'] == 'admin':
            with col1:
                if st.button("Panel de administración"):
                    st.session_state['menu_option'] = "Administración"
        if st.session_state['role'] == 'c402_admin':
            with col1:
                if st.button("Administración C402"):
                    st.session_state['menu_option'] = "Administración C402"

        st.markdown(
            """
            <div class='footer'>
                Correo: labs.ingenieria@up.edu.pe | Teléfono: +51 123 4567 | Ubicaciones: Edificio B, Laboratorio 501 y 402
            </div>
            """,
            unsafe_allow_html=True
        )

    elif choice == "Reservar laboratorio":
        if st.session_state['role'] not in ['admin', 'c402_admin']:
            student_view()
        else:
            st.error("No tienes permisos para acceder a esta sección.")

    elif choice == "Administración":
        if st.session_state['role'] == 'admin':
            admin_view()
        else:
            st.error("No tienes permisos para acceder a esta sección.")

    elif choice == "Administración C402":
        if st.session_state['role'] == 'c402_admin':
            admin_c402_view()
        else:
            st.error("No tienes permisos para acceder a esta sección.")

    elif choice == "Mis reservas":
        if st.session_state['role'] not in ['admin', 'c402_admin']:
            view_user_reservations()
        else:
            st.error("No tienes permisos para acceder a esta sección.")

    elif choice == "Zona de comentarios":
        if st.session_state['role'] not in ['admin', 'c402_admin']:
            comments_section()
        else:
            st.error("No tienes permisos para acceder a esta sección.")

    elif choice == "Cerrar sesión":
        logout()
        return

if __name__ == "__main__":
    main_app()
