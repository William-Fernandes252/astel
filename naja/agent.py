from __future__ import annotations

from urllib.robotparser import RequestRate, RobotFileParser

__all__ = ["UserAgent", "RequestRate", "RobotFileParser"]


class UserAgent:
    """
    A user agent for processing domain rules so that the crawler can respect them.

    :param name: A string representing the name of the user agent, which is used to identify its rules.
    :type name: `str`

    :return: `None`
    :rtype: `None`
    """

    __slots__ = ("name", "_acknowledged_domains")

    def __init__(self, name: str) -> None:
        self.name = name
        self._acknowledged_domains: dict[str, RobotFileParser] = {}

    def respect(self, domain: str, robots_url: str) -> None:
        """
        Process the rules in the robots.txt file in the URL and associates them to the given domain, if the domain has not already been acknowledged.

        :param domain: A string representing the domain to be acknowledged.
        :type domain: `str`

        :param robots_url: A string representing the URL of the robots.txt file for the domain.
        :type robots_url: `str`

        :return: `None`
        :rtype: `None`
        """
        if domain in self._acknowledged_domains:
            return
        self._acknowledged_domains[domain] = RobotFileParser(robots_url)

    def can_access(self, domain: str, url: str) -> bool:
        """
        Determines whether the given URL can be accessed by the user agent for the specified domain.

        :param domain: A string representing the domain of the URL.
        :type domain: `str`

        :param url: A string representing the URL to access.
        :type url: `str`

        :return: A boolean indicating whether the URL can be accessed for the specified domain.
        """
        return self._acknowledged_domains[domain].can_fetch(self.name, url)

    def get_request_rate(self, domain: str) -> RequestRate | None:
        """
        Given a domain, returns the request rate of that domain if it is acknowledged.

        :param domain: A string representing the domain whose request rate is sought.
        :type domain: `str`

        :return: An instance of `RequestRate` representing the domain's request rate if the domain is acknowledged, else None.
        :rtype: `RequestRate | None`
        """
        if domain not in self._acknowledged_domains:
            return None
        return self._acknowledged_domains[domain].request_rate(self.name)

    def get_crawl_delay(self, domain: str) -> str | None:
        """
        Returns the crawl delay for the given domain if it has been acknowledged, None otherwise.

        :param domain: a string representing the domain to check the crawl delay for.
        :type domain: `str`

        :return: a string representing the crawl delay for the given domain if it has been acknowledged, None otherwise.
        :rtype: `str | None`
        """
        if domain not in self._acknowledged_domains:
            return None
        return self._acknowledged_domains[domain].crawl_delay(self.name)

    def get_site_maps(self, domain: str) -> list[str] | None:
        """
        Returns the site maps associated with the given domain if the domain is
        acknowledged, otherwise returns None.

        :param domain: A string representing the domain to retrieve site maps for.
        :type domain: `str`

        :return: A list of strings representing the site maps associated with the domain,
            or None if the domain is not acknowledged.
        :rtype: `list[str] | None`
        """
        if domain not in self._acknowledged_domains:
            return None
        return self._acknowledged_domains[domain].site_maps()
