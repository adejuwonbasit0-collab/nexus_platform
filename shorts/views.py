from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from .models import Short, ShortLike


def _ordered_feed(queryset):
    """Builds the scroll order: standalone shorts stay in normal recency
    order, but if a short belongs to a Series, all of that series'
    episodes are pulled in immediately after it in episode order — so a
    movie broken into episodes plays back-to-back like consecutive shorts
    instead of being scattered through the feed."""
    items = list(queryset.select_related('series'))
    seen_series = set()
    ordered = []
    for item in items:
        if item.series_id:
            if item.series_id in seen_series:
                continue
            seen_series.add(item.series_id)
            episodes = sorted(
                [i for i in items if i.series_id == item.series_id],
                key=lambda x: (x.episode_number or 0)
            )
            ordered.extend(episodes)
        else:
            ordered.append(item)
    return ordered


def shorts_feed(request):
    qs = Short.objects.filter(is_published=True).order_by('-created_at')[:60]
    feed = _ordered_feed(qs)
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
