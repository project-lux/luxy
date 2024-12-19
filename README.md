![Lux Logo](https://github.com/project-lux/luxy/blob/main/docs/images/luxy-logo.jpg?raw=true)

[![PyPI version](https://badge.fury.io/py/luxy.svg)](https://badge.fury.io/py/luxy)
[![GitHub stars](https://img.shields.io/github/stars/project-lux/luxy.svg)](https://github.com/project-lux/luxy/stargazers)
[![GitHub release](https://img.shields.io/github/v/release/project-lux/luxy)](https://github.com/project-lux/luxy/releases)


LuxY is a Python wrapper for Yale's Lux API. Currently, there is minimal support for the API, but it is in active development.

# Installation

```bash
pip install luxy
```

# Usage

The classes of LuxY replicate the classes of the Lux API. They are:

1. PeopleGroups (agent) - People and Groups that are either individuals or organizations
2. Objects (item) - Physical objects in Yale's collections
3. Works (work) - Visual and textual works, including images, texts, and other creative expressions
4. Places (place) - Geographic locations and named spaces
5. Concepts (concept) - Types, materials, languages, measurement units, currencies and other conceptual entities
6. Events (event) - Historical events and occurrences
7. Collections (set) - Collections and sets of objects curated by Yale's institutions

Each of these has common and unique filters that take different data types, from strings to numbers to dates. LuxY also supports nested filters, which are used to filter by multiple levels of the hierarchy. This allows users to create complex queries similar to the ones found in the Lux UI.

## People Groups

```python
from luxy import PeopleGroups

result = PeopleGroups().filter(name="Rembrandt").get()
print(result.url)
print(result.json)
```

## Objects

```python
from luxy import Objects

result = Objects().filter(name="Rembrandt").get()
print(result.url)
print(result.json)
```

## Works

```python
from luxy import Works

result = Works().filter(name="Painting").get()
print(result.url)
print(result.json)
```

## Places

```python
from luxy import Places

result = Places().filter(name="Amsterdam").get()
print(result.url)
print(result.json)
```

## Concepts

```python
from luxy import Concepts

result = Concepts().filter(name="gilding").get()
print(result.url)
print(result.json)
```

## Events

```python
from luxy import Events

result = Events().filter(name="Thirty Years War").get()
print(result.url)
print(result.json)
```

## Collections

```python
from luxy import Collections

result = Collections().filter(name="Letters").get()
print(result.url)
print(result.json)
```

## Working with Numerical Filters

Numerical filters are a bit tricky because they require a tuple with the value and the comparison operator.

```python
from luxy import Objects

result = Objects().filter(height=(1, ">=")).get()
print(result.url)
print(result.json)
```

## Working with Date Filters

Date filters are a bit tricky because they require a tuple with the value and the comparison operator. The value should be a string in the format of `YYYY-MM-DDTHH:MM:SS.SSSZ`.

```python
from luxy import Objects

result = Objects().filter(encounteredDate=("1987-01-01T00:00:00.000Z", ">=")).get()
print(result.url)
print(result.json)
```

## Understanding Options

Each filter has a set of options that can be used to filter the data. These options are stored in the `get_options()` method.

```python
from luxy import PeopleGroups

options = PeopleGroups().get_options()
print(options)

# pretty print the options
PeopleGroups().list_filters()
```

### Complex Example
```python
from luxy import PeopleGroups

result = (
    PeopleGroups()
    .filter(recordType="person")
    .filter(hasDigitalImage=True)
    .filter(text="rembrandt")
    .filter(gender={"name": "male"})
    .get()
)

# print the number of results
print("Number of results:", result.num_results)

# print the url
print("URL:", result.url)

# print the json
print("JSON:", result.json)
```

#### Expected Output

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

## Nested MemberOf Filters

```python
result = (
    Objects()
    .filter(hasDigitalImage=True)
    .filter(
        OR=[
            Objects().memberOf("Letters", depth=2),
            Objects().memberOf("Letters", depth=3),
            Objects().memberOf("Letters", depth=4)
        ]
    )
    .filter(name="letter")
    .get()
)

print(result.url)
print(result.json)
```


# Roadmap

## v. 0.0.2

- [x] Add support for People/Groups
    - [ ] Filter by:
        - [x] Has Digital Image
        - [x] Gender
        - [x] Nationality (nationality)
        - [x] Person or Group Class
        - [x] Categorized As (classification)
        - [x] Born/Formed At (startAt)
        - [x] Born/Formed Date
        - [x] Carried Out (carriedOut)
        - [x] Created Object (produced)
        - [x] Created Works (created)
        - [x] Curated (curated)
        - [x] Died/Dissolved At (endAt)
        - [x] Died/Dissolved Date
        - [x] Encountered
        - [x] Founded By
        - [x] Founded Group
        - [x] Have Member
        - [x] ID
        - [x] Identifier
        - [x] Influenced (influenced)
        - [x] Influenced Creation Of Objects
        - [x] Influenced Creation Of Works
        - [x] Member Of (memberOf)
        - [x] Occupation/Role (occupation)
        - [x] Professional Activity Categorized As (professionalActivity)
        - [x] Professionally Active At (activeAt)
        - [x] Professionally Active Date
        - [x] Published (published)
        - [x] Subject Of
- [x] Add support for Objects
- [x] Add support for Works
- [x] Add support for Places
- [x] Add support for Concepts
- [x] Add support for Events
- [x] Add support for Pagination
- [x] Add support for Downloading Page JSON
- [x] Add support for Downloading Item JSON
- [x] Add more filters
- [x] Add support for date filters
- [x] Add support for numbers
    - [x] Greater Than
    - [x] Less Than
    - [x] Greater Than or Equal To
    - [x] Less Than or Equal To
    - [x] Equal To
    - [x] Not Equal To
- [x] Add And support for filters
- [x] Add support for OR filters
- [x] Add support for have All of # AND
- [x] Add support for have Any of # OR
- [x] Add support for have None of # NOT
- [x] Add more tests
- [x] Add more documentation
- [x] Add a check to make sure a filter exists
