from django.contrib import admin
from .models import (
    Artist, Album, Track, Genre, Playlist,
    MusicComment, TrackLike, TrendingSnapshot, PlatformBranding,
)


@admin.register(PlatformBranding)
class PlatformBrandingAdmin(admin.ModelAdmin):
    """
    Upload the platform logo that appears on the music player
    (like Audiomack / Boomplay branding).
    """
    list_display = ['show_on_player', 'updated_at']
    fieldsets = [
        ('Logo Files', {
            'description': (
                'Upload your platform logo. It will appear on:\n'
                '• The persistent music player bar\n'
                '• Track detail cover art overlay\n'
                '• Song of the Day section'
            ),
            'fields': ['logo', 'logo_dark', 'watermark'],
        }),
        ('Display Settings', {'fields': ['show_on_player']}),
    ]

    def has_add_permission(self, request):
        return not PlatformBranding.objects.exists()


@admin.register(Genre)
class GenreAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'icon']
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Artist)
class ArtistAdmin(admin.ModelAdmin):
    list_display  = ['name', 'country', 'is_verified', 'monthly_listeners', 'trend_score']
    list_editable = ['is_verified']
    search_fields = ['name', 'country']
    prepopulated_fields = {'slug': ('name',)}
    fieldsets = [
        ('Profile',  {'fields': ['name', 'slug', 'photo', 'bio', 'country']}),
        ('Social',   {'fields': ['website', 'social_instagram', 'social_twitter', 'social_youtube']}),
        ('Settings', {'fields': ['is_verified']}),
    ]


@admin.register(Album)
class AlbumAdmin(admin.ModelAdmin):
    list_display  = ['title', 'artist', 'album_type', 'release_year', 'label', 'is_published', 'plays_count']
    list_filter   = ['album_type', 'release_year', 'is_published']
    list_editable = ['is_published']
    search_fields = ['title', 'artist__name']
    prepopulated_fields = {'slug': ('title',)}


@admin.register(Track)
class TrackAdmin(admin.ModelAdmin):
    list_display  = [
        'title', 'artist', 'genre', 'release_year',
        'is_premium', 'is_published', 'is_song_of_day', 'plays_count', 'trend_score',
    ]
    list_filter   = ['is_premium', 'is_published', 'is_song_of_day', 'genre', 'release_year']
    list_editable = ['is_published', 'is_premium', 'is_song_of_day']
    search_fields = ['title', 'artist__name', 'album__title', 'produced_by']
    filter_horizontal = ['featured_artists']
    prepopulated_fields = {'slug': ('title',)}
    readonly_fields = ['plays_count', 'downloads_count', 'likes_count', 'trend_score']
    fieldsets = [
        ('Basic Info',   {'fields': ['title', 'slug', 'artist', 'featured_artists', 'album', 'genre']}),
        ('Files',        {'fields': ['audio_file', 'cover_image']}),
        ('Release Info', {'fields': ['release_year', 'duration', 'country', 'label', 'isrc']}),
        ('Credits',      {'fields': ['produced_by', 'written_by', 'recorded_at', 'mixed_by', 'mastered_by']}),
        ('Lyrics',       {'fields': ['lyrics'], 'classes': ['collapse']}),
        ('Flags',        {'fields': ['is_published', 'is_premium', 'is_featured', 'is_song_of_day', 'uploaded_by']}),
        ('Stats (read-only)', {'fields': ['plays_count', 'downloads_count', 'likes_count', 'trend_score']}),
    ]


@admin.register(TrendingSnapshot)
class TrendingSnapshotAdmin(admin.ModelAdmin):
    list_display = ['content_type', 'object_id', 'rank', 'score', 'snapshot_date']
    list_filter  = ['content_type', 'snapshot_date']
    readonly_fields = ['snapshot_date']


admin.site.register(Playlist)
admin.site.register(MusicComment)
admin.site.register(TrackLike)
