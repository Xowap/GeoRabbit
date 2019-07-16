from django.core.management import BaseCommand

from ...models import Tile


class Command(BaseCommand):
    """
    Deletes all tile statuses to start a scan again.
    """

    def handle(self, *args, **options):
        print(Tile.objects.exclude(depth=0).delete())
        Tile.objects.update(status=Tile.TO_PROBE)
