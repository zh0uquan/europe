# import delegator
#
# c = delegator.run("poetry run pytest -m france")
#
# print(c.out)
#
# if c.err:
#     raise Exception("failed")

with open("test-script.sh") as f:
    f.write("poetry run pytest -m france")
