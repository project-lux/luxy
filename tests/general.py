from luxy import PeopleGroups, PROFILE_NAME, PROFILE_COUNT

# Just labels:
slim = PeopleGroups().filter(name="Rembrandt").get(profile=PROFILE_NAME)
print(slim.json)
for item in slim.json["orderedItems"]:
    print(item["label"], item["id"])

# Just the total count:
count = PeopleGroups().filter(name="Rembrandt").get(profile=PROFILE_COUNT).json["totalItems"]
print("Total count:", count)