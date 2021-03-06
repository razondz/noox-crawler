import requests
import re
from urllib.parse import urlparse
from collections import deque
from bs4 import BeautifulSoup, SoupStrainer


class LinkExtractor:

    _header = {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.11 (KHTML, like Gecko) Chrome/23.0.1271.64 Safari/537.11',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Charset': 'ISO-8859-1,utf-8;q=0.7,*;q=0.3',
        'Accept-Encoding': 'none',
        'Accept-Language': 'en-US,en;q=0.8',
        'Connection': 'keep-alive'
    }

    _edges = deque()

    _links = []

    _config = {}

    def __init__(self, config, start_url=None, debug=False, verbose=False):
        self._config.update(config)
        self._is_debug = debug
        self._is_verbose = verbose
        self.__verboseprint = print if self._is_verbose or self._is_debug else lambda *a, **k: None
        if isinstance(start_url, str):
            self._edges.append(start_url)

    def get_urls(self, crawl_depth_override=None, max_link=None):
        """
        Begin crawling the target website and return the extracted links.

        :param crawl_depth_override int: maximum crawl depth, default is from config
        :param max_link int: max link to extract
        :rtype: list
        """
        # check whether the config has been initialized
        if self._config == {}:
            raise RuntimeError('Config is not defined.')
        # if the edge is empty, we take the starter url from the config
        if len(self._edges) < 1:
            self._edges.append(self._config['url'])
        # if crawl_depth_override is supplied, use it instead of config
        if isinstance(crawl_depth_override, int):
            max_depth = crawl_depth_override
        else:
            max_depth = self._config['crawl_depth']

        # the config should remain as is, so we copy the url regex from config to local variable
        regex = re.compile(self._config['url_regex'])

        depth = 0
        links_np = set()
        while self._edges and (not max_link or len(self._links) < max_link):
            edge = self._edges.popleft()
            self.__verboseprint('Retrieving data from "'+edge+'"')
            page = requests.get(edge, headers=self._header, timeout=5)
            # if we got a sitemap index, add these sitemaps to our edge list
            if self._is_sitemap_index(page) and depth == 0:
                self.__verboseprint('Got sitemap index...')
                if 'sitemapindex_regex' in self._config and len(self._config['sitemapindex_regex']) > 0:
                    sitemapIndexRegex = re.compile(self._config['sitemapindex_regex'])
                else:
                    sitemapIndexRegex = re.compile('.*')
                for loc in BeautifulSoup(page.text, 'lxml-xml', parse_only=SoupStrainer('loc')):
                    url = loc.get_text().strip()
                    if sitemapIndexRegex.match(url):
                        self._edges.append(url)
            else:
                # if we got a sitemap, add the locs to the our links list
                if self._is_sitemap(page):
                    self.__verboseprint('Got sitemap...')
                    for loc in BeautifulSoup(page.text, 'lxml-xml', parse_only=SoupStrainer('loc')):
                        url = self._trim_url_query(loc.get_text().strip())
                        url_np = re.sub(r'https?://', '', url)
                        if regex.match(url) and url_np not in links_np:
                            self._links.append(url)
                            links_np.add(url_np)
                            if depth < max_depth:
                                self._edges.append(url)
                else:
                    # if we got a html page, extract the a tag with href matching with regex
                    soup = BeautifulSoup(page.text, 'lxml', parse_only=SoupStrainer('a', attrs={'href': regex}))
                    for tag in soup.find_all('a'):
                        url = self._trim_url_query(tag['href'])
                        url_np = re.sub(r'https?://', '', url)
                        if url_np not in links_np:
                            self._links.append(url)
                            links_np.add(url_np)
                            if depth < max_depth:
                                self._edges.append(url)
            depth += 1

        return self._links

    def _is_sitemap_index(self, page):
        """
        Check whether the given Response object is a sitemap index or not.

        @param page: requests.models.Response object
        @return: boolean
        """
        if page.__class__.__name__ != 'Response':
            raise ValueError('The supplied argument is not a requests.models.Response instance.')
        soup = BeautifulSoup(page.text, 'lxml-xml', parse_only=SoupStrainer('sitemapindex'))
        return str(soup.find('sitemapindex')) != 'None'

    def _is_sitemap(self, page):
        """
        Check whether the given Response object is a sitemap or not.

        @param page: requests.models.Response object
        @return: boolean
        """
        if page.__class__.__name__ != 'Response':
            raise ValueError('The supplied argument is not a requests.models.Response instance.')
        soup = BeautifulSoup(page.text, 'lxml-xml', parse_only=SoupStrainer('urlset'))
        return str(soup.find('urlset')) != 'None'

    def _trim_url_query(self, url: str):
        """
        Remove query from given url.

        :param url str: url to process
        :rtype: str
        """
        o = urlparse(url)
        return o.scheme + "://" + o.netloc + o.path
