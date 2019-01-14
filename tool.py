import re
import delegator

MODULES = ["france", "germany"]

MODULE_RE = re.compile(r"(?P<module>(\w+\/){2,5})(\w+\.\w+)")


def is_master_branch():
    """
    check if the current branch is master branch name
    :return:
    """
    c = delegator.run("git branch | grep \* | cut -d ' ' -f2")

    if c.err:
        print("current branch is not shown due to err")
        raise Exception
    if c.out == "master":
        print("tests behavior will be different if on the master branch")
        return True
    return False


def main():
    c = delegator.run("git diff origin/master --name-only")

    print(f"file changed:\n{c.out}")

    modules = set()
    for line in c.out.split("\n"):
        match = MODULE_RE.match(line)
        if match:
            module = match.group("module")
            if "tests" in module:
                module, _ = module.rstrip("/").rsplit("/", 1)
            modules.add(module)

    with open("autogen_test.sh", "w+") as f:
        if not modules:
            print("no changes in module is found. Tests phase will be skipped")
        else:
            for module in modules:
                f.write(f"pytest {module}\n")


if __name__ == "__main__":
    if not is_master_branch():
        main()
