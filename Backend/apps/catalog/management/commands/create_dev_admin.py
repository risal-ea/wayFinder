from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()

class Command(BaseCommand):
    help = "Creates default dev admin user (admin / admin123)"

    def handle(self, *args, **options):
        if not User.objects.filter(username="admin").exists():
            User.objects.create_superuser("admin", "admin@wayfinder.ai", "admin123")
            self.stdout.write(self.style.SUCCESS("Superuser 'admin' created successfully (password: admin123)."))
        else:
            self.stdout.write(self.style.WARNING("Superuser 'admin' already exists."))

