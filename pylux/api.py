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
    default="objects",
    objects="objects",
    works="works",
    people_groups="agent",
    places="places",
    concepts="concepts",
    events="events"
)

GENDER_MALE = "https://lux.collections.yale.edu/data/concept/6f652917-4c07-4d51-8209-fcdd4f285343"
GENDER_FEMALE = "https://lux.collections.yale.edu/data/concept/a309a746-9e51-4c34-b207-7f4773d2ac1a"

class BaseLux:
    def __init__(self):
        self.url = config["lux_url"]
        self.filters = []

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
        elif value.lower() == "male":
            return {"id": GENDER_MALE}
        elif value.lower() == "female":
            return {"id": GENDER_FEMALE}
        return value

    def filter(self, **kwargs):
        self.filters.append(kwargs)
        return self

    def get(self):
        query_ands = []
        
        # Add default recordType for PeopleGroups
        # if isinstance(self, PeopleGroups):
        #     query_ands.append({"recordType": "person"})

        # Process all filters
        for filter_dict in self.filters:
            for key, value in filter_dict.items():
                processed_value = self._process_value(value)
                
                if isinstance(processed_value, dict):
                    query_ands.append({key: processed_value})
                else:
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

class PeopleGroups(BaseLux):
    def __init__(self):
        self.name = config["people_groups"]
        super().__init__()