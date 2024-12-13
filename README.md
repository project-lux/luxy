PyLux is a Python wrapper for Yale's Lux API. Currently, there is minimal support for the API, but it is in active development.

# Installation

**warning** not on pypi yet...

```bash
pip install pylux
```

# Usage

```python
from pylux.api import PeopleGroups

result = (
    PeopleGroups()
    .filter(recordType="person")
    .filter(hasDigitalImage=True)
    .filter(text="rembrandt")
    .filter(gender="male")
    .get()
)

# print the number of results
print("Number of results:", result.num_results)

# print the url
print("URL:", result.url)

# print the json
print("JSON:", result.json)
```

## Expected Output

```bash
Number of results: 131
URL: https://lux.collections.yale.edu/api/search/agent?q=%7B%22AND%22%3A%20%5B%7B%22recordType%22%3A%20%22person%22%7D%2C%20%7B%22hasDigitalImage%22%3A%201%7D%2C%20%7B%22text%22%3A%20%22rembrandt%22%7D%2C%20%7B%22gender%22%3A%20%7B%22id%22%3A%20%22https%3A//lux.collections.yale.edu/data/concept/6f652917-4c07-4d51-8209-fcdd4f285343%22%7D%7D%5D%7D
JSON: {'@context': 'https://linked.art/ns/v1/search.json'...
```

# Roadmap
- [x] Add support for People/Groups
    - [ ] Filter by:
        - [x] Has Digital Image
        - [x] Gender
        - [ ] Nationality
        - [x] Person or Group Class
        - [ ] Categorized As
        - [x] Born/Formed At
        - [ ] Born/Formed Date
        - [ ] Died/Dissolved At
        - [ ] Died/Dissolved Date
        - [ ] Occupation/Role
        - [ ] Professionally Active At
        - [ ] Professionally Active Date
        - [ ] Member Of
        - [ ] Professional Activity Categorized As
    - [x] Add support for Groups
- [ ] Add support for Objects
- [ ] Add support for Works
- [ ] Add support for Places
- [ ] Add support for Concepts
- [ ] Add support for Events
- [ ] Add support for Pagination
- [ ] Add more filters
- [ ] Add more tests
- [ ] Add more documentation