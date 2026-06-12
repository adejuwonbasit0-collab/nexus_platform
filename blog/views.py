import json
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from .models import Post, Comment, PostLike, Category, Tag, AIBlogUsage


def blog_home(request):
    featured = Post.objects.filter(status='published', is_featured=True).select_related('author','category')[:4]
    recent   = Post.objects.filter(status='published').select_related('author','category').order_by('-created_at')[:12]
    trending = Post.objects.filter(status='published').order_by('-views_count')[:6]
    cats     = Category.objects.all()
    tags     = Tag.objects.all()[:30]
    return render(request, 'blog/home.html', {
        'featured': featured, 'recent': recent, 'trending': trending,
        'cats': cats, 'tags': tags,
    })


def blog_browse(request):
    qs   = Post.objects.filter(status='published').select_related('author','category')
    q    = request.GET.get('q','')
    cat  = request.GET.get('cat','')
    tag  = request.GET.get('tag','')
    sort = request.GET.get('sort','-created_at')
    if q:   qs = qs.filter(Q(title__icontains=q)|Q(content__icontains=q)|Q(excerpt__icontains=q))
    if cat: qs = qs.filter(category__slug=cat)
    if tag: qs = qs.filter(tags__slug=tag)
    if sort in ('-views_count','-likes_count','-created_at'): qs = qs.order_by(sort)
    cats = Category.objects.all()
    tags = Tag.objects.all()[:40]
    return render(request, 'blog/browse.html', {
        'posts': qs, 'cats': cats, 'tags': tags, 'q': q,
        'active_cat': cat, 'active_tag': tag,
    })


def post_detail(request, slug):
    post = get_object_or_404(Post, slug=slug, status='published')
    sk   = f'blog_{post.pk}'
    if not request.session.get(sk):
        post.views_count += 1; post.save(update_fields=['views_count'])
        request.session[sk] = True
    comments  = post.comments.filter(parent=None).select_related('user').prefetch_related('replies__user')[:30]
    related   = Post.objects.filter(category=post.category, status='published').exclude(pk=post.pk)[:4]
    user_liked = PostLike.objects.filter(user=request.user, post=post).exists() if request.user.is_authenticated else False
    return render(request, 'blog/detail.html', {
        'post': post, 'comments': comments, 'related': related, 'user_liked': user_liked,
    })


@require_POST
def toggle_like(request, pk):
    if not request.user.is_authenticated:
        return JsonResponse({"error":"login_required","count":0,"liked":False},status=401)
    post = get_object_or_404(Post, pk=pk)
    like, created = PostLike.objects.get_or_create(user=request.user, post=post)
    if not created:
        like.delete(); post.likes_count = max(0, post.likes_count - 1); liked = False
    else:
        post.likes_count += 1; liked = True
    post.save(update_fields=['likes_count'])
    return JsonResponse({'ok': True, 'liked': liked, 'likes_count': post.likes_count, 'count': post.likes_count})


@require_POST
def add_comment(request, pk):
    if not request.user.is_authenticated:
        return JsonResponse({"ok":False,"error":"login_required"},status=401)
    post      = get_object_or_404(Post, pk=pk)
    text      = request.POST.get('text','').strip()
    parent_id = request.POST.get('parent_id')
    if not text:
        return JsonResponse({'ok': False})
    parent = Comment.objects.filter(pk=parent_id).first() if parent_id else None
    c = Comment.objects.create(user=request.user, post=post, text=text, parent=parent)
    return JsonResponse({'ok': True, 'username': request.user.username, 'text': c.text, 'id': c.pk})


# ── AI Blog Generator ─────────────────────────────────────────────────────────
AI_MONTHLY_LIMIT = 10

@login_required
def ai_blog_generator(request):
    if not request.user.has_ai_access:
        return render(request, 'blog/ai_locked.html', {})

    now   = timezone.now()
    month = now.strftime('%Y-%m')
    used  = AIBlogUsage.objects.filter(user=request.user, month=month).count()
    remaining = max(0, AI_MONTHLY_LIMIT - used)

    if request.method == 'POST':
        topic = request.POST.get('topic','').strip()
        if not topic:
            return render(request, 'blog/ai_generator.html', {'error': 'Topic is required.', 'remaining': remaining})
        if remaining <= 0:
            return render(request, 'blog/ai_generator.html', {'error': f'Monthly AI limit ({AI_MONTHLY_LIMIT}) reached.', 'remaining': 0})

        from core.utils import get_ai_key
        api_key = get_ai_key('anthropic')
        if not api_key:
            return render(request, 'blog/ai_generator.html', {'error': 'AI not configured. Contact admin.', 'remaining': remaining})

        import urllib.request, urllib.error
        try:
            payload = json.dumps({
                'model': 'claude-sonnet-4-20250514',
                'max_tokens': 2000,
                'messages': [{
                    'role': 'user',
                    'content': (
                        f'Write a detailed, engaging blog post about: "{topic}". '
                        'Format: Return JSON only with keys: title, content (HTML), excerpt (plain text, 200 chars), tags (array of 5 strings). '
                        'Content should be 600-900 words with proper headings.'
                    )
                }]
            }).encode()
            req = urllib.request.Request(
                'https://api.anthropic.com/v1/messages',
                data=payload,
                headers={
                    'Content-Type': 'application/json',
                    'x-api-key': api_key,
                    'anthropic-version': '2023-06-01',
                }
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read())
            raw = data['content'][0]['text'].strip()
            if raw.startswith('```'): raw = raw.split('```')[1].lstrip('json').strip()
            result = json.loads(raw)

            # Build tags
            tag_objs = []
            for t in result.get('tags', [])[:5]:
                tag, _ = Tag.objects.get_or_create(name=t.strip()[:80])
                tag_objs.append(tag)

            # Determine category
            cat = Category.objects.first()

            post = Post.objects.create(
                title=result.get('title', topic),
                author=request.user,
                content=result.get('content',''),
                excerpt=result.get('excerpt','')[:400],
                category=cat,
                status='draft',
                is_ai_generated=True,
            )
            post.tags.set(tag_objs)
            AIBlogUsage.objects.create(user=request.user, post=post, topic=topic, month=month)

            return redirect('blog_edit', pk=post.pk)

        except Exception as e:
            return render(request, 'blog/ai_generator.html', {
                'error': f'Generation failed: {str(e)[:200]}', 'remaining': remaining,
            })

    return render(request, 'blog/ai_generator.html', {'remaining': remaining})


@login_required
def blog_edit(request, pk):
    post = get_object_or_404(Post, pk=pk)
    # Only the author can edit
    if post.author != request.user:
        from django.http import Http404
        raise Http404
    cats = Category.objects.all()
    tags = Tag.objects.all()
    if request.method == 'POST':
        post.title    = request.POST.get('title', post.title)
        post.content  = request.POST.get('content', post.content)
        post.excerpt  = request.POST.get('excerpt', post.excerpt)
        post.status   = request.POST.get('status', 'draft')
        cat_id        = request.POST.get('category')
        if cat_id: post.category = Category.objects.filter(pk=cat_id).first()
        if request.FILES.get('featured_img'):
            post.featured_img = request.FILES['featured_img']
        post.save()
        tag_str = request.POST.get('tags','')
        if tag_str:
            tag_objs = []
            for t in tag_str.split(','):
                t = t.strip()
                if t:
                    tag, _ = Tag.objects.get_or_create(name=t[:80])
                    tag_objs.append(tag)
            post.tags.set(tag_objs)
        from django.contrib import messages as dj_messages
        dj_messages.success(request, 'Post saved!')
        return redirect('post_detail', slug=post.slug)
    return render(request, 'blog/edit.html', {'post': post, 'cats': cats, 'tags': tags})


@login_required
def my_posts(request):
    posts = Post.objects.filter(author=request.user).order_by('-created_at')
    return render(request, 'blog/my_posts.html', {'posts': posts})