from django.contrib import admin
from .models import Content, Series, Season, Episode, Category, Tag, Comment, Like, Download, View

admin.site.register(Category)
admin.site.register(Tag)
admin.site.register(Comment)

@admin.register(Content)
class ContentAdmin(admin.ModelAdmin):
    list_display = ['title', 'content_type', 'tier', 'status', 'creator', 'views', 'created_at']
    list_filter = ['content_type', 'tier', 'status']
    search_fields = ['title', 'description']
    actions = ['approve_content', 'reject_content']
    
    def approve_content(self, request, queryset): queryset.update(status='approved')
    def reject_content(self, request, queryset): queryset.update(status='rejected')

@admin.register(Series)
class SeriesAdmin(admin.ModelAdmin):
    list_display = ['title', 'tier', 'status', 'creator']

admin.site.register(Season)
admin.site.register(Episode)
