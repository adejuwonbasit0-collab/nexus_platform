import os
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import FileResponse, JsonResponse
from django.views.decorators.http import require_POST
from .models import Image, Category, Tag, ImageComment


def image_home(request):
    featured  = Image.objects.filter(is_published=True, is_featured=True)[:8]
    trending  = Image.objects.filter(is_published=True).order_by('-views_count')[:20]
    recent    = Image.objects.filter(is_published=True).order_by('-created_at')[:20]
    cats      = Category.objects.all()
    return render(request,'images/home.html',{'featured':featured,'trending':trending,'recent':recent,'cats':cats})


def image_browse(request):
    qs   = Image.objects.filter(is_published=True).select_related('category')
    q    = request.GET.get('q','')
    cat  = request.GET.get('cat','')
    tag  = request.GET.get('tag','')
    res  = request.GET.get('res','')
    sort = request.GET.get('sort','-created_at')
    if q:   qs = qs.filter(Q(title__icontains=q)|Q(description__icontains=q))
    if cat: qs = qs.filter(category__slug=cat)
    if tag: qs = qs.filter(tags__slug=tag)
    if res: qs = qs.filter(resolution=res)
    if sort in ('-downloads_count','-views_count','-created_at'): qs = qs.order_by(sort)
    cats = Category.objects.all()
    tags = Tag.objects.all()[:40]
    return render(request,'images/browse.html',{
        'images':qs,'cats':cats,'tags':tags,'q':q,'active_cat':cat,'active_tag':tag,
    })


def image_detail(request, slug):
    image = get_object_or_404(Image, slug=slug, is_published=True)
    sk = f'img_{image.pk}'
    if not request.session.get(sk):
        image.views_count += 1; image.save(update_fields=['views_count'])
        request.session[sk] = True
    related = Image.objects.filter(category=image.category, is_published=True).exclude(pk=image.pk)[:12]
    comments = image.comments.select_related('user')[:20]
    return render(request,'images/detail.html',{'image':image,'related':related,'comments':comments})


@login_required
def download_image(request, pk):
    image = get_object_or_404(Image, pk=pk, is_published=True)
    if image.is_premium and not request.user.is_premium:
        return redirect('/subscriptions/')
    image.downloads_count += 1; image.save(update_fields=['downloads_count'])
    from accounts.models import DownloadHistory
    DownloadHistory.objects.create(user=request.user,content_type='image',object_id=image.pk,
                                   file_url=image.image_file.url,ip_address=request.META.get('REMOTE_ADDR'))
    return FileResponse(open(image.image_file.path,'rb'),as_attachment=True,
                        filename=os.path.basename(image.image_file.name))


@require_POST
@login_required
def add_image_comment(request, pk):
    image = get_object_or_404(Image, pk=pk)
    text  = request.POST.get('text','').strip()
    if text:
        c = ImageComment.objects.create(user=request.user,image=image,text=text)
        return JsonResponse({'ok':True,'username':request.user.username,'text':c.text,'id':c.pk})
    return JsonResponse({'ok':False})
