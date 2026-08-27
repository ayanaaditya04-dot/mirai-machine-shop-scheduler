"""Constants and seed values for deterministic data generation.

All generation in src/data/generate.py uses SEED = 42 exclusively, per
PROJECT_PLAN.md's reproducibility requirement.
"""

SEED = 42

# Operator name pool — plausible Tamil/Kannada-region names for a Hosur shop.
# Large enough pool to avoid collisions at operator_count_range max (22).
OPERATOR_NAMES = [
    "Murugan S", "Karthik R", "Selvam P", "Ravichandran K", "Manikandan T",
    "Prakash V", "Suresh Kumar", "Elumalai N", "Balamurugan G", "Vijay Anand",
    "Senthil Kumar", "Raghavan M", "Dinesh Babu", "Gopalakrishnan S", "Anand R",
    "Nagaraj B", "Chandrasekaran V", "Mohan Das", "Rajesh Kanna", "Kannan P",
    "Venkatesh L", "Siva Kumar", "Baskar N", "Jagadish R", "Kumaresan V",
]

# Part catalog — auto-component parts consistent with the brief's example
# routing (turning -> milling -> drilling -> grinding -> inspection).
PART_CATALOG = [
    "Spindle Shaft", "Gear Blank", "Axle Housing Flange", "Clutch Hub",
    "Piston Pin", "Transmission Shaft", "Bearing Sleeve", "Brake Caliper Bracket",
    "Steering Knuckle", "Wheel Hub", "Pinion Shaft", "Idler Gear",
    "Differential Housing", "Camshaft Bushing", "Rocker Arm", "Tie Rod End",
    "Suspension Bracket", "Fuel Rail Mount", "Exhaust Flange", "Yoke Shaft",
    "Pump Housing", "Valve Body", "Sprocket", "Coupling Flange", "Shaft Collar",
]

PART_NUMBER_PREFIX = "SPW"
