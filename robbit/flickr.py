from time import sleep
from typing import Sequence, Text

from django.conf import settings
from pendulum import now
from requests_toolbelt.sessions import BaseUrlSession

from .models import BBox


class Flickr:
    """
    A wrapper around the Flickr API
    """

    _instance = None

    PER_PAGE = 250
    MAX_SEARCH_RESULTS = PER_PAGE * 8
    RATE_LIMIT = 1.0

    def __init__(self, base_url: Text, key: Text) -> None:
        """
        Don't call the constructor directly unless you're aware of what you are
        doing or using custom parameters.
        """

        self.session = BaseUrlSession(base_url)
        self.key = key
        self.last_call = now()

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

        Also, makes sure that the rate limit is respected by sleeping. The
        time of the call is deduced from the sleeping time.
        """

        params = dict(params)

        params["method"] = method
        params["api_key"] = self.key
        params["format"] = "json"
        params["nojsoncallback"] = "1"
        params["per_page"] = self.PER_PAGE

        r = self.session.get("", params=params)
        r.raise_for_status()

        last_call = self.last_call
        this_call = now()
        diff = this_call - last_call
        self.last_call = this_call

        sleep(max(0, self.RATE_LIMIT - diff.in_seconds()))

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
