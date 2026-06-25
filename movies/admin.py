from django.contrib import admin
from .models import Movie, Series, Season, Episode, Genre, Country, WatchProgress, MovieComment


@admin.register(Movie)
class MovieAdmin(admin.ModelAdmin):
    list_display   = ['title', 'release_year', 'is_premium', 'is_published', 'is_featured', 'views_count']
    list_filter    = ['is_premium', 'is_published', 'is_featured', 'genres']
    list_editable  = ['is_published', 'is_featured', 'is_premium']
    search_fields  = ['title']
    prepopulated_fields = {'slug': ('title',)}
    fieldsets = [
        (None, {'fields': ['title', 'slug', 'description', 'genres', 'countries',
                           'release_year', 'rating', 'quality', 'language',
                           'is_premium', 'is_published', 'is_featured', 'uploaded_by']}),
        ('Media', {'fields': ['thumbnail', 'video_file', 'video_url', 'trailer_url']}),
        ('Subtitles / Transcript',
         {'fields': ['subtitles'],
          'description': 'Paste SRT-format subtitles or a plain transcript here. '
                         'Leave blank to have AI generate a scene summary when a user requests it.'}),
    ]


@admin.register(Episode)
class EpisodeAdmin(admin.ModelAdmin):
    list_display   = ['__str__', 'season', 'is_published']
    list_editable  = ['is_published']
    search_fields  = ['title']
    fieldsets = [
        (None, {'fields': ['season', 'number', 'title', 'description', 'duration', 'is_published']}),
        ('Media', {'fields': ['thumbnail', 'video_file', 'video_url']}),
        ('Subtitles / Transcript',
         {'fields': ['subtitles'],
          'description': 'Paste SRT-format subtitles or a plain transcript here. '
                         'Leave blank to have AI generate a scene summary when a user requests it.'}),
    ]


@admin.register(Series)
class SeriesAdmin(admin.ModelAdmin):
    list_display        = ['title', 'is_premium', 'is_published']
    list_editable       = ['is_published', 'is_premium']
    prepopulated_fields = {'slug': ('title',)}


admin.site.register(Season)
admin.site.register(Genre)
admin.site.register(Country)
admin.site.register(WatchProgress)
admin.site.register(MovieComment)
