import re
import toml
import delegator

from pathlib import Path

PACKAGE_RE = re.compile(r"(?P<package>(\w+\/){2,5})(\w+\.\w+)")


def is_master_branch() -> bool:
    """
    check if the current branch is master branch name
    """
    c = delegator.run("git branch | grep \* | cut -d ' ' -f2")
    if c.err:
        raise Exception("current branch is not shown due to err")
    if c.out == "master":
        print("tests behavior will be different if on the master branch")
        return True
    return False


def get_changed_packages() -> set:
    """
    get all the changed modules
    """
    c = delegator.run("git diff origin/master --name-only")
    packages = set()
    for line in c.out.split("\n"):
        match = PACKAGE_RE.match(line)
        if match:
            pacakge = match.group("package").rstrip("/")
            if "tests" in pacakge:
                pacakge, _ = pacakge.rsplit("/", 1)
            packages.add(pacakge)
    return packages


def struct_dependency_tree(tml: dict):
    """
    struct the trees using *.toml
    """
    pass


def bfs(dep_tree: dict, start: str, visited: set) -> None:
    """
    :param dep_tree: the dep tree build by toml
    :param start: start of the package
    :param visited: the packages all ready included
    """
    queue = [start]
    while queue:
        package = queue.pop(0)
        if package not in visited:
            visited.add(package)
            queue.extend(dep_tree[package])


def main():
    if is_master_branch():
        return

    packages = get_changed_packages()
    print(f"changed packages are {packages}")

    affected_packages = set(packages)
    dependency_tree = {}

    for path in Path('.').glob("**/*.toml"):
        with open(path) as tml_file:
            tml = toml.loads(tml_file.read())
            p

            dependency_tree[tml['package']['name']] = [
                package for package in tml['dependencies']
                if package.startswith("europe")
            ]

    print(f"affected: {dependency_tree}")

    # for module in modules:
    #     toml_path = next(Path(module).glob("*.toml"))
    #
    #     with open(toml_path) as tml_file:
    #         tml = toml.loads(tml_file.read())
    #
    #         package_name = "{prefix}.{package_name}".format(
    #             prefix=module.replace('/', '.'),
    #             package_name=tml["package"]["name"]
    #         )
    #
    #         print(tml['dependencies'])

    # with open("autogen_test.sh", "w+") as f:
    #     if not modules:
    #         print("no changes in module is found. Tests phase will be skipped")
    #     else:
    #         for module in modules:
    #             f.write(f"pytest {module}\n")


if __name__ == "__main__":
    main()
