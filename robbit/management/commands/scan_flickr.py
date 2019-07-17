from argparse import ArgumentParser
from typing import Text

import pendulum
from django.contrib.gis.geos import Point
from django.core.management import BaseCommand
from tqdm import tqdm

from ...flickr import Flickr
from ...models import Area, Image, Tile


class Command(BaseCommand):
    """
    This is where the scanning of the whole Flickr database happens.
    """

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

        print(f'Getting content for "{area}"')

        for level in range(0, Tile.MAX_DEPTH + 1):
            self.handle_level(level, area)

    def handle_level(self, level: int, area: Area) -> None:
        """
        Handles a single level. It will evaluate all the tiles found in this
        level. If the tile intersects the scanned area then the tile is
        handled, otherwise the scanning is deferred to another scan which would
        require this tile to be scanned.
        """

        print("")
        print(f"--> Level {level}")

        tiles = Tile.objects.filter(depth=level, status=Tile.TO_PROBE)

        for tile in tqdm(tiles, unit="tile"):
            if tile.polygon.intersects(area.area):
                self.handle_tile(tile)

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
            "extras": ["geo", "date_taken", "url_q", "url_z", "url_b"],
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

            existing = set(
                Image.objects.filter(flickr_id__in=seen).values_list(
                    "flickr_id", flat=True
                )
            )

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
                            )
                    except (ValueError, TypeError):
                        pass

            Image.objects.bulk_create(make_images())

            tile.mark_done()
