from io import BytesIO

# noinspection PyPackageRequirements
import zopfli
from django.contrib.staticfiles.storage import ManifestStaticFilesStorage
from django.contrib.staticfiles.utils import matches_patterns
from django.core.files.base import File


class GzipMixin:
    """
    Brings the Gzip-ability if mixed with a storage. Uses Zopfli for
    compression.
    """

    gzip_patterns = ("*.css", "*.js", "*.svg", "*.ttf")

    def _compress(self, original_file):
        c = zopfli.ZopfliCompressor(zopfli.ZOPFLI_FORMAT_GZIP)
        z = c.compress(original_file.read()) + c.flush()
        return File(BytesIO(z))

    def post_process(self, paths, dry_run=False, **options):
        super_class = super()

        if hasattr(super_class, "post_process"):
            for name, hashed_name, processed in super_class.post_process(
                paths.copy(), dry_run, **options
            ):
                if hashed_name != name:
                    paths[hashed_name] = (self, hashed_name)
                yield name, hashed_name, processed

        if dry_run:
            return

        for path in paths:
            if path:
                if not matches_patterns(path, self.gzip_patterns):
                    continue

                original_file = self.open(path, mode="rb")
                gzipped_path = "{0}.gz".format(path)

                if self.exists(gzipped_path):
                    self.delete(gzipped_path)

                gzipped_file = self._compress(original_file)
                gzipped_path = self.save(gzipped_path, gzipped_file)

                yield gzipped_path, gzipped_path, True


class GzipManifestStaticFilesStorage(GzipMixin, ManifestStaticFilesStorage):
    """
    Almost like the regular ManifestStaticFilesStorage, except it will create
    .gz files for all the text assets.
    """
