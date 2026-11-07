from django.contrib import admin
from .models import BookingRecord

@admin.register(BookingRecord)
class BookingRecordAdmin(admin.ModelAdmin):
    list_display = ('id', 'trip', 'item_type', 'status', 'total_amount', 'currency', 'provider_reference', 'approved_by_user', 'created_at')
    list_filter = ('status', 'item_type', 'provider', 'approved_by_user')
    search_fields = ('id', 'idempotency_key', 'provider_reference', 'trip__title')
    readonly_fields = ('id', 'idempotency_key', 'approval_token', 'created_at', 'updated_at')

