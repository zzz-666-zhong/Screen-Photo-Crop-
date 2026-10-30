"""Bounded, read-only preparation of the next review image."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass


@dataclass
class PreparedImage:
    digest: str
    image: object
    corners: object = None
    preview: object = None
    error: str = ''


class ReviewPipeline:
    """Keep at most one look-ahead; workers never call Tk or write results."""
    def __init__(self, backend, args):
        self.backend, self.args = backend, args
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='crop-prefetch')
        self.entry = None

    @staticmethod
    def key(path):
        stat = path.stat()
        return str(path), stat.st_size, stat.st_mtime_ns

    def prepare(self, path):
        from batch_state import fingerprint
        signature=self.key(path)
        digest = fingerprint(path)
        image = self.backend.load_image(path)
        result = PreparedImage(digest, image)
        if not (self.args.manual or self.args.retry_failed):
            try:
                detector = self.backend.detect_black_border if self.args.black_review else self.backend.detect_screen
                result.corners = detector(image, square=self.args.square)
                if result.corners is not None:
                    result.preview = self.backend.finish_crop(
                        self.backend.rectify(image, result.corners, square=self.args.square), self.args)
            except Exception as exc:
                result.error = str(exc) or type(exc).__name__
        if self.key(path)!=signature:
            raise ValueError('原照片在读取时发生变化，请重新打开 / Source changed while preparing; reopen the image.')
        return result

    def request(self, path):
        key = self.key(path)
        if self.entry is not None and self.entry[0] == key:
            return self.entry[1]
        self.discard()
        future = self.executor.submit(self.prepare, path)
        self.entry = key, future
        return future

    def take(self, path):
        future = self.request(path)
        self.entry = None
        return future

    def discard(self):
        if self.entry is not None:
            self.entry[1].cancel()
            self.entry = None

    def close(self):
        self.discard()
        self.executor.shutdown(wait=False, cancel_futures=True)
