import re
import delegator

from jsonschema import validate
from pathlib import Path
from poetry.utils.toml_file import TomlFile
from poetry.packages import Dependency, VCSDependency


VERSION_BUMP_RE = re.compile(
    r"(?P<major>\*)|(?P<minor>\d+\.\*)|(?P<patch>\d+\.\d+\.\*)"
)

ROOT_PATH = Path(".")

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

        self.requires = dict()
        self.dev_requires = dict()

    @property
    def name(self):
        return self._name

    @property
    def version(self):
        return self._version

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
            self.dev_requires[name] = dependency
        else:
            self.requires[name] = dependency

        return dependency


class ModifiedPackage(Package):
    def __init__(self, name, version, old_version):
        super().__init__(name, version)
        self._old_version = old_version
        self._next_version = _get_next_version(version, old_version)
        self._check()

    @property
    def next_version(self):
        return self._next_version

    @property
    def old_version(self):
        return self._old_version

    def _check(self):
        if not VERSION_BUMP_RE.match(self.version):
            raise RuntimeError(
                "changed packages should change the version in order to"
                "let the automated scripts to build the dependency tree"
            )


def _get_next_version(version_constraint, old_version) -> str:
    match = VERSION_BUMP_RE.match(version_constraint)
    major, minor, patch = old_version.split(".")

    if match.group("major"):
        return f"{int(major)+1}.0.0"

    elif match.group("minor"):
        return f"{major}.{int(minor)+1}.0"

    elif match.group("patch"):
        return f"{major}.{minor}.{int(patch)+1}"


def _get_old_version(pac_file) -> str:
    version_re = re.compile('version\s+=\s+"*(?P<version>(\d+\.\d+\.\d+))"*')
    c = delegator.run(f"git show origin/master:{pac_file} | grep version")
    match = version_re.match(c.out)
    if not match:
        raise RuntimeError(
            f"Modified package {pac_file} doesn't have a correct " f"semantic version"
        )
    return match.group("version")


class Pac:
    def __init__(self, file: Path, local_config: dict, package: Package):
        self._file = TomlFile(file)
        self._local_config = local_config
        self._package = package

    @property
    def file(self):
        return self._file

    @property
    def local_config(self):
        return self._local_config

    @property
    def package(self):
        return self._package

    @classmethod
    def create(cls, pac_file: Path, modified=False):

        local_config = TomlFile(pac_file.as_posix()).read()
        if "package" not in local_config:
            raise RuntimeError(
                "[package] section not found in {}".format(pac_file.name)
            )
        # Checking validity
        cls.check(local_config)

        # Load package
        if str(pac_file.parts[-2]) != local_config["package"]["name"]:
            raise RuntimeWarning(
                "[package] directory name is not as same as we defined in {},".format(
                    pac_file
                )
            )

        name = re.sub("/", ".", str(pac_file.parent))
        version = local_config["package"]["version"]

        if not modified:
            package = Package(name, version)
        else:
            old_version = _get_old_version(pac_file)
            package = ModifiedPackage(name, version, old_version)

        package.root_dir = pac_file.parent

        if "dependencies" in local_config:
            for name, constraint in local_config["dependencies"].items():
                package.add_dependency(name, constraint)

        if "dev-dependencies" in local_config:
            for name, constraint in local_config["dev-dependencies"].items():
                package.add_dependency(name, constraint, category="dev")

        return cls(pac_file, local_config, package)

    @classmethod
    def check(cls, config):
        """
        Checks the validity of a configuration
        """
        validate(config, PAC_JSON_SCHEMA)

class Application:
    _all_pacs = []

    def __init__(self, changes):
        self._changes = changes
        self.affected = []

    @property
    def changes(self):
        return self._changes

    @property
    def pacs(self):
        return self._all_pacs

    @classmethod
    def track_changes(cls):
        c = delegator.run("git diff origin/master --name-only")
        packages = set()

        for path in c.out.split("\n"):
            # we don't detect changes in non python code
            if Path(path).suffix != ".py":
                continue

            package = Path(path).parent
            if "tests" in str(package):
                package = Path(path).parent[1]
            packages.add(package)

        # remove root changes
        if ROOT_PATH in packages:
            packages.remove(ROOT_PATH)

        return [Pac.create(package / "pac.toml", modified=True) for package in packages]

    @classmethod
    def init(cls):
        c = delegator.run("git branch | grep \* | cut -d ' ' -f2")
        if c.err:
            raise RuntimeError("current branch is not shown due to err")
        if c.out == "master":
            raise RuntimeError(
                "tests behavior will be different if on the master branch")

        for path in Path(".").rglob("pac.toml"):
            pac = Pac.create(path)
            cls._all_pacs.append(pac)

        changes = cls.track_changes()

        return cls(changes)

    def find_affected_packages(self):
        changed_packges = {
            changed_pac.package.name: changed_pac.package.next_version
            for changed_pac in self.changes
        }

        print(changed_packges)

        # for pac in self._all_pacs:
        #     self._routes[pac.package.name] += [
        #         (dep_name, dep.pretty_constraint)
        #         for dep_name, dep in pac.package.requires.items()
        #     ]
        #
        #     print(
        #         [
        #             (dep_name, dep.pretty_constraint)
        #             for dep_name, dep in pac.package.requires.items()
        #         ]
        #     )
        #
        # for pac in self.pacs:
        #     for change_pac in self.changes:
        #         if change_pac.package.name in pac.package.requires:
        #             print("hi")


def main():
    app = Application.init()

    app.find_affected_packages()

    # print(f"affected: {}")
    #
    # with open("autogen_test.sh", "w+") as f:
    #     if not changed_packages:
    #         print("no changes in module is found. Tests phase will be skipped")
    #     else:
    #         for package in changed_packages:
    #             f.write(f"pytest {package}\n")


if __name__ == "__main__":
    main()
