"""Count lines of code for each implementation (blank lines, comments and docstrings excluded)."""
import ast
import io
import tokenize
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FILES = {"DRF": ROOT / "drf_app" / "project.py", "FastAPI": ROOT / "fastapi_app" / "main.py"}


def code_lines(path):
    src = path.read_text()
    doc_lines = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], "value", None), ast.Constant) \
                    and isinstance(body[0].value.value, str):
                doc_lines.update(range(body[0].lineno, body[0].end_lineno + 1))
    comment_only = set()
    for tok in tokenize.generate_tokens(io.StringIO(src).readline):
        if tok.type == tokenize.COMMENT and tok.line.strip().startswith("#"):
            comment_only.add(tok.start[0])
    return sum(1 for i, l in enumerate(src.splitlines(), 1) if l.strip() and i not in doc_lines and i not in comment_only)


for name, p in FILES.items():
    print(f"{name:8} {code_lines(p):4} code lines   ({p.relative_to(ROOT)})")
