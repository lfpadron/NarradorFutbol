# Deploy en cPanel: Analista Futbol

Este proyecto es una app Streamlit. En cPanel conviene desplegarla como un
servicio interno en `127.0.0.1:8501` y publicar el subdominio con Apache como
reverse proxy HTTPS.

El patron para futuras misiones es:

| Mision | Subdominio | Puerto interno |
| --- | --- | --- |
| analista-futbol | futbol.astrogatolabs.com.mx | 8501 |
| siguiente-demo | demo2.astrogatolabs.com.mx | 8502 |
| siguiente-demo-2 | demo3.astrogatolabs.com.mx | 8503 |

## 1. Subir el proyecto

En el servidor, usa una ruta estable para las misiones. Por ejemplo:

```bash
sudo mkdir -p /opt/astrogato-missions
sudo chown "$USER":"$USER" /opt/astrogato-missions
cd /opt/astrogato-missions
git clone <URL_DEL_REPO> analista-futbol
cd analista-futbol
```

Si no usaras Git, sube el contenido del repo a esa carpeta evitando `.venv`,
`.env`, `.mypy_cache`, `.pytest_cache`, `.ruff_cache` y archivos `diff_*.txt`.

## 2. Crear variables de entorno

```bash
cp deploy/cpanel/analista-futbol.env.example deploy/cpanel/analista-futbol.env
openssl rand -hex 32
```

Edita `deploy/cpanel/analista-futbol.env`:

- `HOST_PORT=8501`
- `APP_BASE_URL=https://futbol.astrogatolabs.com.mx`
- `APP_SECRET_KEY=<salida de openssl rand -hex 32>`
- `STREAMLIT_SERVER_COOKIE_SECRET=<otra salida de openssl rand -hex 32>`
- `SEED_ADMIN_EMAIL_1=<tu correo admin>`
- `SEED_ADMIN_PASSWORD=<password temporal largo>`
- `OPENAI_API_KEY=<opcional>`
- variables SMTP, si quieres que la app mande invitaciones por correo.

No subas `analista-futbol.env` al repo.

## 3. Levantar el contenedor

Docker:

```bash
docker compose --env-file deploy/cpanel/analista-futbol.env -f deploy/cpanel/compose.analista-futbol.yaml up -d --build
docker compose -f deploy/cpanel/compose.analista-futbol.yaml ps
```

Podman:

```bash
podman compose --env-file deploy/cpanel/analista-futbol.env -f deploy/cpanel/compose.analista-futbol.yaml up -d --build
podman compose -f deploy/cpanel/compose.analista-futbol.yaml ps
```

La app queda escuchando solo en `127.0.0.1:8501`, no expuesta directamente a
Internet.

Para cargar una demo minima:

```bash
docker compose -f deploy/cpanel/compose.analista-futbol.yaml exec analista-futbol uv run python -m src.ingestion.run_ingestion --match-id 7534
docker compose -f deploy/cpanel/compose.analista-futbol.yaml exec analista-futbol uv run python -m src.transform.build_duckdb --match-id 7534 --force
```

Prueba local en el servidor:

```bash
curl -I http://127.0.0.1:8501/_stcore/health
```

## 4. Configurar Apache/cPanel como proxy

Requisitos de Apache: `mod_proxy`, `mod_proxy_http`, `mod_proxy_wstunnel`,
`mod_headers` y `mod_rewrite`.

Copia el include SSL:

```bash
sudo mkdir -p /etc/apache2/conf.d/userdata/ssl/2_4/<cpanel_user>/futbol.astrogatolabs.com.mx
sudo cp deploy/cpanel/apache-futbol.ssl.conf /etc/apache2/conf.d/userdata/ssl/2_4/<cpanel_user>/futbol.astrogatolabs.com.mx/streamlit_proxy.conf
```

Si necesitas forzar HTTP a HTTPS manualmente:

```bash
sudo mkdir -p /etc/apache2/conf.d/userdata/std/2_4/<cpanel_user>/futbol.astrogatolabs.com.mx
sudo cp deploy/cpanel/apache-futbol.std.conf /etc/apache2/conf.d/userdata/std/2_4/<cpanel_user>/futbol.astrogatolabs.com.mx/redirect_https.conf
```

Luego reconstruye Apache:

```bash
sudo /usr/local/cpanel/scripts/rebuildhttpdconf
sudo /usr/local/cpanel/scripts/restartsrv_httpd
```

Activa o revisa AutoSSL para `futbol.astrogatolabs.com.mx` desde WHM/cPanel.

## 5. Plantilla para futuras misiones

Para otra mision:

1. Crea el subdominio en cPanel.
2. Elige un puerto libre: `8502`, `8503`, etc.
3. Duplica el archivo `.env.example` de esa mision y cambia `HOST_PORT`.
4. Duplica el compose o crea uno nuevo apuntando al proyecto de esa mision.
5. Duplica el include Apache y cambia dominio y puerto.
6. Reconstruye Apache y levanta el contenedor.

Mantener cada demo en su propio contenedor evita choques de dependencias,
permite reinicios independientes y hace mas facil retirar una mision sin tocar
las demas.
