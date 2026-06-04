import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nexus_platform.settings')
django.setup()

from django.test import Client

c = Client()
urls = [
    '/search/?q=Neon',
    '/movies/browse/',
    '/music/browse/',
    '/images/browse/',
    '/blog/browse/',
    '/content/browse/',
]
for u in urls:
    r = c.get(u, HTTP_HOST='localhost')
    print(u, r.status_code, len(r.content), [t.name for t in r.templates])
