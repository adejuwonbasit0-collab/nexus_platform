from django.contrib import admin
from .models import Post, Comment, PostLike, Category, Tag, AIBlogUsage

@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display  = ['title','author','category','status','is_featured','is_ai_generated','views_count','created_at']
    list_filter   = ['status','is_featured','is_ai_generated','category']
    list_editable = ['status','is_featured']
    search_fields = ['title','author__username']
    prepopulated_fields = {'slug': ('title',)}

admin.site.register(Comment)
admin.site.register(PostLike)
admin.site.register(Category)
admin.site.register(Tag)
admin.site.register(AIBlogUsage)
