from ids20 import parse_id
from sorter20 import sort_ids

raw = "3,1,x7,2"
ids = [parse_id(part) for part in raw.split(",")]
print(sort_ids(ids))
