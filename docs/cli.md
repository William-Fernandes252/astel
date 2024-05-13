# CLI

Astel also includes a simple command line interface to execute a crawler with a initial set of
URLs and see the pages found.

```bash
astel --help
```

```txt
Usage: astel [OPTIONS] URLS...

  Console script for astel.

Options:
  -w, --workers INTEGER  Number of workers to use.  [default: 5]
  -l, --limit INTEGER    Maximum number of URLs to crawl.  [default: 20]
  -u, --agent TEXT       User agent to use for the requests.  [default: astel]
  --help                 Show this message and exit.
```
