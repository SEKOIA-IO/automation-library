from diskcache import Cache as InternalCache


class Cache:
    def __init__(self, directory_path):
        self._cache = InternalCache(directory_path)

    def get(self, key) -> str | None:
        with InternalCache(self._cache.directory) as reference:
            return reference.get(key, None)

    def set(self, key, value):
        with InternalCache(self._cache.directory) as reference:
            reference.set(key, value)
