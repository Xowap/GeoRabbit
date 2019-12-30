from argparse import ArgumentParser
from multiprocessing.pool import ThreadPool
from threading import Lock
from typing import Text

import pendulum
from django.contrib.gis.geos import Point
from django.core.management import BaseCommand
from django.db.transaction import atomic
from tqdm import tqdm

from ...flickr import Flickr
from ...models import Area, Image, Tile


class Command(BaseCommand):
    """
    This is where the scanning of the whole Flickr database happens.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.insert_lock = Lock()

    def get_area(self, slug: Text) -> Area:
        """
        Transforms an area slug into a real area object. To be used by the
        arguments parser.
        """

        try:
            return Area.objects.get(name=slug)
        except Area.DoesNotExist:
            raise ValueError(f'No area with the name "{slug}" exist.')

    def add_arguments(self, parser: ArgumentParser):
        parser.add_argument(
            "-a", "--area", help="Name of the area to parse", type=self.get_area
        )

    def handle(self, area: Area, *args, **options):
        """
        Root function. It will simply scan one by one each level until the max
        depth is reached.
        """

        try:
            print(f'Getting content for "{area}"')

            for level in range(0, Tile.MAX_DEPTH + 1):
                self.handle_level(level, area)
        finally:
            f = Flickr.instance()
            f.stop_generating_keys()

    def handle_level(self, level: int, area: Area) -> None:
        """
        Handles a single level. It will evaluate all the tiles found in this
        level. If the tile intersects the scanned area then the tile is
        handled, otherwise the scanning is deferred to another scan which would
        require this tile to be scanned.

        Notes
        -----
        As the Flickr API is fairly slow and the amount of data to download is
        pretty big, the Flickr class allows for:

        - Rotating API keys in order to increase the rate limit a little bit
        - Being called from several threads but still maintain the rate limit
          on each key

        The parallelism happens at the tiles level: a thread pool will run each
        tile in a separate thread.
        """

        print("")
        print(f"--> Level {level}")

        tiles = Tile.objects.filter(depth=level, status=Tile.TO_PROBE).order_by(
            "y", "x"
        )

        def handle_tile(tile: Tile):
            if tile.polygon.intersects(area.area):
                self.handle_tile(tile)

        with ThreadPool(Flickr.instance().keys_count * 3) as pool:
            for _ in tqdm(
                pool.imap_unordered(handle_tile, tiles),
                total=tiles.count(),
                unit="tile",
                smoothing=0.01,
            ):
                pass

    def handle_tile(self, tile: Tile):
        """
        Basically, for each tile two things can happen: either the tile has
        less than MAX_SEARCH_RESULTS search results (the value is empirical
        to give good results with the Flickr API which is working more or less
        will under such extreme conditions), either the tile has more in which
        case it needs to be split.

        If the tile needs to be split then children are created and they will
        be scanned when moving down to the next level.

        There is one specificity though: if the children were not created
        because the max depth has been reached, then we gather the first
        MAX_SEARCH_RESULTS items and mark the tile as done. Tiles with such
        an image density will stand out either way.
        """

        f = Flickr.instance()

        kwargs = {
            "bbox": tile.bbox,
            "extras": ["geo", "date_taken", "url_q", "url_z", "url_b", "count_faves"],
        }
        info = f.search(page=1, **kwargs)
        harvest = True

        if int(info["photos"]["total"]) > Flickr.MAX_SEARCH_RESULTS:
            harvest = not tile.need_children()

        if harvest:
            seen = set()
            to_insert = []

            for page in range(
                0,
                min(
                    int(info["photos"]["pages"]),
                    int(Flickr.MAX_SEARCH_RESULTS / Flickr.PER_PAGE),
                ),
            ):
                if page == 0:
                    photos = info
                else:
                    photos = f.search(page=page + 1, **kwargs)

                assert len(photos["photos"]["photo"]) <= Flickr.PER_PAGE

                for photo in photos["photos"]["photo"]:
                    photo_id = int(photo["id"])

                    if photo_id not in seen:
                        seen.add(photo_id)
                        to_insert.append(photo)

            def make_images():
                """
                This is done in a generator because sometimes you might get
                a parsing error on an image, in which case you don't want
                a single image to crash the whole thing.
                """

                for image in to_insert:
                    try:
                        if int(image["id"]) not in existing:
                            yield Image(
                                flickr_id=int(image["id"]),
                                coords=Point(
                                    (
                                        float(image["longitude"]),
                                        float(image["latitude"]),
                                    )
                                ),
                                date_taken=pendulum.parse(image["datetaken"], tz="UTC"),
                                data=image,
                                faves=int(image.get("count_faves", 0)),
                            )
                    except (ValueError, TypeError):
                        pass

            with self.insert_lock, atomic():
                existing = set(
                    Image.objects.filter(flickr_id__in=seen).values_list(
                        "flickr_id", flat=True
                    )
                )

                Image.objects.bulk_create(make_images())

                tile.mark_done()
