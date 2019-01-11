import delegator

c = delegator.run("poetry run pytest -m france")

if c.err:
    raise Exception("failed")
