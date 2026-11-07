def mean(data):
    total = 0
    count = 0
    for x in data:
        total += x
        count += 1
    return total / count


def spread(data):
    return max(data) - min(data)
