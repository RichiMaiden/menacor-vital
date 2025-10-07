import flet as ft

def make_chip(label: str, icon=None, color=None, padding: int = 6):
    """
    Chip compatible con versiones antiguas de Flet:
    - Si hay icono, lo dibuja con ft.Icon(icon).
    - Usa un Container estilizado (no ft.Chip) para evitar errores de API.
    """
    leading = ft.Icon(icon, size=14) if icon else None
    content = ft.Row(
        controls=(([leading] if leading else []) + [ft.Text(label, size=12)]),
        spacing=6,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )

    return ft.Container(
        content=content,
        bgcolor=color or ft.Colors.GREY_200,
        border_radius=16,
        padding=ft.padding.symmetric(padding, 10),
    )

def make_card(title: str, content_controls: list):
    return ft.Card(
        content=ft.Container(
            padding=12,
            content=ft.Column(
                [ft.Text(title, weight=ft.FontWeight.BOLD), *content_controls],
                spacing=8,
            ),
        )
    )
