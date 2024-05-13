<div align="center">
  <img style="width: 50%; height: auto" src="docs/assets/logo.png" alt="Astel logo">
</div>

# Astel

[![pypi](https://img.shields.io/pypi/v/astel.svg)](https://pypi.org/project/astel/)
[![python](https://img.shields.io/pypi/pyversions/astel.svg)](https://pypi.org/project/astel/)
[![Build Status](https://github.com/William-Fernandes252/astel/actions/workflows/dev.yml/badge.svg)](https://github.com/William-Fernandes252/astel/actions/workflows/dev.yml)
[![codecov](https://codecov.io/gh/William-Fernandes252/astel/graph/badge.svg?token=D8S6AF7A3Q)](https://codecov.io/gh/William-Fernandes252/astel)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

A simple, fast and reliable asyncronous web crawler for Python.

* Documentation: <https://William-Fernandes252.github.io/astel>
* GitHub: <https://github.com/William-Fernandes252/astel>
* PyPI: <https://pypi.org/project/astel/>
* Free software: MIT

## Features

The main goal of `astel` is to offer a simpler, efficient and performant solution to programmatically look for
links  in webpages: no need to extend any class (**composition** over inheritance), no configuration and as few dependencies as possible.

This package relies on [HTTPX](https://www.python-httpx.org/) to send all requests in asynchronous operations, thus maximizing the number of pages processed during each execution.

## Credits

This package was created with [Cookiecutter](https://github.com/audreyr/cookiecutter) and the [waynerv/cookiecutter-pypackage](https://github.com/waynerv/cookiecutter-pypackage) project template.
