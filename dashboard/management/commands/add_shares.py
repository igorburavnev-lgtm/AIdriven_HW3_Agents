from django.conf import settings
from django.core.management.base import BaseCommand

from dashboard.models import Share


class Command(BaseCommand):
    help = "Add shares to DB"

    def handle(self, *args, **options):
        # Imported lazily: the Tinkoff SDK is only needed by this command.
        from tinkoff.invest import Client

        with Client(settings.TINKOFF_TOKEN) as client:
            instruments = client.instruments.shares()

        created = 0
        for share in instruments.instruments:
            # ``figi`` is the natural key; other attributes are initial values only,
            # otherwise a renamed instrument creates a duplicate row and violates
            # the UNIQUE constraint on figi.
            _, was_created = Share.objects.get_or_create(
                figi=share.figi,
                defaults={
                    "name": share.name,
                    "isin": share.isin,
                    "ticker": share.ticker,
                    "currency": share.currency,
                    "uid": share.uid,
                },
            )
            created += int(was_created)

        self.stdout.write(self.style.SUCCESS(f"Added {created} shares"))
