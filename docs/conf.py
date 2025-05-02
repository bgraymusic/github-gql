from dataclasses import dataclass
import importlib
import inspect
from pathlib import Path
import sys
from typing import Any


# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
sys.path.insert(0, str(Path(__file__).parent.parent))

# Configuration file for the Sphinx documentation builder.

# -- Project information

project = "GitHubGQL"
copyright = "2025, Brian Gray"
author = "Brian Gray"

release = "0.0.1"
version = "0.0.1"

# -- General configuration

extensions = [
    "sphinx.ext.napoleon",  # See: https://sphinxcontrib-napoleon.readthedocs.io/en/latest/
    # 'sphinx.ext.duration',
    # 'sphinx.ext.doctest',
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    # 'sphinx.ext.intersphinx',
]

napoleon_attr_annotations = True

intersphinx_mapping = {
    "python": ("https://docs.python.org/3/", None),
    "sphinx": ("https://www.sphinx-doc.org/en/master/", None),
}
intersphinx_disabled_domains = ["std"]

templates_path = ["_templates"]

# -- Options for HTML output

html_theme = "sphinx_rtd_theme"

# -- Options for EPUB output
epub_show_urls = "footnote"

# Collect classes and create autodoc pages


@dataclass
class ClassDef:
    module_name: str
    class_name: str


def find_classes(dir: str) -> list[ClassDef]:
    cls_dir = Path(f"{str(Path(__file__).parent.parent)}/{dir}")
    classes: list[ClassDef] = []
    for file in [x for x in cls_dir.iterdir() if x.name.endswith(".py")]:
        module_name = f"{dir}.{file.stem}"
        module = importlib.import_module(module_name)
        classes.extend(
            [
                ClassDef(module_name=module_name, class_name=name)
                for name, cls in inspect.getmembers(module)
                if name != "GitHubGQL" and inspect.isclass(cls) and cls.__module__ == module_name
            ]
        )
    return sorted(classes, key=lambda x: x.class_name)


all_classes = find_classes("githubgql")

other_classes_template = """
Other Classes
=============

&autoClassList;
"""


def autoclass_entry(module_name: str, class_name: str) -> str:
    return f".. autoclass:: {module_name}.{class_name}"


with open("other-classes.rst", "w") as f:
    f.write(
        other_classes_template.replace(
            "&autoClassList;", "\n".join([autoclass_entry(x.module_name, x.class_name) for x in all_classes])
        )
    )

class_page_template = """
&className;
&titleSeparator;

.. autoclass:: &moduleName;.&className;()
"""

# for cls in all_classes:
#     with open(f'{cls.class_name}.rst', 'w') as f:
#         template = class_page_template.replace('&moduleName;', cls.module_name)
#         template = template.replace('&className;', cls.class_name)
#         template = template.replace('&titleSeparator;', '=' * len(cls.class_name))
#         f.write(template)
