# Despliegue Torre de Control COPEC

## Google Cloud
Activa:
- Google Sheets API
- Google Drive API

Crea una cuenta de servicio y descarga el JSON.

## Google Sheets
Comparte el Google Sheet con el `client_email` de la cuenta de servicio como Lector.

## Streamlit Secrets

Usa el formato del archivo `.streamlit/secrets.toml.example`.

Si tus hojas se llaman:
- `GUARDIAN`
- `FLOTAGO`

usa:

```toml
[google_sheet]
spreadsheet_id = "ID_DE_TU_GOOGLE_SHEET"
guardian_worksheet_name = "GUARDIAN"
flotago_worksheet_name = "FLOTAGO"
```

## Streamlit Cloud

- Main file path: `app.py`
- Luego configura Secrets
- Presiona Reboot app
