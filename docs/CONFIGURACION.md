# Leiten Webhook - Configuracion y Plan de Accion

## Que hace este sistema

Cuando alguien abre un Pull Request en cualquier repositorio de la organizacion **grupoLeiten** en GitHub, el sistema envia automaticamente un email al autor del PR notificandole que sus cambios fueron enviados correctamente.

**Flujo:** GitHub PR abierto → Webhook → Vercel (serverless function Python) → Resend API → Email al autor

---

## Datos del proyecto

| Dato | Valor |
|------|-------|
| Repositorio | github.com/grupoLeiten/leiten-webhook |
| Deploy | Vercel (leiten-webhook.vercel.app) |
| Archivo principal | `api/index.py` |
| Servicio de email | Resend (resend.com) |
| Remitente | Leiten IT <onboarding@resend.dev> |
| Asunto del email | Tus cambios se enviaron correctamente |

---

## Variables de entorno en Vercel

Estas son las variables que deben estar configuradas en **Vercel > Settings > Environment Variables** (Production):

| Variable | Descripcion | Donde se obtiene |
|----------|-------------|------------------|
| `RESEND_API_KEY` | API key de Resend para enviar emails | resend.com > API Keys |
| `GITHUB_WEBHOOK_SECRET` | Secret compartido con el webhook de GitHub | GitHub org > Settings > Webhooks |
| `GITHUB_TOKEN` | Token de GitHub (fine-grained) para leer datos de PRs | github.com > Settings > Developer settings > Personal access tokens |

**Variables viejas que NO se usan (borrar si aparecen):** `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `EMAIL_FROM`

---

## Configuracion del Webhook en GitHub

Ubicacion: github.com/organizations/grupoLeiten > Settings > Webhooks

| Campo | Valor |
|-------|-------|
| Payload URL | `https://leiten-webhook.vercel.app/api/index` |
| Content type | `application/json` |
| Secret | (mismo valor que `GITHUB_WEBHOOK_SECRET` en Vercel) |
| Eventos | Solo "Pull requests" |
| Activo | Si |

---

## Cuenta de Resend

| Dato | Valor |
|------|-------|
| URL | resend.com |
| Email de la cuenta | (el que usaron para registrarse) |
| Plan | Free tier |
| Limitacion | Solo puede enviar desde `onboarding@resend.dev` |
| Para usar dominio propio | Agregar y verificar dominio en Resend > Domains |

---

## Plan de Accion - Si deja de funcionar

### Paso 1: Verificar que el webhook esta activo

1. Ir a github.com/organizations/grupoLeiten > Settings > Webhooks
2. Verificar que el webhook apunta a `https://leiten-webhook.vercel.app/api/index`
3. Hacer click en el webhook y revisar "Recent Deliveries" al final
4. Si hay entregas con error (rojo), hacer click para ver el detalle

### Paso 2: Verificar que Vercel responde

1. Abrir en el navegador: `https://leiten-webhook.vercel.app`
2. Deberia mostrar un JSON con status de la configuracion
3. Si no responde, ir a vercel.com > proyecto leiten-webhook > Deployments
4. Verificar que el ultimo deploy esta en estado "Ready"

### Paso 3: Verificar variables de entorno

1. Ir a vercel.com > proyecto leiten-webhook > Settings > Environment Variables
2. Confirmar que existen: `RESEND_API_KEY`, `GITHUB_WEBHOOK_SECRET`, `GITHUB_TOKEN`
3. Si se cambio alguna variable, **hay que hacer un redeploy** (Vercel NO redeploya automaticamente al cambiar env vars)

**Como forzar un redeploy:**
- Ir a Deployments > ultimo deploy > click en "..." > Redeploy
- O pushear cualquier commit a main

### Paso 4: Verificar Resend

1. Ir a resend.com > API Keys
2. Confirmar que la API key esta activa (no revocada)
3. Ir a resend.com > Emails para ver el log de emails enviados
4. Si aparecen errores, verificar que el destinatario sea valido

---

## Errores comunes y soluciones

### Email no llega pero el webhook responde 200

**Causa probable:** La API key de Resend es invalida o esta revocada.
**Solucion:** Verificar en resend.com que la key sea valida. Generar una nueva si es necesario. Actualizar en Vercel y hacer redeploy.

### Error 1010 de Cloudflare (403 Forbidden)

**Causa:** El User-Agent de Python (`Python-urllib/3.x`) esta bloqueado por Cloudflare.
**Solucion:** El codigo ya incluye `User-Agent: leiten-webhook/1.0` en todas las requests. Si se reescribe el codigo, asegurarse de incluir este header.

### Error 401 de Resend

**Causa:** API key incorrecta o inexistente.
**Solucion:** Ir a resend.com, copiar la API key correcta, pegarla en Vercel como `RESEND_API_KEY`, y hacer redeploy.

### Email llega pero sin datos del PR

**Causa:** El `GITHUB_TOKEN` no tiene permisos para leer el repositorio.
**Solucion:** Generar un nuevo token fine-grained con acceso de lectura a la organizacion grupoLeiten.

### Vercel no toma los cambios de env vars

**Causa:** Vercel no redeploya automaticamente cuando se cambian variables de entorno.
**Solucion:** Forzar un redeploy manual desde el dashboard de Vercel o pushear un commit.

### El email llega a spam

**Solucion:** Esto pasa porque se envia desde `onboarding@resend.dev` (dominio de Resend, no propio). Para mejorar la entregabilidad, verificar un dominio propio en Resend (resend.com > Domains > Add Domain) y configurar los registros DNS (SPF, DKIM, DMARC).

---

## Archivos del proyecto

```
leiten-webhook/
  api/
    index.py          <- Handler principal del webhook
  docs/
    CONFIGURACION.md  <- Este documento
  vercel.json         <- Configuracion de rutas de Vercel
  README.md           <- Documentacion del repo
```

---

## Mejoras futuras sugeridas

1. **Dominio propio en Resend** - Verificar dominio para enviar desde una direccion @sinis.com.ar o @leiten.com en vez de onboarding@resend.dev
2. **Limpiar env vars viejas** - Borrar SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD si aun existen en Vercel
