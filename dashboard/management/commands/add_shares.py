from django.conf import settings
from django.core.management.base import BaseCommand

from dashboard.models import Share


class Command(BaseCommand):
    help = "Add shares to DB"

    def handle(self, *args, **options):
        # Deferred import: only this command needs the Tinkoff SDK.
        from tinkoff.invest import Client

        with Client(settings.TINKOFF_TOKEN) as client:
            instruments = client.instruments.shares()

        created = 0
        for share in instruments.instruments:
            # ``figi`` is the natural key. Matching on every attribute (the
            # original behaviour) inserted a duplicate row whenever the broker
            # renamed an instrument, and the UNIQUE constraint on figi then
            # aborted the whole command.
            _, created_now = Share.objects.get_or_create(
                figi=share.figi,
                defaults={
                    "name": share.name,
                    "isin": share.isin,
                    "ticker": share.ticker,
                    "currency": share.currency,
                    "uid": share.uid,
                },
            )
            created += int(created_now)

        self.stdout.write(self.style.SUCCESS(f"Added {created} shares"))
