from simple_automation import Context, LogicError
from jinja2.exceptions import TemplateNotFound
from jinja2 import Template, Environment, FileSystemLoader

jinja2_env = Environment(
    loader=FileSystemLoader('templates', followlinks=True),
    autoescape=False)

def template_str(context: Context, template_str):
    template = Template(template_str)
    return template.render(context.vars())

def directory(context: Context, path: str) -> None:
    path = template_str(context, path)
    # todo stat
    context.remote_exec(["mkdir", "-m", oct(context.dir_mode)[2:], path])

def directories(context: Context, paths: list) -> None:
    for path in paths:
        directory(context, path)

def template(context: Context, src: str, dst: str) -> None:
    src = template_str(context, src)
    dst = template_str(context, dst)

    try:
        template = jinja2_env.get_template(src)
    except TemplateNotFound as e:
        raise LogicError("template not found: " + str(e))

    content = template.render(context.vars())
    print(f"template {src} -> {dst}")
    print(content)
