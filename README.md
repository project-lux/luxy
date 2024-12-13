![Lux Logo](./docs/images/luxy-logo.jpg)

[![PyPI version](https://badge.fury.io/py/luxy.svg)](https://badge.fury.io/py/luxy)
[![GitHub stars](https://img.shields.io/github/stars/project-lux/luxy.svg)](https://github.com/project-lux/luxy/stargazers)
[![GitHub release](https://img.shields.io/github/v/release/project-lux/luxy)](https://github.com/project-lux/luxy/releases)


LuxY is a Python wrapper for Yale's Lux API. Currently, there is minimal support for the API, but it is in active development.

# Installation

**warning** not on pypi yet...

```bash
pip install luxy
```

# Usage

```python
from luxy import PeopleGroups

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

## Working with Pagination

```python
from luxy import PeopleGroups

result = (
    PeopleGroups()
    .filter(endAt={"name": "Amsterdam"})
    .get()
)

# print the number of results
print("Number of results:", result.num_results)
print("Number of pages:", result.num_pages())

for i, page in enumerate(result.get_page_data_all(), 1):
    if i > 2: # Break after 2 pages
        break
    print(f"Page {i}:", page["id"])
    for j, item in enumerate(result.get_items(page)):
        print(f"Item {j}:", result.get_item_data(item)["_label"])
```

# Roadmap

- [x] Add support for People/Groups
    - [ ] Filter by:
        - [x] Has Digital Image
        - [x] Gender
        - [ ] Nationality (nationality)
        - [x] Person or Group Class
        - [ ] Categorized As (classification)
        - [x] Born/Formed At (startAt)
        - [ ] Born/Formed Date
        - [ ] Carried Out (carriedOut)
        - [x] Created Object (produced)
        - [x] Created Works (created)
        - [x] Curated (curated)
        - [x] Died/Dissolved At (endAt)
        - [ ] Died/Dissolved Date
        - [ ] Encountered
        - [ ] Founded By
        - [ ] Founded Group
        - [ ] Have Member
        - [ ] ID
        - [ ] Identifier
        - [x] Influenced (influenced)
        - [ ] Influenced Creation Of Objects
        - [ ] Influenced Creation Of Works
        - [ ] Member Of (memberOf)
        - [x] Occupation/Role (occupation)
        - [x] Professional Activity Categorized As (professionalActivity)
        - [x] Professionally Active At (activeAt)
        - [ ] Professionally Active Date
        - [x] Published (published)
        - [ ] Subject Of
- [ ] Add support for Objects
- [ ] Add support for Works
- [ ] Add support for Places
- [ ] Add support for Concepts
- [ ] Add support for Events
- [x] Add support for Pagination
- [x] Add support for Downloading Page JSON
- [x] Add support for Downloading Item JSON
- [ ] Add more filters
- [x] Add And support for filters
- [ ] Add support for OR filters
- [ ] Add support for have All of
- [ ] Add support for have Any of
- [ ] Add support for have None of
- [ ] Add more tests
- [ ] Add more documentation