from src.security.streamlit_auth import render_profile_page
from src.ui.footer import render_footer
from src.ui.navigation import ensure_page_shell

ensure_page_shell("Mi usuario")
render_profile_page()
render_footer()
