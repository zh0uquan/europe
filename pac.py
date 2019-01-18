import re
import delegator

from jsonschema import validate
from pathlib import Path
from poetry.utils.toml_file import TomlFile
from poetry.packages import Package


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

NO_MANUL_BUMP_VERSION_ERROR = """
Please check package {name}
No manual version bump found in your toml file!
Please use fuzzy bump to increase the package you changed!
For example, if you want to release a new major change, do
change the version in pac.toml file as follows:

[package]
name = changed_package
version = "*" # indicates a major bump for automated scripts

"""


class ModifiedPackage(Package):
    def __init__(self, name, version, old_version):
        if not VERSION_BUMP_RE.match(version):
            raise RuntimeError(NO_MANUL_BUMP_VERSION_ERROR.format(name=name))

        self._old_version = old_version
        self._next_version = _get_next_version(version, old_version)
        super().__init__(name, self.next_version)

    @property
    def next_version(self):
        return self._next_version

    @property
    def old_version(self):
        return self._old_version


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
            f"Modified package {pac_file} doesn't have a correct semantic version"
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

        if str(pac_file.parent) == str(ROOT_PATH):
            name = local_config["package"]["name"]

        else:
            if pac_file.parts[-2] != local_config["package"]["name"]:
                raise RuntimeWarning(
                    "[package] directory name is not as same as we "
                    "defined in {},".format(pac_file)
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
    def __init__(self, changed_packages, pending_packages):
        self._changed_packages = changed_packages
        self._pending_packages = pending_packages
        self._affected_packages = []

    @property
    def changed_packages(self):
        return self._changed_packages

    @property
    def affected_packages(self):
        return self._affected_packages

    @classmethod
    def track_changed_paths(cls):
        c = delegator.run("git diff origin/master --name-only")
        package_paths = set()

        for path in c.out.split("\n"):
            # we don't detect changes in non python code
            if Path(path).suffix != ".py":
                continue

            package_path = Path(path).parent
            if "tests" in str(package_path):
                package_path = Path(path).parents[1]

            # remove root changes
            if ROOT_PATH in package_paths:
                package_paths.remove(ROOT_PATH)

            while True:
                # make sure changes belong to one of the package
                if (package_path / "pac.toml").exists():
                    break

                package_path = Path(package_path).parents[0]

            package_paths.add(package_path)

        return set(path / "pac.toml" for path in package_paths)

    @classmethod
    def init(cls):
        c = delegator.run("git branch | grep \* | cut -d ' ' -f2")
        if c.err:
            raise RuntimeError("current branch is not shown due to err")
        if c.out == "master":
            raise RuntimeError(
                "tests behavior will be different if on the master branch"
            )

        all_paths = set(Path(".").rglob("pac.toml"))
        changed_paths = cls.track_changed_paths()
        pending_paths = all_paths - changed_paths

        changed_packages = [
            Pac.create(path, modified=True).package for path in changed_paths
        ]

        pending_packages = [Pac.create(path).package for path in pending_paths]
        return cls(changed_packages, pending_packages)

    def run(self):
        self.find_affected_packages()
        self.generate_setup()
        self.generate_testfile()

    def generate_setup(self):
        pass

    def generate_testfile(self):
        tests_packages = self._affected_packages + self._changed_packages
        with open("autogen_test.sh", "w+") as f:
            if not tests_packages:
                print("No code changes in package is found. Safe PASS")
            else:
                for package in tests_packages:

                    path = re.sub("\.", "/", package.name)
                    print(f"test path: {path}")
                    f.write(f"pytest {path}\n")

    def find_affected_packages(self):
        affected_packages = set()
        changed_package_dict = {
            package.name: package for package in self._changed_packages
        }

        for package in self._pending_packages:
            # skip the package we have changed
            if package in self._changed_packages:
                continue

            for dependency in package.requires:
                dependency_name = dependency.name
                if dependency_name not in changed_package_dict:
                    continue

                if package in affected_packages:
                    continue

                # pac's dependency is affected by changed packages
                if dependency.accepts(changed_package_dict[dependency_name]):
                    affected_packages.add(package)

        self._affected_packages = list(affected_packages)

        return self._affected_packages


def main():
    app = Application.init()
    app.run()


if __name__ == "__main__":
    main()
