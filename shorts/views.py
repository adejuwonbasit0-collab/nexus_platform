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


PAGE_SIZE = 12  # shorts served per batch, both on first load and on infinite-scroll


def _feed_seed(request, fresh=False):
    """A shuffle seed that's stable for the length of one Shorts session (so
    paging further into the feed keeps building on the SAME shuffled order
    instead of re-shuffling under the user's feet on every request — that
    used to be reseeded every single second, which is why only a fixed 60
    items ever surfaced and pagination wasn't possible), but generates a
    fresh shuffle each time the feed is opened from scratch."""
    if not request.session.session_key:
        request.session.save()
    if fresh or not request.session.get('shorts_feed_seed'):
        import random
        request.session['shorts_feed_seed'] = random.randint(1, 2_000_000_000)
    return request.session['shorts_feed_seed']


def _full_feed_order(seed):
    """The full shuffled order across EVERY published short (not just the
    most recent 60), so the feed keeps offering new content instead of
    dead-ending once the first batch of items has been scrolled through."""
    from django.db.models import Count
    qs = (Short.objects.filter(is_published=True)
          .annotate(comment_count=Count('comments')))
    return _ordered_feed(qs, seed=seed)


def _liked_ids_for(request, shorts):
    if request.user.is_authenticated:
        return set(ShortLike.objects.filter(user=request.user, short__in=shorts).values_list('short_id', flat=True))
    return set()


def shorts_feed(request):
    seed = _feed_seed(request, fresh=True)
    ordered = _full_feed_order(seed)
    feed = ordered[:PAGE_SIZE]
    return render(request, 'shorts/feed.html', {
        'shorts': feed,
        'liked_ids': _liked_ids_for(request, feed),
        'has_more': len(ordered) > 0,  # even a single short can loop forever
    })


def shorts_more(request):
    """Infinite-scroll batch: returns the next PAGE_SIZE shorts as a
    rendered HTML fragment. Once every short has been shown, it wraps back
    to the start of the same shuffled order rather than dead-ending — same
    endless-scroll behavior as TikTok/Reels."""
    seed = _feed_seed(request)
    ordered = _full_feed_order(seed)
    if not ordered:
        return JsonResponse({'ok': True, 'html': '', 'has_more': False})
    try:
        offset = int(request.GET.get('offset', 0))
    except ValueError:
        offset = 0
    start = offset % len(ordered)
    batch = (ordered[start:] + ordered[:start])[:PAGE_SIZE]
    from django.template.loader import render_to_string
    html = render_to_string('shorts/_slides.html', {
        'shorts': batch,
        'liked_ids': _liked_ids_for(request, batch),
    }, request=request)
    return JsonResponse({'ok': True, 'html': html, 'has_more': True})


@require_POST
def track_view(request, pk):
    from django.db.models import F
    Short.objects.filter(pk=pk).update(view_count=F('view_count') + 1)
    return JsonResponse({'ok': True})


@require_POST
def flag_broken(request, pk):
    """Called by the player when a short fails to actually play (deleted,
    made private, or blocked by its owner after import). Unpublishes it
    so the feed stops serving it to anyone going forward — a client-side
    skip alone only fixes it for the one viewer who happened to hit it."""
    Short.objects.filter(pk=pk).update(is_published=False)
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
