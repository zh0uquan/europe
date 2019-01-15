import toml
import delegator

from jsonschema import validate
from pathlib import Path
from poetry.utils.toml_file import TomlFile
from poetry.packages import ProjectPackage
PAC_JSON_SCHEMA = {}


class Pac:
    def __init__(self, file: Path, local_config: dict):
        self._file = TomlFile(file)
        self._local_config = local_config

    @property
    def file(self):
        return self._file

    @property
    def local_config(self):
        return self._local_config

    @classmethod
    def create(cls, cwd: Path):
        pac_file = Path(cwd) / "pac.toml"

        if not pac_file.exists():
            raise RuntimeError("Pac could not find a pac.toml file in {}".format(cwd))

        local_config = TomlFile(pac_file.as_posix()).read()
        if "package" not in local_config:
            raise RuntimeError(
                "[package] section not found in {}".format(pac_file.name)
            )
        # Checking validity
        cls.check(local_config)

        # Load package
        name = local_config["package"]["name"]
        version = local_config["package"]["version"]

        package = ProjectPackage(name, version, version)
        package.root_dir = pac_file.parent

        package.classifiers = local_config.get("classifiers", [])

        if "dependencies" in local_config:
            for name, constraint in local_config["dependencies"].items():
                if name.lower() == "python":
                    package.python_versions = constraint
                    continue

                if isinstance(constraint, list):
                    for _constraint in constraint:
                        package.add_dependency(name, _constraint)

                    continue

                package.add_dependency(name, constraint)

        if "dev-dependencies" in local_config:
            for name, constraint in local_config["dev-dependencies"].items():
                if isinstance(constraint, list):
                    for _constraint in constraint:
                        package.add_dependency(name, _constraint)

                    continue

                package.add_dependency(name, constraint, category="dev")

        return cls(pac_file, local_config)

    @classmethod
    def check(cls, config):
        """
        Checks the validity of a configuration
        """
        result = {"errors": [], "warnings": []}
        # Schema validation errors
        validation_errors = validate(config, PAC_JSON_SCHEMA)

        result["errors"] += validation_errors

        return result


def is_master_branch() -> bool:
    """
    check if the current branch is master branch name
    """
    c = delegator.run("git branch | grep \* | cut -d ' ' -f2")
    if c.err:
        raise RuntimeError("current branch is not shown due to err")
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

    for path in c.out.split("\n"):
        package = str(Path(path).parent)
        if "tests" in package:
            package, _ = package.rstrip("/").rsplit("/", 1)
        packages.add(package)

    if "." in packages:
        packages.remove(".")

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

    for path in Path(".").glob("**/*.toml"):
        with open(path) as tml_file:
            tml = toml.loads(tml_file.read())
            print(tml)

            dependency_tree[tml["package"]["name"]] = [
                package
                for package in tml["dependencies"]
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

    with open("autogen_test.sh", "w+") as f:
        if not packages:
            print("no changes in module is found. Tests phase will be skipped")
        else:
            for package in packages:
                f.write(f"pytest {package}\n")


if __name__ == "__main__":
    main()
