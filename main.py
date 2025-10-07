import flet as ft
import datetime

# --- Lógica local y sincronización
try:
    from app import db
except ImportError:
    import db

# --- Tema, componentes y sesión
try:
    from ui import theme
except Exception:
    import theme

try:
    from ui.components import make_chip, make_card
except Exception:
    from components import make_chip, make_card

try:
    from auth.session import session
except Exception:
    from session import session


APP_TITLE = "Menacor Vital"

# --- Helper para íconos compatibles
def I(name: str, fallback: str):
    return getattr(ft.Icons, name, getattr(ft.Icons, fallback))


def _spacer(h=8):
    return ft.Container(height=h)


def _subtitle(text: str):
    return ft.Text(text, style=ft.TextThemeStyle.TITLE_MEDIUM, weight=ft.FontWeight.W_600)


def _input(label: str, **kwargs):
    base = dict(label=label, dense=True, border=ft.InputBorder.OUTLINE, border_radius=12)
    base.update(kwargs)
    return ft.TextField(**base)


def _primary_button(label: str, icon=None, on_click=None):
    return ft.ElevatedButton(
        label,
        icon=icon,
        on_click=on_click,
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=12),
            padding=ft.padding.symmetric(14, 18),
        ),
    )


def _ghost_button(label: str, icon=None, on_click=None):
    return ft.OutlinedButton(
        label,
        icon=icon,
        on_click=on_click,
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=12),
            padding=ft.padding.symmetric(12, 16),
        ),
    )


def _surface(container_content, padding=16, margin=0):
    return ft.Container(
        content=container_content,
        padding=padding,
        margin=margin,
        bgcolor=ft.Colors.with_opacity(0.98, ft.Colors.WHITE),
        border_radius=16,
        shadow=ft.BoxShadow(
            spread_radius=1,
            blur_radius=16,
            color=ft.Colors.with_opacity(0.08, ft.Colors.BLACK54),
            offset=ft.Offset(0, 4),
        ),
    )


def main(page: ft.Page):
    page.title = APP_TITLE
    page.padding = 0
    page.scroll = ft.ScrollMode.AUTO

    # --- Tema
    def apply_theme(dark: bool):
        page.theme_mode = ft.ThemeMode.DARK if dark else ft.ThemeMode.LIGHT
        page.update()

    is_dark = False
    apply_theme(is_dark)

    def toggle_theme(e):
        nonlocal is_dark
        is_dark = not is_dark
        apply_theme(is_dark)

    page.appbar = ft.AppBar(
        title=ft.Row(
            [ft.Icon(I("MONITOR_HEART_ROUNDED", "MONITOR_HEART")), ft.Text(APP_TITLE, weight=ft.FontWeight.W_700)],
            spacing=8,
        ),
        center_title=False,
        bgcolor=getattr(theme, "PRIMARY_COLOR", "#4CAF50"),
        color=ft.Colors.WHITE,
        actions=[
            ft.IconButton(
                I("DARK_MODE", "BRIGHTNESS_6") if not is_dark else I("LIGHT_MODE", "BRIGHTNESS_5"),
                on_click=toggle_theme,
                tooltip="Tema",
            ),
        ],
    )

    # --- Base de datos local
    db.ensure_db()

    # --- FilePicker para exportar CSV
    file_picker = ft.FilePicker()
    page.overlay.append(file_picker)
    page.update()

    # ---------------------------
    # Sección Registro & Login
    # ---------------------------
    username = _input("Usuario", autofocus=True, prefix_icon=I("PERSON_OUTLINED", "PERSON"))
    password = _input("Contraseña", password=True, can_reveal_password=True, prefix_icon=I("LOCK_OUTLINE", "LOCK"))
    full_name = _input("Nombre completo", prefix_icon=I("BADGE_OUTLINED", "BADGE"))
    birthdate = _input("Fecha de nacimiento (AAAA-MM-DD)", value=datetime.date.today().isoformat(), prefix_icon=I("CALENDAR_MONTH_OUTLINED", "CALENDAR_MONTH"))
    email = _input("Email", prefix_icon=I("MAIL_OUTLINE", "MAIL"))
    register_errors = ft.Text("", color=ft.Colors.RED_400, size=12)

    def validate_register_fields():
        errors = []
        if not username.value.strip(): errors.append("• Usuario es obligatorio.")
        if not password.value.strip(): errors.append("• Contraseña es obligatoria.")
        if not birthdate.value.strip(): errors.append("• Fecha de nacimiento es obligatoria.")
        register_errors.value = "\n".join(errors)
        register_errors.visible = len(errors) > 0
        return len(errors) == 0

    def on_register(e):
        if not validate_register_fields():
            page.update()
            return
        try:
            uid = db.register_user(username.value.strip(), password.value.strip(), full_name.value.strip(), birthdate.value.strip(), email.value.strip())
            db.enqueue("user", uid, "create", {
                "username": username.value.strip(),
                "password": password.value.strip(),
                "full_name": (full_name.value or "").strip() or None,
                "birthdate": birthdate.value.strip(),
                "email": (email.value or "").strip() or None,
            })
            user = db.login_user(username.value.strip(), password.value.strip())
            if user:
                session.user = user
                page.snack_bar = ft.SnackBar(ft.Text(f"Usuario creado (id={uid}). Sesión iniciada."))
                page.snack_bar.open = True
                page.update()
                tabs.selected_index = 1
            else:
                page.snack_bar = ft.SnackBar(ft.Text(f"Usuario creado (id={uid}). Iniciá sesión."))
                page.snack_bar.open = True
                page.update()
            db.sync_if_possible()
        except Exception as ex:
            page.dialog = ft.AlertDialog(title=ft.Text("Error al registrar"), content=ft.Text(str(ex)))
            page.dialog.open = True
            page.update()

    register_btn = _primary_button("Crear cuenta", icon=I("PERSON_ADD_ROUNDED", "PERSON_ADD"), on_click=on_register)

    login_username = _input("Usuario", prefix_icon=I("PERSON", "ACCOUNT_CIRCLE"))
    login_password = _input("Contraseña", password=True, can_reveal_password=True, prefix_icon=I("LOCK", "LOCK"))

    def on_login(e):
        user = db.login_user(login_username.value.strip(), login_password.value.strip())
        if user:
            session.user = user
            page.snack_bar = ft.SnackBar(ft.Text(f"Bienvenido, {user['username']}"))
            page.snack_bar.open = True
            page.update()
            tabs.selected_index = 1
            load_history()
        else:
            page.dialog = ft.AlertDialog(title=ft.Text("Credenciales inválidas"))
            page.dialog.open = True
            page.update()

    login_btn = _ghost_button("Ingresar", icon=I("LOGIN", "LOGIN"), on_click=on_login)

    register_card = _surface(ft.Column([_subtitle("Crear cuenta"), username, password, full_name, birthdate, email, register_errors, register_btn], spacing=10))
    login_card = _surface(ft.Column([_subtitle("Ingresar"), login_username, login_password, login_btn], spacing=10))

    auth_view = ft.Container(padding=20, content=ft.Column([
        _spacer(6),
        ft.Text("Tu salud, en tus manos", style=ft.TextThemeStyle.HEADLINE_MEDIUM, weight=ft.FontWeight.W_700),
        ft.Text("Registra y consulta tus signos vitales de forma simple y segura.", color=ft.Colors.GREY),
        _spacer(12), register_card, _spacer(12), login_card, _spacer(12),
        ft.Text(f"Base local: {db.DB_PATH}", size=10, color=ft.Colors.GREY)
    ], spacing=8))

    # ---------------------------
    # Sección Registro de Datos
    # ---------------------------
    vital_date = _input("Fecha (AAAA-MM-DD)", value=datetime.date.today().isoformat(), prefix_icon=I("CALENDAR_MONTH", "EVENT"))
    vital_pressure = _input("Presión (ej. 120/80)", prefix_icon=I("MONITOR_HEART", "HEALING"))
    vital_glucose = _input("Glucosa (mg/dL)", prefix_icon=I("WATER_DROP_OUTLINED", "WATER_DROP"))
    vital_notes = _input("Notas", multiline=True, min_lines=2, max_lines=4, prefix_icon=I("NOTES", "NOTE"))

    def open_login_guard():
        page.dialog = ft.AlertDialog(title=ft.Text("Iniciá sesión"), content=ft.Text("Debes iniciar sesión para registrar tus datos."))
        page.dialog.open = True
        page.update()

    def on_save_vital(e):
        if not session.user:
            open_login_guard()
            return
        s, d = db.parse_pressure(vital_pressure.value.strip())
        try:
            vid = db.add_vital(session.user["id"], vital_date.value.strip(), vital_pressure.value.strip(), vital_glucose.value.strip(), vital_notes.value.strip())
            db.enqueue("vital", vid, "create", {
                "user_external": session.user["username"],
                "date": vital_date.value.strip(),
                "pressure_systolic": s,
                "pressure_diastolic": d,
                "glucose": float(vital_glucose.value.strip()) if vital_glucose.value.strip() else None,
                "notes": vital_notes.value.strip() or None,
            })
            page.snack_bar = ft.SnackBar(ft.Text("Dato guardado localmente. Sincronizando..."))
            page.snack_bar.open = True
            page.update()
            db.sync_if_possible()
            vital_pressure.value = ""; vital_glucose.value = ""; vital_notes.value = ""
            page.update(); load_history()
        except Exception as ex:
            page.dialog = ft.AlertDialog(title=ft.Text("Error al guardar"), content=ft.Text(str(ex)))
            page.dialog.open = True
            page.update()

    # --- Exportar CSV con FilePicker
    def on_export(e):
        if not session.user:
            open_login_guard()
            return

        data = db.export_csv(session.user["id"])
        csv_bytes = data.getvalue()

        def on_save_result(ev: ft.FilePickerResultEvent):
            if ev.path:
                try:
                    with open(ev.path, "wb") as f:
                        f.write(csv_bytes)
                    page.snack_bar = ft.SnackBar(ft.Text("CSV guardado correctamente."))
                    page.snack_bar.open = True
                    page.update()
                except Exception as ex:
                    page.dialog = ft.AlertDialog(title=ft.Text("Error al guardar"), content=ft.Text(str(ex)))
                    page.dialog.open = True
                    page.update()

        file_picker.on_result = on_save_result
        file_picker.save_file(file_name="historial_vital.csv")

    export_btn = _ghost_button("Exportar historial (CSV)", icon=I("DOWNLOAD", "FILE_DOWNLOAD"), on_click=on_export)
    sync_btn = _ghost_button("Sincronizar ahora", icon=I("SYNC", "SYNC"), on_click=lambda e: db.sync_if_possible())
    save_vital_btn = _primary_button("Guardar datos", icon=I("SAVE_ROUNDED", "SAVE"), on_click=on_save_vital)

    form_card = _surface(ft.Column([
        _subtitle("Registro de signos vitales"),
        vital_date, vital_pressure, vital_glucose, vital_notes,
        save_vital_btn, ft.Row([export_btn, sync_btn], spacing=8)
    ], spacing=10))
    register_view = ft.Container(padding=20, content=ft.Column([form_card], spacing=10))

    # ---------------------------
    # Sección Historial
    # ---------------------------
    history_list = ft.ListView(expand=True, spacing=8, padding=0, auto_scroll=False)

    def load_history():
        history_list.controls.clear()
        if not session.user:
            page.update()
            return
        rows = db.list_vitals(session.user["id"])
        for r in rows:
            chips = []
            if r["pressure_systolic"] is not None:
                chips.append(make_chip(f"PA: {r['pressure_systolic']}/{r['pressure_diastolic'] or ''}", icon=I("FAVORITE_OUTLINED","FAVORITE_BORDER")))
            if r["glucose"] is not None:
                chips.append(make_chip(f"Glucosa: {r['glucose']} mg/dL", icon=I("WATER_DROP","OPACITY")))
            if r["notes"]:
                chips.append(make_chip(r["notes"], icon=I("NOTE_OUTLINED","NOTE")))
            history_list.controls.append(make_card(title=r["date"], content_controls=[ft.Row(chips, wrap=True, spacing=6)]))
        page.update()

    def open_quick_add(e):
        if not session.user:
            open_login_guard()
            return

        q_date = _input("Fecha (AAAA-MM-DD)", value=datetime.date.today().isoformat())
        q_press = _input("Presión (120/80)")
        q_gluc = _input("Glucosa (mg/dL)")
        q_notes = _input("Notas")

        def on_quick_save(ev):
            s, d = db.parse_pressure(q_press.value.strip())
            try:
                vid = db.add_vital(session.user["id"], q_date.value.strip(), q_press.value.strip(), q_gluc.value.strip(), q_notes.value.strip())
                db.enqueue("vital", vid, "create", {
                    "user_external": session.user["username"],
                    "date": q_date.value.strip(),
                    "pressure_systolic": s,
                    "pressure_diastolic": d,
                    "glucose": float(q_gluc.value.strip()) if q_gluc.value.strip() else None,
                    "notes": q_notes.value.strip() or None,
                })
                db.sync_if_possible()
                page.snack_bar = ft.SnackBar(ft.Text("Registro rápido guardado."))
                page.snack_bar.open = True
                page.update()
                page.dialog.open = False
                page.update()
                load_history()
            except Exception as ex:
                page.dialog = ft.AlertDialog(title=ft.Text("Error al guardar"), content=ft.Text(str(ex)))
                page.dialog.open = True
                page.update()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Agregar registro rápido"),
            content=ft.Column([q_date, q_press, q_gluc, q_notes, _primary_button("Guardar", icon=I("SAVE","CHECK"), on_click=on_quick_save)], tight=True, spacing=8),
        )
        page.dialog = dialog
        dialog.open = True
        page.update()

    history_view = ft.Container(padding=12, content=history_list)
    page.floating_action_button = ft.FloatingActionButton(
        icon=I("ADD", "ADD_CIRCLE_OUTLINE"),
        tooltip="Agregar registro",
        on_click=open_quick_add,
        bgcolor=getattr(theme, "PRIMARY_COLOR", "#4CAF50"),
        foreground_color=ft.Colors.WHITE,
    )

    # --- Tabs
    tabs = ft.Tabs(selected_index=0, expand=1, tabs=[
        ft.Tab(text="Registro/Login", icon=I("PERSON","ACCOUNT_CIRCLE"), content=auth_view),
        ft.Tab(text="Registrar Datos", icon=I("HEALTH_AND_SAFETY","HEALING"), content=register_view),
        ft.Tab(text="Historial", icon=I("HISTORY","LIST"), content=history_view),
    ])
    page.add(tabs)
    db.sync_if_possible()


if __name__ == "__main__":
    ft.app(target=main)
