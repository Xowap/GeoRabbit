from time import sleep
from typing import Sequence, Text

from django.conf import settings
from requests_toolbelt.sessions import BaseUrlSession

from .models import BBox


class Flickr:
    """
    A wrapper around the Flickr API
    """

    _instance = None

    PER_PAGE = 250
    MAX_SEARCH_RESULTS = PER_PAGE * 4
    RATE_LIMIT = 1.0

    def __init__(self, base_url: Text, key: Text) -> None:
        """
        Don't call the constructor directly unless you're aware of what you are
        doing or using custom parameters.
        """

        self.session = BaseUrlSession(base_url)
        self.key = key

    @classmethod
    def instance(cls) -> "Flickr":
        """
        Returns a properly configured instances that will be created on first
        call and returned from cache subsequently
        """

        if cls._instance is None:
            cls._instance = Flickr(settings.FLICKR_BASE_URL, settings.FLICKR_API_KEY)

        return cls._instance

    def call(self, method, **params):
        """
        Calls a method on the Flickr API. Pass all additional parameters as
        kwargs to this method. The API key and other details like this will
        be automatically added.
        """

        params = dict(params)

        params["method"] = method
        params["api_key"] = self.key
        params["format"] = "json"
        params["nojsoncallback"] = "1"

        r = self.session.get("", params=params)
        r.raise_for_status()

        sleep(self.RATE_LIMIT)

        return r.json()

    def search(self, page: int, bbox: BBox, extras: Sequence[Text] = None):
        """
        Performs a search. Not all options are supported because we don't need
        them in this code.

        See https://www.flickr.com/services/api/flickr.photos.search.html
        """

        if not extras:
            extras = []

        return self.call(
            "flickr.photos.search",
            page=page,
            bbox=bbox.to_flickr(),
            extras=",".join(extras),
        )