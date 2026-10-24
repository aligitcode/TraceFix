from lookup import find_user

users = [{"name": "ali"}]
result = find_user(users, "zed")
print(result["name"])
