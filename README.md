# leiten-webhook

Webhook receiver que escucha eventos de **Pull Request** en GitHub y envía un email de notificación al autor del PR antes de que se haga el merge.

## Deploy en Vercel

El proyecto está deployado como Serverless Function en Vercel. El archivo principal es `api/index.py`.

## Variables de entorno (Vercel)

| Variable | Descripción |
|---|---|
| `GITHUB_WEBHOOK_SECRET` | Secret compartido con GitHub para validar firmas |
| `RESEND_API_KEY` | API Key de Resend para envío de emails |
| `GITHUB_TOKEN` | Fine-grained token de GitHub para consultar emails de autores |

## Configurar el webhook en GitHub

1. Ir a **Organization Settings** → **Webhooks** → **Add webhook**
2. **Payload URL**: `https://leiten-webhook.vercel.app/webhook`
3. **Content type**: `application/json`
4. **Secret**: el mismo valor que `GITHUB_WEBHOOK_SECRET`
5. **Events**: seleccionar solo **Pull requests**
6. Guardar

## Desarrollo local

```bash
git clone https://github.com/grupoLeiten/leiten-webhook.git
cd leiten-webhook
pip install -r requirements.txt
python app.py
```
