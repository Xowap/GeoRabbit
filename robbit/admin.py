from django.contrib import admin
from leaflet.admin import LeafletGeoAdmin

from .models import Area


@admin.register(Area)
class AreaAdmin(LeafletGeoAdmin):
    """
    Simple admin to create the areas in order to do the scans correctly
    """

    list_display = ["name"]
