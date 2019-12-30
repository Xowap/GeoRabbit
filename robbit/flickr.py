from queue import Queue
from threading import Lock, Thread
from time import sleep
from typing import List, Sequence, Text

from django.conf import settings
from requests_toolbelt.sessions import BaseUrlSession

from .models import BBox


class Flickr:
    """
    A wrapper around the Flickr API

    It provides a thread-safe warranty that it won't exceed the rate limit
    imposed by Flickr, aka 1 request/second. If you call this from several
    threads it will make sure to wait at least 1s between two calls.

    Also, if you want to bring that rate limit up, you can provide several API
    keys. I'm guessing that this is not exactly within the terms and conditions
    but as long as it doesn't go too far it should be fine. I guess?
    """

    _instance = None
    _instance_lock = Lock()

    PER_PAGE = 250
    MAX_SEARCH_RESULTS = PER_PAGE * 8
    RATE_LIMIT = 1.0
    RETRY_WAIT = 10

    def __init__(self, base_url: Text, keys: List[Text]) -> None:
        """
        Don't call the constructor directly unless you're aware of what you are
        doing or using custom parameters.
        """

        # HTTP session
        self.session = BaseUrlSession(base_url)

        # Keys list
        self.keys = keys

        # Queue of keys, see _generate_keys()
        self.keys_queue = Queue(len(self.keys))

        # Indicates if key generation should be running
        self.key_gen_running = False

        # Keys-generating thread
        self.key_gen_thread = Thread(target=self._generate_keys, daemon=True)

    @classmethod
    def instance(cls) -> "Flickr":
        """
        Returns a properly configured instances that will be created on first
        call and returned from cache subsequently
        """

        with cls._instance_lock:
            if cls._instance is None:
                if not settings.FLICKR_API_KEYS:
                    raise RuntimeError("No Flickr API keys are available")

                cls._instance = Flickr(
                    settings.FLICKR_BASE_URL, settings.FLICKR_API_KEYS
                )
                cls._instance.start_generating_keys()

            return cls._instance

    @property
    def keys_count(self) -> int:
        """
        Indicates how many keys are available to guess how many threads should
        be running
        """

        return len(self.keys)

    def _generate_keys(self):
        """
        Flickr has a rate limit beyond which you cannot go. For this reason,
        this function will run in a separate thread (see
        start_generating_keys(), which is also automatically called by
        instance()) and put in the queue API keys as soon as they are
        available for call. This allows for a simple thread-safe mechanism
        to respect the rate limit without any complicated timekeeping.
        """

        while self.key_gen_running:
            sleep(self.RATE_LIMIT)

            for key in self.keys:
                self.keys_queue.put(key)

    def start_generating_keys(self):
        """
        Starts the keys generator thread.

        See Also
        --------
        stop_generating_keys() : To stop the thread
        _generate_keys() : The keys generation function
        """

        self.key_gen_running = True
        self.key_gen_thread.start()

    def stop_generating_keys(self):
        """
        Stops the keys generator thread. See _generate_keys().

        See Also
        --------
        start_generating_keys() : To start the thread
        _generate_keys() : The keys generation function
        """

        self.key_gen_running = False
        self.keys_queue.empty()

    def call(self, method, **params):
        """
        Calls a method on the Flickr API. Pass all additional parameters as
        kwargs to this method. The API key and other details like this will
        be automatically added.

        Also, makes sure that the rate limit is respected by only consuming
        keys from the queue.

        See Also
        --------
        _generate_keys() : To get an explanation on the keys queue
        """

        params = dict(params)

        params["method"] = method
        params["api_key"] = self.keys_queue.get()
        params["format"] = "json"
        params["nojsoncallback"] = "1"
        params["per_page"] = self.PER_PAGE

        r = None

        for _ in range(0, 100):
            r = self.session.get("", params=params)

            if r.status_code == 500:
                sleep(self.RETRY_WAIT)
            else:
                r.raise_for_status()
                return r.json()

        if r:
            r.raise_for_status()
        else:
            raise IOError("Could not get a response")

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
