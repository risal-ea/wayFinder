from django.contrib import admin
from .models import Trip, ItineraryDay, TripShortlist

class ItineraryDayInline(admin.TabularInline):
    model = ItineraryDay
    extra = 0

class TripShortlistInline(admin.TabularInline):
    model = TripShortlist
    extra = 0

@admin.register(Trip)
class TripAdmin(admin.ModelAdmin):
    list_display = ('title', 'origin_city', 'destination_city', 'start_date', 'end_date', 'budget_ceiling', 'currency', 'status')
    search_fields = ('title', 'origin_city', 'destination_city')
    list_filter = ('status', 'currency', 'start_date')
    inlines = [ItineraryDayInline, TripShortlistInline]

@admin.register(ItineraryDay)
class ItineraryDayAdmin(admin.ModelAdmin):
    list_display = ('trip', 'day_number', 'date', 'theme', 'day_cost_estimate')
    list_filter = ('trip__destination_city',)
    search_fields = ('theme', 'trip__title')

@admin.register(TripShortlist)
class TripShortlistAdmin(admin.ModelAdmin):
    list_display = ('trip', 'item_type', 'is_selected_for_booking', 'created_at')
    list_filter = ('item_type', 'is_selected_for_booking')

