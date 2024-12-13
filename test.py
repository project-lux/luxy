from pylux import PeopleGroups

result = (
    PeopleGroups()
    .filter(recordType="person")
    .filter(name="rembrandt")
    .filter(hasDigitalImage=True)
    .filter(text="rembrandt")
    .filter(gender="male")
    .filter(gender={"name": "male"})
    .filter(startAt={"name": "Amsterdam"})
    .get()
)

# print the number of results
print("Number of results:", result.num_results)

# print the url
print("URL:", result.url)

# print the json
print("JSON:", result.json)