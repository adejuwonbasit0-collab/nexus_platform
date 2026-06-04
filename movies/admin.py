from django.contrib import admin
from .models import Movie, Series, Season, Episode, Genre, Country, WatchProgress, MovieComment

@admin.register(Movie)
class MovieAdmin(admin.ModelAdmin):
    list_display  = ['title','release_year','is_premium','is_published','is_featured','views_count']
    list_filter   = ['is_premium','is_published','is_featured','genres']
    list_editable = ['is_published','is_featured','is_premium']
    search_fields = ['title']
    prepopulated_fields = {'slug': ('title',)}

@admin.register(Series)
class SeriesAdmin(admin.ModelAdmin):
    list_display = ['title','is_premium','is_published']
    list_editable= ['is_published','is_premium']
    prepopulated_fields = {'slug': ('title',)}

admin.site.register(Season)
admin.site.register(Episode)
admin.site.register(Genre)
admin.site.register(Country)
admin.site.register(WatchProgress)
admin.site.register(MovieComment)
