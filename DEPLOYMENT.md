# Despliegue

## Google Cloud
Activa:
- Google Sheets API
- Google Drive API

Crea una cuenta de servicio y genera JSON.

## Google Sheets
Comparte el Sheet con el `client_email` de la cuenta de servicio como Lector.

## Streamlit Secrets
Usa el ejemplo `.streamlit/secrets.toml.example`.

Si la hoja se llama `FlotaGo`, deja:
```toml
flotago_worksheet_name = "FlotaGo"
```

## Streamlit Cloud
- Main file: `app.py`
- Reboot/Redeploy después de configurar secrets.
