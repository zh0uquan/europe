import re
import delegator

MODULES = [
    "france", "germany"
]

MODULE_NAME = re.compile("(europe)\/(\w+)\/(.*)")

c = delegator.run("git diff origin/master --name-only")


marks = set()
for line in c.out.split("\n"):
    print(line)
    match = MODULE_NAME.match(line)
    if match:
        marks.add(f"-m {match.group(2)}")

with open("autogen_test.sh", "w+") as f:
    if not marks:
        print("no changes in module is found. Tests phase will be skipped")
    else:
        f.write(f"poetry run pytest {' '.join(mark for mark in marks)}")
