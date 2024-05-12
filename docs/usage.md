# Usage

To use Naja in a project, simply create a crawler instance passing a set of URLs to start.

```python
import asyncio
import naja

async def main():
    crawler = Crawler(["https://example.com"])
    crawler.run()
    print(crawler.urls_seen)
    # {ParsedUrl(domain='example', scheme='https', ...)}

if __name__ == '__main__':
    asyncio.run(main())
```

Note that the all the crawler operations are **asyncronous**, so you need to use a package that can run corotines like the built-in `asyncio` Python module.

To get details on how you can configure and customize the crawler behavior, go to the [API Reference](/naja/api).
