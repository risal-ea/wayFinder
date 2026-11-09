from django.contrib import admin
from .models import BookingRecord, FlightTraveler

class FlightTravelerInline(admin.TabularInline):
    model = FlightTraveler
    extra = 0
    readonly_fields = ('eticket_number', 'created_at')

@admin.register(BookingRecord)
class BookingRecordAdmin(admin.ModelAdmin):
    list_display = ('id', 'provider_reference', 'item_type', 'status', 'total_amount', 'currency', 'approved_by_user', 'created_at')
    list_filter = ('status', 'item_type', 'provider', 'approved_by_user')
    search_fields = ('id', 'idempotency_key', 'provider_reference', 'trip__title')
    readonly_fields = ('id', 'idempotency_key', 'approval_token', 'created_at', 'updated_at')
    inlines = [FlightTravelerInline]

@admin.register(FlightTraveler)
class FlightTravelerAdmin(admin.ModelAdmin):
    list_display = ('first_name', 'last_name', 'traveler_type', 'booking', 'passport_number', 'eticket_number', 'created_at')
    search_fields = ('first_name', 'last_name', 'passport_number', 'eticket_number')
    list_filter = ('traveler_type', 'gender')
