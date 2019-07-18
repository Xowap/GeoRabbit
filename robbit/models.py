from typing import NamedTuple, Text

from django.contrib.gis.db.models import MultiPolygonField, PointField
from django.contrib.gis.geos import Polygon
from django.contrib.postgres.fields import JSONField
from django.core.validators import MinValueValidator
from django.db import models
from django.utils.translation import ugettext_lazy as _


class Coords(NamedTuple):
    """
    Represents a pair of x, y coordinates (typically longitude and latitude).
    """

    x: float
    y: float


class BBox(NamedTuple):
    """
    Represents a bounding box. c1 is the small values and c2 is the big values.
    """

    c1: Coords
    c2: Coords

    def to_flickr(self) -> Text:
        """
        Converts the bounding box into Flickr syntax.
        """

        return f"{self.c1.x},{self.c1.y},{self.c2.x},{self.c2.y}"

    def to_polygon(self) -> Polygon:
        """
        Converts the bounding box into a GEOS polygon.
        """

        return Polygon.from_bbox(self.c1 + self.c2)


class Tile(models.Model):
    """
    The MAX_DEPTH is computed  so that it encompasses a small area. If there is
    more than the API limit of pictures in this area then it means that this
    place is super-interesting but also already totally standing out, so there
    is no need to dig deeper. This is mostly helpful for special points like
    0,0 which are uninteresting but due to bugs have numerous pictures.

    See
    https://www.xkcd.com/2170/
    https://www.wolframalpha.com/input/?i=360%2F(2%5Ex)+%3D+0.001;+solve+x
    """

    MAX_DEPTH = 19

    TO_PROBE = "to-probe"
    CONTAINED = "contained"
    SPLIT = "split"

    STATUSES = [
        (TO_PROBE, _("to probe")),
        (CONTAINED, _("contained")),
        (SPLIT, _("split")),
    ]

    parent = models.ForeignKey(
        "Tile", related_name="children", on_delete=models.CASCADE, null=True
    )
    depth = models.IntegerField(
        db_index=True,
        validators=[
            MinValueValidator(
                0,
                message=_(
                    "Depth cannot be lower than 0 as it is already a full-earth tile"
                ),
            ),
            MinValueValidator(
                MAX_DEPTH,
                message=_(
                    "Max depth is %(max)d because more would not be useful "
                    "(see documentation)"
                )
                % {"max": MAX_DEPTH},
            ),
        ],
    )
    x = models.IntegerField(db_index=True)
    y = models.IntegerField(db_index=True)
    status = models.CharField(
        max_length=max(len(x) for x, _ in STATUSES),
        choices=STATUSES,
        default=TO_PROBE,
        help_text=_(
            "to-probe = a first API call must be done to know if the tile "
            "needs to be split, contained = all pictures from this tile are "
            "returned by the API, split = sub-tiles must be inspected instead"
        ),
    )

    @property
    def bbox(self) -> BBox:
        """
        Generates the bounding box for this tile.
        """

        splits = 2.0 ** self.depth

        dx = 360.0 / splits
        dy = 180.0 / splits

        return BBox(
            Coords(x=-180 + self.x * dx, y=-90 + self.y * dy),
            Coords(x=-180 + (self.x + 1) * dx, y=-90 + (self.y + 1) * dy),
        )

    @property
    def polygon(self) -> Polygon:
        """
        Generates the GEOS polygon for this tile.
        """

        return self.bbox.to_polygon()

    def need_children(self) -> bool:
        """
        Call this function if you find that this tile needs children. It will
        generate the required children, unless MAX_DEPTH has been reached. In
        that case, False will be returned.
        """

        depth = self.depth + 1

        if depth > self.MAX_DEPTH:
            return False

        x2 = self.x * 2
        y2 = self.y * 2

        Tile.objects.bulk_create(
            [
                Tile(depth=depth, x=x2, y=y2, parent=self),
                Tile(depth=depth, x=x2 + 1, y=y2, parent=self),
                Tile(depth=depth, x=x2 + 1, y=y2 + 1, parent=self),
                Tile(depth=depth, x=x2, y=y2 + 1, parent=self),
            ]
        )

        self.status = Tile.SPLIT
        self.save()

        return True

    def mark_done(self):
        """
        Marks the tile as completely contained
        """

        self.status = Tile.CONTAINED
        self.save()


class Image(models.Model):
    """
    Represents a Flickr image. All image data returned by the API is kept in
    the data field just in case it becomes useful later.
    """

    flickr_id = models.BigIntegerField(unique=True)
    coords = PointField(spatial_index=True)
    date_taken = models.DateTimeField(null=True)
    faves = models.PositiveIntegerField(db_index=True)
    data = JSONField()


class Area(models.Model):
    """
    That's a scanable area that can be created in the admin.
    """

    name = models.SlugField(unique=True)
    area = MultiPolygonField()

    def __str__(self):
        return self.name
