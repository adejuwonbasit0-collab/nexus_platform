# NEXUS — AI-Powered Media & Content Platform

> A full-stack, production-ready media platform combining AI image generation, video/music streaming, blog publishing, creator monetization, and an admin control centre — built with Django + Vanilla JS.

---

## 🚀 Quick Start (Local)

### 1. Clone / extract the project
```bash
cd nexus_platform
```

### 2. Create a virtual environment
```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
```

### 3. Install dependencies
```bash
pip install django djangorestframework pillow python-decouple django-cors-headers PyJWT
```

### 4. Apply migrations
```bash
python manage.py migrate
```

### 5. Seed demo data
```bash
python seed_data.py
```

### 6. (Optional) Set API keys in environment
```bash
export OPENAI_API_KEY="sk-..."          # For real DALL-E image generation
export ANTHROPIC_API_KEY="sk-ant-..."   # For real Claude AI assistant
```
Without keys the platform runs in **demo mode** — AI chat returns smart fallbacks and image generation returns placeholder images from Picsum.

### 7. Run the development server
```bash
python manage.py runserver
```

Open **http://127.0.0.1:8000**

---

## 🔑 Default Credentials

| Role    | Username        | Password     | URL                            |
|---------|-----------------|--------------|--------------------------------|
| Admin   | `admin`         | `admin123`   | `/admin-panel/`                |
| Creator | `alice_creates` | `creator123` | `/creator/`                    |
| Creator | `bob_films`     | `creator123` | `/creator/`                    |
| Creator | `chloe_beats`   | `creator123` | `/creator/`                    |

> **Django Admin** (raw DB): `/django-admin/` with admin credentials.

---

## 🗺 Platform URLs

| URL | Description |
|-----|-------------|
| `/` | Homepage — featured, recent content |
| `/browse/` | Universal search & filter |
| `/images/` | Image gallery |
| `/movies/` | Movies & series |
| `/music/` | Music library with inline player |
| `/blog/` | Blog posts |
| `/ai/studio/` | AI image generator |
| `/content/<pk>/` | Content detail + streaming/player |
| `/series/<pk>/` | Series page with episode list |
| `/watch/<pk>/` | Episode video player |
| `/auth/login/` | Sign in |
| `/auth/register/` | Register (user or creator) |
| `/creator/` | Creator dashboard |
| `/creator/upload/` | Creator content upload |
| `/admin-panel/` | Admin dashboard |
| `/admin-panel/content/` | Content management & moderation |
| `/admin-panel/content/upload/` | Admin content upload |
| `/admin-panel/series/` | Series / season / episode manager |
| `/admin-panel/users/` | User management |
| `/admin-panel/analytics/` | Revenue & view analytics |
| `/admin-panel/monetization/` | Commission rate settings |
| `/admin-panel/settings/` | Site-wide editable settings |

---

## 🏗 Architecture

```
nexus_platform/          ← Django project config (settings, urls, wsgi)
accounts/                ← Custom User model (admin / creator / user roles)
content/                 ← Core content models + views + URLs
  models.py              → Content, Series, Season, Episode, Comment, Like, Download, View
  views.py               → Browse, Detail, Stream, Download, Like, Comment
core/                    ← Admin panel, Creator dashboard, Site settings, AI logs
  views.py               → admin_dashboard, admin_content, admin_users, creator_dashboard …
  context_processors.py  → Injects site settings into every template
  models.py              → SiteSettings, AILog, AIGeneratedImage
ai_tools/                ← AI image generation, AI chat assistant, content moderation
  views.py               → generate_image, ai_assistant, moderate_content
monetization/            ← Earnings, commission rates, payments
  models.py              → CommissionSettings, Earning, Payment
templates/               ← All HTML templates (Django templating)
  base.html              → Global layout, nav, footer, AI chat widget
  home.html              → Homepage
  auth/                  → Login, Register
  content/               → Detail, Browse, Gallery, Movies, Music, Blogs, Watch
  admin_panel/           → Full admin dashboard suite
  creator/               → Creator dashboard & upload
  ai/                    → AI Studio
static/                  ← CSS, JS, images
media/                   ← Uploaded content files
seed_data.py             ← One-command demo data loader
```

---

## 🗄 Database Schema (key tables)

| Table | Key Fields |
|-------|-----------|
| `accounts_user` | username, email, role (admin/creator/user), total_earnings, is_verified |
| `content_content` | title, content_type, tier, status, file, thumbnail, views, likes_count, downloads_count, ai_score, ai_flags |
| `content_series` | title, creator, tier, status |
| `content_season` | series, number |
| `content_episode` | season, number, title, file, views |
| `content_comment` | user, content/series, text, is_flagged |
| `content_like` | user + content (unique) |
| `content_download` | user, content, ip_address |
| `content_view` | content/episode, user, ip_address |
| `core_sitesettings` | key, value, group |
| `core_ailog` | action, input_data, output_data, model_used, tokens_used |
| `core_aigeneratedimage` | user, prompt, image_url, saved_to_platform |
| `monetization_commissionsettings` | content_type, action, amount |
| `monetization_earning` | creator, content, amount, reason |
| `monetization_payment` | user, content, amount, status |

---

## ⚙️ Feature Highlights

### 🎬 Video Streaming
HTTP Range-request streaming — supports seeking, buffering, and chunked delivery for any video file. Works for both standalone videos and series episodes.

### 🤖 AI Image Generation
- Calls **OpenAI DALL-E 3** when `OPENAI_API_KEY` is set
- Falls back to demo Picsum images without a key
- Generated images are stored in `core_aigeneratedimage` and shown in the user's gallery

### 💬 AI Assistant Chat Widget
- Persistent floating chat bubble on every page
- Calls **Anthropic Claude** when `ANTHROPIC_API_KEY` is set
- Smart fallback replies in demo mode
- Conversation history maintained per session in the browser

### 💰 Monetization
- Admin sets per-action commission rates (view / download, per content type)
- Every download and view auto-creates an `Earning` record for the creator
- Earnings aggregated on creator dashboard and admin analytics

### 🛡 AI Moderation
- Keyword-based auto-moderation on submission (plug in a real ML model)
- Admin can override any AI decision (approve / reject) in the admin panel

### 🌐 Fully Editable Site Settings
- Platform name, tagline, social links, footer URLs, AI prompts
- All editable through `/admin-panel/settings/` — no code changes needed

---

## 🔧 Production Checklist

- [ ] Set `DEBUG = False` and `ALLOWED_HOSTS` in settings
- [ ] Switch `DATABASES` to PostgreSQL or MySQL
- [ ] Configure `STATIC_ROOT` and run `collectstatic`
- [ ] Serve media files via Nginx or S3/CDN
- [ ] Set `SECRET_KEY` from environment variable
- [ ] Add real API keys for OpenAI / Anthropic
- [ ] Configure email backend for notifications
- [ ] Add Celery + Redis for async tasks (AI generation, large uploads)
- [ ] Enable HTTPS / SSL via Let's Encrypt


git add .
git commit -m "add"
git push origin main