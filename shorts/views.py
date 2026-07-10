from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from .models import Short, ShortLike, ShortComment


def _ordered_feed(queryset, seed=None):
    """Builds the scroll order: standalone shorts stay in a shuffled order
    (seeded so it differs per user/session and changes on each fresh visit,
    instead of everyone seeing the exact same fixed list forever), but if a
    short belongs to a Series, all of that series' episodes are pulled in
    immediately after it in episode order — so a movie broken into
    episodes plays back-to-back like consecutive shorts instead of being
    scattered through the feed."""
    import random
    items = list(queryset.select_related('series'))
    seen_series = set()
    groups = []
    for item in items:
        if item.series_id:
            if item.series_id in seen_series:
                continue
            seen_series.add(item.series_id)
            episodes = sorted(
                [i for i in items if i.series_id == item.series_id],
                key=lambda x: (x.episode_number or 0)
            )
            groups.append(episodes)
        else:
            groups.append([item])

    rng = random.Random(seed) if seed is not None else random.Random()
    rng.shuffle(groups)

    ordered = []
    for g in groups:
        ordered.extend(g)
    return ordered


def shorts_feed(request):
    from django.db.models import Count
    # A fresh shuffle seed each time this page loads (so refreshing or
    # logging back in gives a different order, not the exact same list
    # forever), but unique per user so two people don't see identical
    # orderings at the same moment.
    import time
    if request.user.is_authenticated:
        identity = f'user-{request.user.pk}'
    else:
        if not request.session.session_key:
            request.session.save()
        identity = f'anon-{request.session.session_key}'
    seed = f'{identity}-{int(time.time() // 1)}'

    qs = (Short.objects.filter(is_published=True)
          .annotate(comment_count=Count('comments'))
          .order_by('-created_at')[:60])
    feed = _ordered_feed(qs, seed=seed)
    liked_ids = set()
    if request.user.is_authenticated:
        liked_ids = set(ShortLike.objects.filter(user=request.user, short__in=feed).values_list('short_id', flat=True))
    return render(request, 'shorts/feed.html', {
        'shorts': feed,
        'liked_ids': liked_ids,
    })


@require_POST
def track_view(request, pk):
    from django.db.models import F
    Short.objects.filter(pk=pk).update(view_count=F('view_count') + 1)
    return JsonResponse({'ok': True})


@login_required
@require_POST
def toggle_like(request, pk):
    short = get_object_or_404(Short, pk=pk)
    like, created = ShortLike.objects.get_or_create(short=short, user=request.user)
    if not created:
        like.delete()
        short.like_count = max(0, short.like_count - 1)
        liked = False
    else:
        short.like_count += 1
        liked = True
    short.save(update_fields=['like_count'])
    return JsonResponse({'ok': True, 'liked': liked, 'like_count': short.like_count})


def list_comments(request, pk):
    short = get_object_or_404(Short, pk=pk)
    comments = short.comments.select_related('user').all()[:100]
    return JsonResponse({
        'ok': True,
        'comments': [
            {
                'username': c.user.username,
                'avatar_url': c.user.avatar.url if getattr(c.user, 'avatar', None) else '',
                'text': c.text,
            }
            for c in comments
        ],
    })


@login_required
@require_POST
def add_comment(request, pk):
    short = get_object_or_404(Short, pk=pk)
    text = (request.POST.get('text') or '').strip()[:500]
    if not text:
        return JsonResponse({'ok': False, 'error': 'Empty comment'}, status=400)
    ShortComment.objects.create(short=short, user=request.user, text=text)
    return JsonResponse({'ok': True, 'username': request.user.username, 'text': text})
