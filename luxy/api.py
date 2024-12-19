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

class FilterBuilder:
    def __init__(self, path=None):
        self.path = path or []

    def __getattr__(self, name):
        new_path = self.path + [name]
        return FilterBuilder(new_path)

    def __call__(self, value, depth=None):
        if depth is not None:
            if depth < 1:
                raise ValueError("Depth must be at least 1")
            
            # Use the last path element for nesting
            if not self.path:
                raise ValueError("No path specified for depth-based nesting")
            
            nest_key = self.path[-1]
            
            # Create nested structure based on depth
            current = {"name": value}
            for _ in range(depth):
                current = {nest_key: current}
            return current
        
        # Original behavior for non-depth calls
        current = {"name": value}
        for key in reversed(self.path):
            current = {key: current}
        return current

class BaseLux:
    def __init__(self):
        self.base_url = config["lux_url"]
        self.filters = []
        self.page_size = 20
        self.memberOf = FilterBuilder(["memberOf"])
        self.partOf = FilterBuilder(["partOf"])
        self.broader = FilterBuilder(["broader"])
        self._cached_response = None
        self._cached_query_dict = None

    def _encode_query(self, query: str):
        return urllib.parse.quote(json.dumps(query))

    def _query_builder(self, query: str):
        return f"{self.base_url}/search/{self.name}?q={query}"

    def _process_value(self, value):
        if value is True:
            return 1
        elif value is False:
            return 0
        elif isinstance(value, dict):
            return value
        return value

    def filter(self, **kwargs):
        # Get available options for validation
        valid_options = self.get_options()

        for key, value in kwargs.items():
            # Special handling for OR conditions
            if key == "OR":
                if not isinstance(value, list):
                    raise ValueError("OR filter must be a list of conditions")
                self.filters.append({"OR": value})
                continue
            
            # Rest of the validation logic for regular filters
            if key not in valid_options and key not in ["AND", "NOT"]:
                raise ValueError(f"Invalid filter '{key}' for {self.name}. Use list_filters() to see available options.")

            # Handle tuple case (value, comparison operator)
            if isinstance(value, tuple) and len(value) == 2:
                val, comp = value
                
                # Validate comparison operators based on relation type
                relation = valid_options[key]['relation']
                if relation not in ['number', 'date'] and comp != '==':
                    raise ValueError(f"Comparison operators can only be used with numeric or date filters. '{key}' is of type '{relation}'")
                
                if comp not in ['>', '>=', '<', '<=', '==', '!=']:
                    raise ValueError(f"Invalid comparison operator: {comp}")
                
                filter_obj = {
                    key: str(val),
                    "_comp": comp
                }
                self.filters = [filter_obj]
                
            else:
                # Validate enum values if they exist
                if "values" in valid_options[key] and value not in valid_options[key]["values"]:
                    valid_values = ", ".join(repr(v) for v in valid_options[key]["values"])
                    raise ValueError(f"Invalid value '{value}' for filter '{key}'. Valid values are: {valid_values}")
                
                processed_value = self._process_value(value) if not isinstance(value, dict) else self._process_nested_dict(value)
                self.filters.append({key: processed_value})
        
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
        # Check if there are any filters
        if not self.filters:
            raise ValueError("No filters specified. Please add at least one filter before calling get()")

        # Build the query
        query_ands = []
        
        for filter_dict in self.filters:
            # If it's already an OR condition, append as is
            if "OR" in filter_dict:
                query_ands.append({"OR": filter_dict["OR"]})
            # If it contains both a value and _comp, keep them together
            elif "_comp" in filter_dict:
                query_ands.append(filter_dict)
            # Otherwise process as normal
            else:
                for key, value in filter_dict.items():
                    processed_value = self._process_value(value)
                    query_ands.append({key: processed_value})

        query_dict = {"AND": query_ands} if query_ands else {}

        # If we have a cached response and the query hasn't changed, return cached data
        if self._cached_response and self._cached_query_dict == query_dict:
            logger.warning("Returning cached data...")
            return self

        # Otherwise, make the request and cache the results
        query_url = self._query_builder(self._encode_query(query_dict))
        response = requests.get(query_url)
        
        # Cache the results
        self._cached_query_dict = query_dict
        self._cached_response = response
        
        # Update instance attributes
        self.url = query_url
        # Create a reversed mapping from config values to keys
        reversed_config = {v: k for k, v in config.items()}
        self.view_url = query_url.replace(f"/api/search/{self.name}", f"/view/results/{reversed_config[self.name]}")
    
        self.json = self.get_json(response)
        self.num_results = self.get_num_results(self.json)
        return self

    def clear_cache(self):
        """Clear the cached response to force a new request"""
        self._cached_response = None
        self._cached_query_dict = None
        return self

    def get_json(self, response):
        return response.json()

    def get_num_results(self, json):
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
        if end_page is None or end_page > self.num_pages():
            logger.warning(f"End page is greater than the number of pages ({self.num_pages()}). Setting end page to {self.num_pages()+1}")
            end_page = self.num_pages()+1
        page_urls = self.get_page_urls()
        for page_url in page_urls[start_page:end_page]:
            yield self.get_page_data(page_url)

    def get_items(self, page_data):
        return page_data['orderedItems']
    
    def get_item_data(self, item):
        return self.get_page_data(item['id'])
    
    def get_options(self):
        """Get available filter options for this entity type.
        
        Returns:
            dict: A formatted dictionary where each key is a filter name and 
                 the value contains information about that filter including:
                 - description: What the filter does
                 - type: The data type expected
                 - values: List of possible values (if applicable)
        """
        options = get_lux_config()["terms"][self.name]
        
        # Format the options for better readability
        formatted_options = {}
        for key, details in options.items():
            formatted_options[key] = {
                "label": details.get("label", "No label available"),
                "description": details.get("helpText", "No description available"),
                "relation": details.get("relation", "Unknown type"),
                "allowedOptionsName": details.get("allowedOptionsName", "Unknown type"),
                "defaultOptionsName": details.get("defaultOptionsName", "Unknown type"),
            }
            
            # Add possible values if they exist
            if "values" in details:
                formatted_options[key]["values"] = details["values"]
                
        return formatted_options

    def list_filters(self):
        """Print a human-readable list of available filters and their descriptions."""
        options = self.get_options()
        print(f"\nAvailable filters for {self.name}:")
        print("-" * 50)
        
        for filter_name, details in options.items():
            print(f"\n{filter_name} ({details["label"]}) - ({details['relation']}):")
            print(f"  Description: {details['description']}")
            if "values" in details:
                print("  Possible values:")
                for value in details["values"]:
                    print(f"    - {value}")

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

class Collections(BaseLux):
    def __init__(self):
        self.name = config["set"]
        super().__init__()