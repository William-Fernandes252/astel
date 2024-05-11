from __future__ import annotations

from typing import List
from urllib.robotparser import RequestRate, RobotFileParser

__all__ = ["UserAgent", "RequestRate", "RobotFileParser"]


class UserAgent:
    """A user agent for processing domain rules so that the crawler can respect them.

    Args:
        name (str): The name of the user agent
    """

    __slots__ = ("name", "_acknowledged_domains")

    def __init__(self, name: str) -> None:
        self.name = name
        self._acknowledged_domains: dict[str, RobotFileParser] = {}

    def respect(self, domain: str, robots_txt: str) -> None:
        """Process the rules in the robots.txt file in the URL and associates
        them to the given domain, if the domain has not already been acknowledged.

        Args:
            domain (str): A string representing the domain to be acknowledged.
            robots_url (str): A string representing the URL of the robots.txt file for
            the domain.
        """
        if domain in self._acknowledged_domains:
            return
        parser = RobotFileParser()
        parser.parse(robots_txt.splitlines())
        self._acknowledged_domains[domain] = parser

    def can_access(self, domain: str, url: str) -> bool:
        """Determines whether the given URL can be accessed by the user agent for the
        specified domain.

        Args:
            domain (str): A string representing the domain of the URL.
            url (str): A string representing the URL to access.

        Returns:
            bool: A boolean indicating whether the URL can be accessed for the
            specified domain.
        """
        return self._acknowledged_domains[domain].can_fetch(self.name, url)

    def get_request_rate(self, domain: str) -> RequestRate | None:
        """Given a domain, returns the request rate of that domain
        if it is acknowledged.

        Args:
            domain (str): A string representing the domain whose request rate is sought.

        Returns:
            Union[RequestRate, None]: An instance of `RequestRate` representing the
            domain's request rate if the domain is acknowledged, else `None`.
        """
        if domain not in self._acknowledged_domains:
            return None
        return self._acknowledged_domains[domain].request_rate(self.name)

    def get_crawl_delay(self, domain: str) -> str | None:
        """Returns the crawl delay for the given domain if it has been acknowledged,
        None otherwise.

        Args:
            domain (str): A string representing the domain to check the crawl delay for.

        Returns:
            Union[str, None]: A string representing the crawl delay for the given domain
            if it has been acknowledged, `None` otherwise.
        """
        if domain not in self._acknowledged_domains:
            return None

        crawl_delay = self._acknowledged_domains[domain].crawl_delay(self.name)
        return str(crawl_delay) if crawl_delay is not None else None

    def get_site_maps(self, domain: str) -> list[str] | None:
        """Returns the site maps associated with the given domain if the domain is
        acknowledged, otherwise returns None.

        Args:
            domain (str): A string representing the domain to retrieve site maps for.

        Returns:
            Union[list[str], None]: A list of strings representing the site maps
            associated with the domain, or `None` if the domain is not acknowledged.
        """
        if domain not in self._acknowledged_domains:
            return None
        return self._acknowledged_domains[domain].site_maps()

    @property
    def acknowledged_domains(self) -> List[str]:
        """The domains that have been acknowledged by the user agent."""
        return list(self._acknowledged_domains.keys())
