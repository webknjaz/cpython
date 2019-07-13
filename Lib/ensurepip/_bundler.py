"""Build time dist downloading and bundling logic."""

import hashlib
import importlib.resources
import sys
import urllib.parse
import urllib.request


_PROJECT_URLS = (
    'https://files.pythonhosted.org/packages/c8/b0/'
    'cc6b7ba28d5fb790cf0d5946df849233e32b8872b6baca10c9e002ff5b41/'
    'setuptools-41.0.0-py2.py3-none-any.whl#'
    'sha256=e67486071cd5cdeba783bd0b64f5f30784ff855b35071c8670551fd7fc52d4a1',

    'https://files.pythonhosted.org/packages/d8/f3/'
    '413bab4ff08e1fc4828dfc59996d721917df8e8583ea85385d51125dceff/'
    'pip-19.0.3-py2.py3-none-any.whl#'
    'sha256=bd812612bbd8ba84159d9ddc0266b7fbce712fc9bc98c82dee5750546ec8ec64',
)


def _ensure_wheels_are_downloaded(*, verbosity=0):
    """Download wheels into bundle if they are not there yet."""
    with importlib.resources.path('ensurepip', '_bundled') as bundled_dir:
        wheels = map(_get_name_and_url, _PROJECT_URLS)
        for wheel_file_name, project_url, wheel_sha256 in wheels:
            whl_file_path = bundled_dir / wheel_file_name
            try:
                if _is_content_sha256_valid(
                        content=whl_file_path.read_bytes(),
                        sha256=wheel_sha256,
                ):
                    if verbosity:
                        print(
                            f'A valid `{wheel_file_name}` is already '
                            'present in cache. Skipping download.',
                            file=sys.stderr,
                        )
                    continue
            except FileNotFoundError:
                pass

            if verbosity:
                print(
                    f'Downloading `{wheel_file_name}`...',
                    file=sys.stderr,
                )
            downloaded_whl_contents = _download(
                url=project_url,
                sha256=wheel_sha256,
            )
            if verbosity:
                print(
                    f'Saving `{wheel_file_name}` to disk...',
                    file=sys.stderr,
                )
            whl_file_path.write_bytes(downloaded_whl_contents)


def _download(*, url, sha256):
    """Retrieve the given URL contents and verify hash if needed.

    If hash in the URL fragment doesn't match downloaded one, raise a
    ValueError.

    Return the URL contents as a memoryview object on success.
    """
    with urllib.request.urlopen(url) as downloaded_file:
        resource_content = memoryview(downloaded_file.read())

    if not _is_content_sha256_valid(content=resource_content, sha256=sha256):
        raise ValueError(f"The payload's hash is invalid for ``{url}``.")

    return resource_content


def _is_content_sha256_valid(*, content, sha256):
    return (
        sha256 is None or
        sha256 == hashlib.sha256(content).hexdigest()
    )


def _get_name_and_url(url):
    url_path = urllib.parse.urlsplit(url).path
    _path_dir, _sep, file_name = url_path.rpartition('/')
    sha256 = _extract_sha256_from_url_fragment(url=url)
    return file_name, url, sha256


def _extract_sha256_from_url_fragment(*, url):
    """Extract SHA-256 hash from the given URL fragment part."""
    url_fragment = urllib.parse.urlsplit(url).fragment.strip()
    return next(
        iter(urllib.parse.parse_qs(url_fragment).get("sha256")),
        None,
    )
