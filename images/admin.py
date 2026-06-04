from django.contrib import admin
from .models import Image, Category, Tag, ImageComment

@admin.register(Image)
class ImageAdmin(admin.ModelAdmin):
    list_display  = ['title','category','resolution','is_premium','is_published','downloads_count']
    list_filter   = ['is_premium','is_published','resolution','category']
    list_editable = ['is_published','is_premium']
    search_fields = ['title']
    prepopulated_fields = {'slug': ('title',)}

admin.site.register(Category)
admin.site.register(Tag)
admin.site.register(ImageComment)
