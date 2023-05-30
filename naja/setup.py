from distutils.core import setup

exec(open("naja/version.py").read())
setup(
    name="naja",
    version=__version__,  # type: ignore
    description="A asyncronous web crawling package for Python.",
    author="William Fernandes Dias",
    author_email="william.winchester1967@gmail.com",
    url="https://github.com/William-Fernandes252/naja",
    packages=["naja"],
    install_requires=["httpx", "tdlextract"],
    py_modules=[
        "filters",
        "parsers",
        "limiters",
        "crawler",
        "protocols",
        "errors",
        "agent",
    ],
)
