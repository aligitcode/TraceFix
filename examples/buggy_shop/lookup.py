def find_user(users, name):
    for user in users:
        if user["name"] == name:
            return user
