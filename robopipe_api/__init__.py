try:
    from importlib.metadata import version, PackageNotFoundError

    __version__ = version(__name__)
except PackageNotFoundError:
    __version__ = "0.0.0.dev0"
