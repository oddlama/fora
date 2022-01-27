import ast
from dataclasses import dataclass, field
import sys
from typing import Optional
from textwrap import dedent

from astdown.loader import ModuleAst

@dataclass
class DocstringSection:
    name: str
    decls: dict[str, str] = field(default_factory=dict)

@dataclass
class Docstring:
    content: Optional[str] = None
    sections: dict[str, DocstringSection] = field(default_factory=dict)

def parse_numpy_docstring(node: ast.AST, module: ModuleAst) -> Optional[Docstring]:
    docstr = None
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        docstr = node.value
    else:
        docstr = ast.get_docstring(node)
    if docstr is None:
        return None

    doc = Docstring()
    is_in_code = False

    section: Optional[DocstringSection] = None
    decl: Optional[str] = None
    content = ""
    def _commit_content():
        nonlocal section, content
        content = dedent(content).strip()

        if content != "":
            if section is None:
                doc.content = content
            elif decl is not None:
                section.decls[decl] = content
            content = ""

    lines = docstr.splitlines()
    skip_next_line = False
    for line, next in zip(lines, lines[1:] + [""]):
        if skip_next_line:
            skip_next_line = False
            continue

        line_stripped = line.strip()
        line_has_leading_whitespace = line.startswith(("  ", "\t"))

        # Don't interpret anything in code blocks
        if line_stripped.startswith("```"):
            is_in_code = not is_in_code
        if is_in_code:
            content += line + "\n"
            continue

        # If a section start is encountered, skip the section lines,
        # commit the currently accumulated content and start the section
        if next.startswith("----") and not line_has_leading_whitespace:
            if len(line_stripped) != len(next):
                print(f"warning: Encountered invalid section underline below '{line_stripped}' in {module.path}:{node.lineno}", file=sys.stderr)

            _commit_content()
            section = DocstringSection(name=line_stripped)
            doc.sections[section.name.lower()] = section
            skip_next_line = True
            continue

        # If a line without leading whitespace is encountered in a section,
        # and it wasn't a new section start, we have a new decl.
        if section is not None and not line_has_leading_whitespace:
            _commit_content()
            decl = line_stripped
            continue

        content += line + "\n"
    _commit_content()

    return doc
