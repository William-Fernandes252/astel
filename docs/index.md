<div align="center">
  <img style="width: 50%; height: auto" src="assets/logo.png" alt="Naja logo">
</div>

[![pypi](https://img.shields.io/pypi/v/naja.svg)](https://pypi.org/project/naja/)
[![python](https://img.shields.io/pypi/pyversions/naja.svg)](https://pypi.org/project/naja/)
[![Build Status](https://github.com/William-Fernandes252/naja/actions/workflows/dev.yml/badge.svg)](https://github.com/William-Fernandes252/naja/actions/workflows/dev.yml)
[![codecov](https://codecov.io/gh/William-Fernandes252/naja/branch/main/graphs/badge.svg)](https://codecov.io/github/William-Fernandes252/naja)

A simple, fast and reliable asyncronous web crawler for Python.

* Documentation: <https://William-Fernandes252.github.io/naja>
* GitHub: <https://github.com/William-Fernandes252/naja>
* PyPI: <https://pypi.org/project/naja/>
* Free software: MIT

## Features

The main goal of `naja` is to offer a simpler, efficient and performant solution to programmatically look for
links  in webpages: no need to extend any class (**composition** over inheritance), no configuration and as few dependencies as possible.

This package relies on [HTTPX](https://www.python-httpx.org/) to send all requests in asynchronous operations, thus maximizing the number of pages processed during each execution.

## Credits

This package was created with [Cookiecutter](https://github.com/audreyr/cookiecutter) and the [waynerv/cookiecutter-pypackage](https://github.com/waynerv/cookiecutter-pypackage) project template.
