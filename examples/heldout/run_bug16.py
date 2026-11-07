from stats16 import mean, spread

readings = (float(x) for x in ["1.5", "2.5", "4.0"])
print(mean(readings))
print(spread(readings))
