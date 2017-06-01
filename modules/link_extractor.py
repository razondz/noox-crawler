import requests
import re
from multiprocessing import Queue
from time import sleep
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

    _edges = Queue()

    _links = []

    _config = {}

    def __init__(cls, config, start_url=None):
        cls._config.update(config)
        if isinstance(start_url, str):
            cls._edges.put(start_url)

    def get_urls(cls, crawl_depth_override=None, max_link=None):
        """
        Begin crawling the target website and return the extracted links.

        @param crawl_depth_override: maximum crawl depth, default is from config
        @return: list
        """
        # check whether the config has been initialized
        if cls._config == {}:
            raise RuntimeError('Config is not defined.')
        # if the edge is empty, we take the starter url from the config
        if cls._edges.qsize() < 1:
            cls._edges.put(cls._config['url'], block=True)
        # if crawl_depth_override is supplied, use it instead of config
        if isinstance(crawl_depth_override, int):
            max_depth = crawl_depth_override
        else:
            max_depth = cls._config['crawl_depth']

        # the config should remain as is, so we copy the url regex from config to local variable
        regex = re.compile(cls._config['url_regex'])

        depth = 0
        sleep(0.001)
        while not cls._edges.empty() and (not max_link or len(cls._links) < max_link):
            print('Retrieving data from url...')
            edge = cls._edges.get(block=True)
            page = requests.get(edge, headers=cls._header)
            # if we got a sitemap index, add these sitemaps to our edge list
            if cls._is_sitemap_index(page) and depth == 0:
                print('Got sitemap index...')
                for loc in BeautifulSoup(page.text, 'lxml-xml', parse_only=SoupStrainer('loc')):
                    cls._edges.put(loc.get_text().strip(), block=True)
                    sleep(0.001)
            else:
                # if we got a sitemap, add the locs to the our links list
                if cls._is_sitemap(page):
                    print('Got sitemap...')
                    for loc in BeautifulSoup(page.text, 'lxml-xml', parse_only=SoupStrainer('loc')):
                        url = loc.get_text().strip()
                        if regex.match(url) and url not in cls._links:
                            cls._links.append(url)
                            if depth < max_depth:
                                cls._edges.put(url, block=True)
                                sleep(0.001)
                else:
                    # if we got a html page, extract the a tag with href matching with regex
                    soup = BeautifulSoup(page.text, 'lxml', parse_only=SoupStrainer('a', attrs={'href': regex}))
                    for url in soup.find_all('a'):
                        if url['href'] not in cls._links:
                            cls._links.append(url['href'])
                            if depth < max_depth:
                                cls._edges.put(url['href'], block=True)
                                sleep(0.001)
            depth += 1

        print('Found '+str(len(cls._links))+' links...')
        print('Operation finished...')
        return cls._links

    def _is_sitemap_index(cls, page):
        """
        Check whether the given Response object is a sitemap index or not.

        @param page: requests.models.Response object
        @return: boolean
        """
        if page.__class__.__name__ != 'Response':
            raise ValueError('The supplied argument is not a requests.models.Response instance.')
        soup = BeautifulSoup(page.text, 'lxml-xml', parse_only=SoupStrainer('sitemapindex'))
        return str(soup.find('sitemapindex')) != 'None'

    def _is_sitemap(cls, page):
        """
        Check whether the given Response object is a sitemap or not.

        @param page: requests.models.Response object
        @return: boolean
        """
        if page.__class__.__name__ != 'Response':
            raise ValueError('The supplied argument is not a requests.models.Response instance.')
        soup = BeautifulSoup(page.text, 'lxml-xml', parse_only=SoupStrainer('urlset'))
        return str(soup.find('urlset')) != 'None'