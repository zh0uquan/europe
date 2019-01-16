import re
import delegator

from jsonschema import validate
from pathlib import Path
from poetry.utils.toml_file import TomlFile
from poetry.packages import Dependency, VCSDependency


AUTO_BUMP_RE = re.compile(r"(\*)|(\d+\.\*)|(\d+\.\d+\.\*)")

PAC_JSON_SCHEMA = {
    "definitions": {},
    "$schema": "http://json-schema.org/draft-07/schema#",
    "$id": "http://example.com/root.json",
    "type": "object",
    "title": "The Root Schema",
    "required": ["package", "dependencies", "dev-dependencies"],
    "properties": {
        "package": {
            "$id": "#/properties/package",
            "type": "object",
            "title": "The Package Schema",
            "required": ["name", "version"],
            "properties": {
                "name": {
                    "$id": "#/properties/package/properties/name",
                    "type": "string",
                    "title": "The Name Schema",
                    "default": "",
                    "pattern": "^(.*)$",
                },
                "version": {
                    "$id": "#/properties/package/properties/version",
                    "type": "string",
                    "title": "The Version Schema",
                    "default": "",
                    "examples": ["0.1.0"],
                    "pattern": "^(.*)$",
                },
            },
        },
        "dependencies": {
            "$id": "#/properties/dependencies",
            "type": "object",
            "title": "The Dependencies Schema",
            "default": None,
            "": "",
        },
        "dev-dependencies": {
            "$id": "#/properties/dev-dependencies",
            "type": "object",
            "title": "The Dev-dependencies Schema",
        },
    },
}


class Package:
    def __init__(self, name, version):
        self._name = name
        self._version = version

        self.requires = list()
        self.dev_requires = list()

    def add_dependency(self, name, constraint=None, category="main"):
        if constraint is None:
            constraint = "*"

        if isinstance(constraint, dict):

            if "git" in constraint:
                # VCS dependency
                dependency = VCSDependency(
                    name,
                    "git",
                    constraint["git"],
                    branch=constraint.get("branch", None),
                    tag=constraint.get("tag", None),
                    rev=constraint.get("rev", None),
                )
            else:
                version = constraint["version"]

                dependency = Dependency(name, version, category=category)
        else:
            dependency = Dependency(name, constraint, category=category)

        if category == "dev":
            self.dev_requires.append(dependency)
        else:
            self.requires.append(dependency)

        return dependency


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
    def create(cls, pac_file: Path, auto_bump=False):
        local_config = TomlFile(pac_file.as_posix()).read()
        if "package" not in local_config:
            raise RuntimeError(
                "[package] section not found in {}".format(pac_file.name)
            )
        # Checking validity
        cls.check(local_config, auto_bump)

        # Load package
        name = local_config["package"]["name"]
        version = local_config["package"]["version"]

        package = Package(name, version)
        package.root_dir = pac_file.parent

        if "dependencies" in local_config:
            for name, constraint in local_config["dependencies"].items():
                package.add_dependency(name, constraint)

        if "dev-dependencies" in local_config:
            for name, constraint in local_config["dev-dependencies"].items():
                package.add_dependency(name, constraint, category="dev")

        return cls(pac_file, local_config)

    @classmethod
    def check(cls, config, auto_bump=False):
        """
        Checks the validity of a configuration
        """
        validate(config, PAC_JSON_SCHEMA)

        if auto_bump and not AUTO_BUMP_RE.match(config["package"]["version"]):
            raise RuntimeError(
                "changed packages should change the version in order to"
                "let the automated scripts to build the dependency tree"
            )


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

    changed_packages = get_changed_packages()
    print(f"changed packages are {changed_packages}")

    dependency_tree = {}

    for path in Path(".").rglob("pac.toml"):
        auto_bump = True if str(path.parent) in changed_packages else False
        pac = Pac.create(path, auto_bump)

        print(pac.file, pac.local_config)

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
        if not changed_packages:
            print("no changes in module is found. Tests phase will be skipped")
        else:
            for package in changed_packages:
                f.write(f"pytest {package}\n")


if __name__ == "__main__":
    main()
