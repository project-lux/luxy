import logging
import warnings
import urllib.parse
import requests
import json

logger = logging.getLogger(__name__)

config = dict(
    lux_url="https://lux.collections.yale.edu/api",
    max_retries=0,
    retry_backoff_factor=0.1,
    default="item",
    objects="item",
    works="work",
    people_groups="agent",
    places="place",
    concepts="concept",
    events="event",
    set="set",
    lux_config="https://lux.collections.yale.edu/api/advanced-search-config"
)

def get_lux_config():
    response = requests.get(config["lux_config"])
    return response.json()

GENDER_MALE = "https://lux.collections.yale.edu/data/concept/6f652917-4c07-4d51-8209-fcdd4f285343"
GENDER_FEMALE = "https://lux.collections.yale.edu/data/concept/a309a746-9e51-4c34-b207-7f4773d2ac1a"

class FilterBuilder:
    def __init__(self, path=None):
        self.path = path or []

    def __getattr__(self, name):
        new_path = self.path + [name]
        return FilterBuilder(new_path)

    def __call__(self, value):
        current = {"name": value}
        for key in reversed(self.path):
            current = {key: current}
        return current

class BaseLux:
    def __init__(self):
        self.url = config["lux_url"]
        self.filters = []
        self.page_size = 20
        self.memberOf = FilterBuilder(["memberOf"])

    def _encode_query(self, query: str):
        return urllib.parse.quote(json.dumps(query))

    def _query_builder(self, query: str):
        return f"{self.url}/search/{self.name}?q={query}"

    def _process_value(self, value):
        if value is True:
            return 1
        elif value is False:
            return 0
        elif isinstance(value, dict):
            return value
        elif isinstance(value, str):
            if value.lower() == "male":
                return {"id": GENDER_MALE}
            elif value.lower() == "female":
                return {"id": GENDER_FEMALE}
        return value

    def filter(self, **kwargs):
        # Handle nested memberOf queries by allowing dict values to be nested
        processed_kwargs = {}
        for key, value in kwargs.items():
            if isinstance(value, dict):
                # Handle nested structure recursively
                processed_kwargs[key] = self._process_nested_dict(value)
            else:
                processed_kwargs[key] = self._process_value(value)
        
        self.filters.append(processed_kwargs)
        return self

    def _process_nested_dict(self, d):
        result = {}
        for key, value in d.items():
            if isinstance(value, dict):
                result[key] = self._process_nested_dict(value)
            else:
                result[key] = self._process_value(value)
        return result

    def get(self):
        query_ands = []
        
        # Process all filters
        for filter_dict in self.filters:
            if "OR" in filter_dict:
                # Handle OR conditions
                query_ands.append({"OR": filter_dict["OR"]})
            else:
                # Handle regular conditions
                for key, value in filter_dict.items():
                    processed_value = self._process_value(value)
                    query_ands.append({key: processed_value})

        query_dict = {"AND": query_ands} if query_ands else {}
        query_url = self._query_builder(self._encode_query(query_dict))
        response = requests.get(query_url)
        self.url = query_url
        self.json = self.get_json(response)
        self.num_results = self.num_results(self.json)
        return self

    def get_json(self, response):
        return response.json()

    def num_results(self, json):
        try:
            return json['partOf'][0]['totalItems']
        except (KeyError, IndexError):
            logger.warning("Could not find total items in response")
            return 0
        
    def num_pages(self):
        return (self.num_results // self.page_size) + (1 if self.num_results % self.page_size else 0)
    
    def get_page_urls(self):
        page_urls = []
        for page in range(1, self.num_pages()+1):
            temp_url = self.url + f"&page={page}"
            page_urls.append(temp_url)
        return page_urls
    
    def get_page_data(self, page_url):
        response = requests.get(page_url)
        return self.get_json(response)
    
    def get_page_data_all(self, start_page=0, end_page=None):
        if start_page > self.num_pages():
            logger.warning(f"Start page is greater than the number of pages ({self.num_pages()}). Setting start page to {self.num_pages()-1}")
            start_page = self.num_pages()-1
        if end_page > self.num_pages():
            logger.warning(f"End page is greater than the number of pages ({self.num_pages()}). Setting end page to {self.num_pages()+1}")
            end_page = self.num_pages()+1
        page_urls = self.get_page_urls()
        for page_url in page_urls[start_page:end_page]:
            yield self.get_page_data(page_url)

    def get_items(self, page_data):
        return page_data['orderedItems']
    
    def get_item_data(self, item):
        return self.get_page_data(item['id'])
    
class PeopleGroups(BaseLux):
    def __init__(self):
        self.name = config["people_groups"]
        super().__init__()

class Objects(BaseLux):
    def __init__(self):
        self.name = config["objects"]
        super().__init__()

class Works(BaseLux):
    def __init__(self):
        self.name = config["works"]
        super().__init__()

class Places(BaseLux):
    def __init__(self):
        self.name = config["places"]
        super().__init__()

class Concepts(BaseLux):
    def __init__(self):
        self.name = config["concepts"]
        super().__init__()

class Events(BaseLux):
    def __init__(self):
        self.name = config["events"]
        super().__init__()

class Sets(BaseLux):
    def __init__(self):
        self.name = config["set"]
        super().__init__()