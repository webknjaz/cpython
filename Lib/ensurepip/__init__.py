import importlib.resources
import os
import os.path
import pathlib
import shutil
import sys
import tempfile


from ._bundler import (
    _ensure_wheels_are_downloaded,
    _get_name_and_url,
    _PROJECT_URLS,
)


__all__ = ("version", "bootstrap")


def _get_name_and_version(url):
    return tuple(_get_name_and_url(url)[0].split('-')[:2])


def _run_pip(args, additional_paths=None):
    # Add our bundled software to the sys.path so we can import it
    if additional_paths is not None:
        sys.path = additional_paths + sys.path

    # Install the bundled software
    import pip._internal
    return pip._internal.main(args)


def version():
    """
    Returns a string specifying the bundled version of pip.
    """
    try:
        return next(
            v for n, v in (
                _get_name_and_version(pu) for pu in _PROJECT_URLS
            )
            if n == 'pip'
        )
    except StopIteration:
        raise RuntimeError('Failed to get bundled Pip version')


def _disable_pip_configuration_settings():
    # We deliberately ignore all pip environment variables
    # when invoking pip
    # See http://bugs.python.org/issue19734 for details
    keys_to_remove = [k for k in os.environ if k.startswith("PIP_")]
    for k in keys_to_remove:
        del os.environ[k]
    # We also ignore the settings in the default pip configuration file
    # See http://bugs.python.org/issue20053 for details
    os.environ['PIP_CONFIG_FILE'] = os.devnull


def bootstrap(*, root=None, upgrade=False, user=False,
              altinstall=False, default_pip=False,
              verbosity=0):
    """
    Bootstrap pip into the current Python installation (or the given root
    directory).

    Note that calling this function will alter both sys.path and os.environ.
    """
    # Discard the return value
    _bootstrap(root=root, upgrade=upgrade, user=user,
               altinstall=altinstall, default_pip=default_pip,
               verbosity=verbosity)


def _bootstrap(*, root=None, upgrade=False, user=False,
              altinstall=False, default_pip=False,
              verbosity=0):
    """
    Bootstrap pip into the current Python installation (or the given root
    directory). Returns pip command status code.

    Note that calling this function will alter both sys.path and os.environ.
    """
    if altinstall and default_pip:
        raise ValueError("Cannot use altinstall and default_pip together")

    _disable_pip_configuration_settings()

    # By default, installing pip and setuptools installs all of the
    # following scripts (X.Y == running Python version):
    #
    #   pip, pipX, pipX.Y, easy_install, easy_install-X.Y
    #
    # pip 1.5+ allows ensurepip to request that some of those be left out
    if altinstall:
        # omit pip, pipX and easy_install
        os.environ["ENSUREPIP_OPTIONS"] = "altinstall"
    elif not default_pip:
        # omit pip and easy_install
        os.environ["ENSUREPIP_OPTIONS"] = "install"

    # Ensure that the downloaded wheels are there
    _ensure_wheels_are_downloaded(verbosity=verbosity)

    with tempfile.TemporaryDirectory() as tmpdir:
        # Put our bundled wheels into a temporary directory and construct the
        # additional paths that need added to sys.path
        tmpdir_path = pathlib.Path(tmpdir)
        additional_paths = []
        wheels = map(_get_name_and_url, _PROJECT_URLS)
        for wheel_file_name, project_url, wheel_sha256 in wheels:
            tmp_wheel_path = tmpdir_path / wheel_file_name

            with importlib.resources.path(
                    'ensurepip', '_bundled',
            ) as bundled_dir:
                bundled_wheel = bundled_dir / wheel_file_name
                shutil.copy2(bundled_wheel, tmp_wheel_path)

            additional_paths.append(str(tmp_wheel_path))

        # Construct the arguments to be passed to the pip command
        args = ["install", "--no-index", "--find-links", tmpdir]
        if root:
            args += ["--root", root]
        if upgrade:
            args += ["--upgrade"]
        if user:
            args += ["--user"]
        if verbosity:
            args += ["-" + "v" * verbosity]

        wheels_specs = map(_get_name_and_version, _PROJECT_URLS)
        return _run_pip(args + [p[0] for p in wheels_specs], additional_paths)

def _uninstall_helper(*, verbosity=0):
    """Helper to support a clean default uninstall process on Windows

    Note that calling this function may alter os.environ.
    """
    # Nothing to do if pip was never installed, or has been removed
    try:
        import pip
    except ImportError:
        return

    pip_version = version()
    # If the pip version doesn't match the bundled one, leave it alone
    if pip.__version__ != pip_version:
        err_msg = (
            "ensurepip will only uninstall a matching version "
            f"({pip.__version__!r} installed, {pip_version!r} bundled)"
        )
        print(err_msg, file=sys.stderr)
        return

    _disable_pip_configuration_settings()

    # Construct the arguments to be passed to the pip command
    args = ["uninstall", "-y", "--disable-pip-version-check"]
    if verbosity:
        args += ["-" + "v" * verbosity]

    wheels_specs = map(_get_name_and_version, _PROJECT_URLS)
    return _run_pip(args + [p[0] for p in reversed(tuple(wheels_specs))])


def _main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(prog="python -m ensurepip")
    parser.add_argument(
        "--version",
        action="version",
        version="pip {}".format(version()),
        help="Show the version of pip that is bundled with this Python.",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="count",
        default=0,
        dest="verbosity",
        help=("Give more output. Option is additive, and can be used up to 3 "
              "times."),
    )
    parser.add_argument(
        "-U", "--upgrade",
        action="store_true",
        default=False,
        help="Upgrade pip and dependencies, even if already installed.",
    )
    parser.add_argument(
        "--user",
        action="store_true",
        default=False,
        help="Install using the user scheme.",
    )
    parser.add_argument(
        "--root",
        default=None,
        help="Install everything relative to this alternate root directory.",
    )
    parser.add_argument(
        "--altinstall",
        action="store_true",
        default=False,
        help=("Make an alternate install, installing only the X.Y versioned "
              "scripts (Default: pipX, pipX.Y, easy_install-X.Y)."),
    )
    parser.add_argument(
        "--default-pip",
        action="store_true",
        default=False,
        help=("Make a default pip install, installing the unqualified pip "
              "and easy_install in addition to the versioned scripts."),
    )

    args = parser.parse_args(argv)

    return _bootstrap(
        root=args.root,
        upgrade=args.upgrade,
        user=args.user,
        verbosity=args.verbosity,
        altinstall=args.altinstall,
        default_pip=args.default_pip,
    )
