from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import JsonResponse, FileResponse, Http404
from django.db.models import Q
from django.core.paginator import Paginator
import os

from .models import Image, ImageComment, ImageLike, Category as ImageCategory


def image_home(request):
    all_imgs = Image.objects.filter(is_published=True).order_by('-created_at')
    featured = list(all_imgs.filter(is_featured=True)[:8])
    recent   = list(all_imgs[:24])
    cats     = ImageCategory.objects.all()
    return render(request, 'images/home.html', {
        'featured': featured, 'recent': recent, 'cats': cats,
    })


def image_browse(request):
    qs = Image.objects.filter(is_published=True).order_by('-created_at')
    q    = request.GET.get('q', '')
    cat  = request.GET.get('cat', '')
    res  = request.GET.get('resolution', '')
    sort = request.GET.get('sort', '-created_at')
    if sort not in ['-created_at', '-views_count', '-downloads_count', '-likes_count']:
        sort = '-created_at'
    if q:   qs = qs.filter(Q(title__icontains=q) | Q(description__icontains=q))
    if cat: qs = qs.filter(category__slug=cat)
    if res: qs = qs.filter(resolution=res)
    qs = qs.order_by(sort)
    page = Paginator(qs, 24).get_page(request.GET.get('page', 1))
    categories = ImageCategory.objects.all()
    return render(request, 'images/browse.html', {
        'images': page, 'q': q, 'active_cat': cat,
        'resolution': res, 'sort': sort, 'cats': categories,
    })


def image_detail(request, slug):
    image = get_object_or_404(Image, slug=slug, is_published=True)
    # Increment view count
    Image.objects.filter(pk=image.pk).update(views_count=image.views_count + 1)
    image.refresh_from_db()
    related  = Image.objects.filter(is_published=True).exclude(pk=image.pk)
    if image.category:
        related = related.filter(category=image.category)
    related = related.order_by('-created_at')[:8]
    comments = image.comments.select_related('user').order_by('-created_at')[:30]
    user_liked = False
    if request.user.is_authenticated:
        user_liked = ImageLike.objects.filter(user=request.user, image=image).exists()
    return render(request, 'images/detail.html', {
        'image': image, 'related': related, 'comments': comments,
        'user_liked': user_liked,
    })


@login_required
def download_image(request, pk):
    image = get_object_or_404(Image, pk=pk, is_published=True)
    if image.is_premium:
        try:
            from monetization.models import UserSubscription
            if not UserSubscription.objects.filter(user=request.user, status='active').exists():
                from django.http import HttpResponseForbidden
                return HttpResponseForbidden('Premium subscription required')
        except Exception:
            pass
    f = image.image_file or image.thumbnail
    if not f or not os.path.exists(f.path):
        raise Http404
    Image.objects.filter(pk=pk).update(downloads_count=image.downloads_count + 1)
    return FileResponse(open(f.path, 'rb'), as_attachment=True,
                        filename=f'{image.title}.jpg')


@require_POST
def toggle_like(request, pk):
    if not request.user.is_authenticated:
        return JsonResponse({"error":"login_required","count":0,"liked":False},status=401)
    image = get_object_or_404(Image, pk=pk)
    like, created = ImageLike.objects.get_or_create(user=request.user, image=image)
    if not created:
        like.delete()
        Image.objects.filter(pk=pk).update(likes_count=max(0, image.likes_count - 1))
        liked = False
    else:
        Image.objects.filter(pk=pk).update(likes_count=image.likes_count + 1)
        liked = True
    image.refresh_from_db()
    return JsonResponse({'liked': liked, 'count': image.likes_count})


@require_POST
def add_image_comment(request, pk):
    if not request.user.is_authenticated:
        return JsonResponse({"ok":False,"error":"login_required"},status=401)
    image = get_object_or_404(Image, pk=pk)
    text  = request.POST.get('text', '').strip()
    if not text:
        return JsonResponse({'ok': False, 'error': 'Empty comment'})
    comment = ImageComment.objects.create(user=request.user, image=image, text=text)
    return JsonResponse({
        'ok': True, 'username': request.user.username,
        'text': comment.text, 'id': comment.pk,
    })