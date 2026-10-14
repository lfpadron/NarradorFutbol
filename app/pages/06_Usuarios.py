from src.security.user_management import render_users_page
from src.ui.footer import render_footer
from src.ui.navigation import ensure_page_shell

ensure_page_shell("Usuarios")
render_users_page()
render_footer()
