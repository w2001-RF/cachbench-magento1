"""
Dataset loaders for benchmark system
"""

from abc import ABC, abstractmethod
from typing import List
import time
import numpy as np
import logging
from .models import CacheRequest

logger = logging.getLogger(__name__)


class DatasetLoader(ABC):
    """Base class for loading trace datasets"""
    
    @abstractmethod
    def load(self, path: str) -> List[CacheRequest]:
        """Load dataset and return list of cache requests"""
        pass


class MagentoTraceLoader(DatasetLoader):
    """Loader for Magento access logs"""
    
    def load(self, path: str) -> List[CacheRequest]:
        """
        Load Magento trace file
        Expected format: timestamp,url,size,category
        """
        requests = []
        
        try:
            with open(path, 'r') as f:
                for line in f:
                    if line.startswith("timestamp"):
                        continue
                    parts = line.strip().split(',')
                    if len(parts) >= 4:
                        request = CacheRequest(
                            timestamp=float(parts[0]),
                            key=parts[1],
                            size=int(parts[2]),
                            category=parts[3],
                            metadata={}
                        )
                        requests.append(request)
        except FileNotFoundError:
            logger.warning(f"Trace file not found: {path}, generating synthetic data")
            requests = self._generate_synthetic(1000)
        
        return requests
    
    def _generate_synthetic(self, count: int) -> List[CacheRequest]:
        """Generate synthetic e-commerce trace"""
        categories = ['product', 'category', 'cms_page', 'block', 'api']
        requests = []
        
        for i in range(count):
            category = np.random.choice(categories, p=[0.4, 0.2, 0.15, 0.15, 0.1])
            size = int(np.random.lognormal(8, 2))  # Log-normal distribution for sizes
            
            request = CacheRequest(
                timestamp=time.time() + i,
                key=f"/{category}/{np.random.randint(1, 1000)}",
                size=max(100, min(size, 100000)),  # Clamp size
                category=category
            )
            requests.append(request)

        return requests


# ----------------------------------------------------------------------
# External datasets: e-commerce event logs, real cache traces, access logs
# ----------------------------------------------------------------------

import csv
import gzip
import io
import re
import struct
import zipfile
import zlib
from datetime import datetime, timedelta, timezone
from itertools import islice
from pathlib import Path
from typing import Dict, Iterator, Optional, Sequence, Tuple


def _open_binary(path: str):
    """Open a trace file, decompressing .gz / .zst / .zip transparently"""
    lower = str(path).lower()
    if lower.endswith(".gz"):
        return gzip.open(path, "rb")
    if lower.endswith(".zst"):
        try:
            import zstandard
        except ImportError as e:
            raise ImportError("Reading .zst traces needs the 'zstandard' package: "
                              "pip install zstandard") from e
        return io.BufferedReader(
            zstandard.ZstdDecompressor().stream_reader(open(path, "rb"), closefd=True))
    if lower.endswith(".zip"):
        archive = zipfile.ZipFile(path)
        return archive.open(archive.namelist()[0])
    return open(path, "rb")


def _read_lines(path: str) -> Iterator[str]:
    with _open_binary(path) as raw:
        text = io.TextIOWrapper(raw, encoding="utf-8", errors="replace", newline="")
        try:
            yield from text
        except EOFError:
            logger.warning(f"{path} ends early (truncated download?); using the complete part")


class SyntheticSizer:
    """
    Made-up response sizes for datasets that have none (Kaggle, REES46, Retailrocket).
    Sizes are derived from the key, so a given URL always has the same size.
    """

    DEFAULT_RANGES = {"product": (5000, 50000), "api": (500, 5000)}

    def __init__(self, ranges: Optional[Dict[str, Tuple[int, int]]] = None,
                 default: Tuple[int, int] = (1000, 10000), salt: str = ""):
        self.ranges = ranges or self.DEFAULT_RANGES
        self.default = default
        self.salt = salt

    def size(self, key: str, category: str) -> int:
        lo, hi = self.ranges.get(category, self.default)
        return lo + zlib.crc32((self.salt + key).encode()) % (hi - lo)


class StreamingTraceLoader(DatasetLoader):
    """Base for loaders that read a file lazily; max_requests caps very large traces"""

    def __init__(self, max_requests: Optional[int] = None):
        self.max_requests = max_requests

    @abstractmethod
    def iter_requests(self, path: str) -> Iterator[CacheRequest]:
        pass

    def load(self, path: str) -> List[CacheRequest]:
        requests = list(islice(self.iter_requests(path), self.max_requests))
        logger.info(f"{type(self).__name__}: loaded {len(requests)} requests from {path}")
        return requests


class _EventLogLoader(StreamingTraceLoader):
    """Maps shop events to Magento-style URLs, as in the existing magento_trace_*.csv files"""

    EVENT_URLS: Dict[str, Tuple[str, str]] = {}

    def __init__(self, max_requests: Optional[int] = None,
                 event_types: Optional[Sequence[str]] = None,
                 sizer: Optional[SyntheticSizer] = None):
        super().__init__(max_requests)
        self.event_types = set(event_types) if event_types else set(self.EVENT_URLS)
        self.sizer = sizer or SyntheticSizer()

    def _request(self, timestamp: float, event: str, item_id: str,
                 metadata: Dict) -> Optional[CacheRequest]:
        if event not in self.event_types or event not in self.EVENT_URLS:
            return None
        template, category = self.EVENT_URLS[event]
        key = template.format(pid=item_id)
        return CacheRequest(timestamp=timestamp, key=key,
                            size=self.sizer.size(key, category),
                            category=category, metadata=metadata)


class REES46EventLoader(_EventLogLoader):
    """
    Kaggle "eCommerce behavior data from multi category store" (Oct-Nov 2019),
    REES46 Open CDP monthly files (Dec 2019 - Apr 2020) and the Kaggle cosmetics shop.
    Columns: event_time,event_type,product_id,category_id,category_code,brand,price,user_id,user_session
    """

    EVENT_URLS = {
        "view": ("/product/{pid}", "product"),
        "cart": ("/checkout/cart/add/{pid}", "api"),
        "remove_from_cart": ("/checkout/cart/delete/{pid}", "api"),
        "purchase": ("/checkout/onepage/success", "api"),
    }

    def iter_requests(self, path: str) -> Iterator[CacheRequest]:
        reader = csv.reader(_read_lines(path))
        header = next(reader, None) or []
        col = {name: i for i, name in enumerate(header)}
        t_col, e_col, p_col = col["event_time"], col["event_type"], col["product_id"]
        last_time, last_ts = None, 0.0

        for row in reader:
            if len(row) < len(header):
                continue  # truncated last line
            event_time = row[t_col]
            if event_time != last_time:  # many events share a second
                try:
                    last_ts = datetime.fromisoformat(event_time[:19]).replace(
                        tzinfo=timezone.utc).timestamp()
                except ValueError:
                    continue
                last_time = event_time
            request = self._request(last_ts, row[e_col], row[p_col], {"event": row[e_col]})
            if request is not None:
                yield request


KaggleEcommerceLoader = REES46EventLoader


class RetailrocketLoader(_EventLogLoader):
    """
    Retailrocket e-commerce dataset, events.csv.
    Columns: timestamp (ms),visitorid,event,itemid,transactionid
    The file is not in time order, so requests are sorted unless sort_by_time=False.
    """

    EVENT_URLS = {
        "view": ("/product/{pid}", "product"),
        "addtocart": ("/checkout/cart/add/{pid}", "api"),
        "transaction": ("/checkout/onepage/success", "api"),
    }

    def __init__(self, *args, sort_by_time: bool = True, **kwargs):
        super().__init__(*args, **kwargs)
        self.sort_by_time = sort_by_time

    def iter_requests(self, path: str) -> Iterator[CacheRequest]:
        reader = csv.reader(_read_lines(path))
        header = next(reader, None) or []
        col = {name: i for i, name in enumerate(header)}
        t_col, e_col, i_col = col["timestamp"], col["event"], col["itemid"]

        def rows():
            for row in reader:
                if len(row) < len(header):
                    continue
                try:
                    ts = int(row[t_col]) / 1000.0
                except ValueError:
                    continue
                request = self._request(ts, row[e_col], row[i_col], {"event": row[e_col]})
                if request is not None:
                    yield request

        if self.sort_by_time:
            yield from sorted(rows(), key=lambda r: r.timestamp)
        else:
            yield from rows()


class TwitterCacheTraceLoader(StreamingTraceLoader):
    """
    Twitter production cache traces (github.com/twitter/cache-trace).
    Columns: timestamp,key,key_size,value_size,client_id,operation,ttl
    Object size is key_size + value_size. Only reads (get/gets) become requests unless
    include_writes=True; writes still update the known size of their key.
    """

    READ_OPS = {"get", "gets"}
    WRITE_OPS = {"set", "add", "replace", "cas", "append", "prepend"}

    def __init__(self, max_requests: Optional[int] = None, include_writes: bool = False):
        super().__init__(max_requests)
        self.include_writes = include_writes

    def iter_requests(self, path: str) -> Iterator[CacheRequest]:
        known_sizes: Dict[str, int] = {}
        for line in _read_lines(path):
            parts = line.rstrip("\r\n").split(",")
            if len(parts) < 7:
                continue
            op = parts[-2]
            is_write = op in self.WRITE_OPS
            if not is_write and op not in self.READ_OPS:
                continue  # delete, incr, decr, ...
            try:
                timestamp = float(parts[0])
                key_size, value_size = int(parts[-5]), int(parts[-4])
            except ValueError:
                continue
            key = ",".join(parts[1:-5])  # keys may contain commas

            if value_size > 0:
                size = key_size + value_size
                known_sizes[key] = size
            else:
                size = known_sizes.get(key, 0)  # a get that missed in production
            if (is_write and not self.include_writes) or size <= 0:
                continue
            yield CacheRequest(timestamp=timestamp, key=key, size=size, category="kv",
                               metadata={"op": op} if is_write else {})


class LibCacheSimLoader(StreamingTraceLoader):
    """
    libCacheSim traces: the oracleGeneral binary format (24-byte records of
    uint32 time, uint64 object id, uint32 size, int64 next access) or its CSV
    form ("# time, object, size, next_access_vtime").
    """

    RECORD = struct.Struct("<IQIq")

    def iter_requests(self, path: str) -> Iterator[CacheRequest]:
        name = Path(path).name.lower()
        if "oraclegeneral" in name or name.split(".")[-1] == "bin" or ".bin." in name:
            yield from self._iter_binary(path)
        else:
            yield from self._iter_csv(path)

    def _iter_binary(self, path: str) -> Iterator[CacheRequest]:
        size = self.RECORD.size
        pending = b""
        with _open_binary(path) as f:
            while True:
                try:
                    chunk = f.read(size * 65536)
                except EOFError:
                    logger.warning(f"{path} ends early (truncated download?); using the complete part")
                    break
                if not chunk:
                    break
                pending += chunk
                usable = len(pending) - len(pending) % size
                for timestamp, obj_id, obj_size, _ in self.RECORD.iter_unpack(pending[:usable]):
                    if obj_size > 0:
                        yield CacheRequest(timestamp=float(timestamp), key=str(obj_id),
                                           size=obj_size, category="object")
                pending = pending[usable:]
        if pending:
            logger.warning(f"{path}: ignored {len(pending)} trailing bytes (partial record)")

    def _iter_csv(self, path: str) -> Iterator[CacheRequest]:
        for line in _read_lines(path):
            if line.startswith("#"):
                continue
            parts = [p.strip() for p in line.split(",")]
            if len(parts) < 3:
                continue
            try:
                timestamp, obj_size = float(parts[0]), int(parts[2])
            except ValueError:
                continue
            if obj_size > 0:
                yield CacheRequest(timestamp=timestamp, key=parts[1], size=obj_size,
                                   category="object")


class AccessLogLoader(StreamingTraceLoader):
    """
    Web server access logs in Common or Combined Log Format: NASA HTTP logs
    (Internet Traffic Archive), Nginx, Apache and Varnish (varnishncsa) logs of a
    Magento store. Response sizes are the real ones from the log.

    URLs are classified into Magento page types with url_rules: (regex, category)
    pairs tried in order; the first match wins, anything else is "page".
    """

    LOG_RE = re.compile(r'^(\S+) \S+ \S+ \[([^\]]+)\] "(\S+) (\S+)[^"]*" (\d{3}) (\S+)')
    MONTHS = {m: i for i, m in enumerate(
        ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
         "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], start=1)}

    DEFAULT_URL_RULES = [
        (r"^/(pub/)?(static|media)/", "static"),
        (r"\.(js|css|png|jpe?g|gif|svg|webp|ico|woff2?|ttf|eot|map)(\?|$)", "static"),
        (r"^/(rest|graphql|soap)\b", "api"),
        (r"^/(checkout|customer|sales|wishlist|newsletter|paypal|braintree)\b", "api"),
        (r"^/catalogsearch\b", "search"),
        (r"^/catalog/product/view\b", "product"),
        (r"^/catalog/category/view\b", "category"),
        (r"^/(\?.*)?$", "cms_page"),               # home page
        (r"^/[^/?]+\.html(\?|$)", "product"),      # Magento product URL key at the root
        (r"^/.+/[^/?]+\.html(\?|$)", "category"),  # nested path: category URL
    ]

    def __init__(self, max_requests: Optional[int] = None,
                 methods: Sequence[str] = ("GET",),
                 statuses: Sequence[int] = (200,),
                 url_rules: Optional[Sequence[Tuple[str, str]]] = None,
                 strip_query: bool = False):
        super().__init__(max_requests)
        self.methods = set(methods)
        self.statuses = {str(s) for s in statuses}
        self.url_rules = [(re.compile(p, re.IGNORECASE), c)
                          for p, c in (url_rules or self.DEFAULT_URL_RULES)]
        self.strip_query = strip_query

    def categorize(self, url: str) -> str:
        for pattern, category in self.url_rules:
            if pattern.search(url):
                return category
        return "page"

    def iter_requests(self, path: str) -> Iterator[CacheRequest]:
        last_time, last_ts = None, 0.0
        for line in _read_lines(path):
            m = self.LOG_RE.match(line)
            if not m:
                continue
            _, log_time, method, url, status, size = m.groups()
            if method not in self.methods or status not in self.statuses or not size.isdigit():
                continue
            if log_time != last_time:
                try:
                    last_ts = self._parse_time(log_time)
                except (KeyError, ValueError):
                    continue
                last_time = log_time
            if self.strip_query:
                url = url.split("?", 1)[0]
            if int(size) > 0:
                yield CacheRequest(timestamp=last_ts, key=url, size=int(size),
                                   category=self.categorize(url))

    def _parse_time(self, value: str) -> float:
        # "01/Jul/1995:00:00:01 -0400"; parsed by hand because %b depends on the locale
        day, month, rest = value.split("/", 2)
        year, hh, mm, ss_tz = rest.split(":", 3)
        ss, _, tz = ss_tz.partition(" ")
        offset = timedelta(0)
        if tz:
            sign = -1 if tz[0] == "-" else 1
            offset = sign * timedelta(hours=int(tz[1:3]), minutes=int(tz[3:5]))
        return datetime(int(year), self.MONTHS[month], int(day), int(hh), int(mm), int(ss),
                        tzinfo=timezone(offset)).timestamp()


LOADERS = {
    "magento": MagentoTraceLoader,
    "rees46": REES46EventLoader,
    "kaggle": REES46EventLoader,
    "retailrocket": RetailrocketLoader,
    "twitter": TwitterCacheTraceLoader,
    "libcachesim": LibCacheSimLoader,
    "access_log": AccessLogLoader,
}


def detect_format(path: str) -> str:
    """Guess the trace format from the file name and its first line"""
    if "oraclegeneral" in Path(path).name.lower():
        return "libcachesim"
    lines = _read_lines(path)
    try:
        first = next((line.strip() for line in lines if line.strip()), "")
    finally:
        lines.close()

    if first.startswith("timestamp,url,size,category"):
        return "magento"
    if first.startswith("event_time,event_type"):
        return "rees46"
    if first.startswith("timestamp,visitorid,event"):
        return "retailrocket"
    if first.startswith("# time"):
        return "libcachesim"
    if AccessLogLoader.LOG_RE.match(first):
        return "access_log"
    parts = first.split(",")
    if len(parts) >= 7 and parts[-2] in (TwitterCacheTraceLoader.READ_OPS
                                         | TwitterCacheTraceLoader.WRITE_OPS):
        return "twitter"
    raise ValueError(f"Cannot detect the trace format of {path}; pass fmt= one of {sorted(LOADERS)}")


def load_trace(path: str, fmt: Optional[str] = None, max_requests: Optional[int] = None,
               **loader_kwargs) -> List[CacheRequest]:
    """Load any supported trace; fmt is detected from the file when omitted"""
    fmt = fmt or detect_format(path)
    if fmt not in LOADERS:
        raise ValueError(f"Unknown trace format '{fmt}'; known formats: {sorted(LOADERS)}")
    if fmt == "magento":
        requests = MagentoTraceLoader().load(path)
        return requests[:max_requests] if max_requests else requests
    return LOADERS[fmt](max_requests=max_requests, **loader_kwargs).load(path)